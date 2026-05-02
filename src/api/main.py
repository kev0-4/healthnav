import asyncio
import json
import logging
import os
import time
from pathlib import Path

import openai
import requests as _requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from src.pipeline.pipeline import run
from src.utils.review_cache import cache_get, cache_set

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("api")

app = FastAPI(title="HealthNav API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:4173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
GOOGLE_API_KEY  = os.getenv("GOOGLE_API_KEY")
SERPER_API_KEY  = os.getenv("SERPER_API_KEY")
_SERPER_HEADERS = {"X-API-KEY": SERPER_API_KEY or "", "Content-Type": "application/json"}
_HBP_KNOWLEDGE = (Path(__file__).parent / "hbp_knowledge.md").read_text()

_CHAT_SYSTEM = """You are HealthNav Assistant — a healthcare cost planning helper for Indian patients.

## Healthcare Knowledge Base
{knowledge}

## Current Patient Result
{result_summary}

## Instructions
- Answer ONLY questions about the patient result above or India's AB-PMJAY / HBP healthcare cost planning
- Always cite specific numbers from the result when answering cost questions
- For medical advice, treatment recommendations, or diagnosis: decline and say "please consult a qualified doctor"
- For unrelated questions: decline politely in one sentence
- Be concise — 2–4 sentences unless the question genuinely needs more detail
- Never fabricate procedure codes, rates, or hospital names not shown above
- If unsure, say so honestly""".strip()


def _condense_result(ctx: dict) -> str:
    lines = []
    lines.append(
        f"Condition: {ctx.get('condition')} (ICD-10: {ctx.get('icd10')}, "
        f"{ctx.get('confidence')}% confidence, {ctx.get('severity')} severity)"
    )
    lines.append(f"City: {ctx.get('city')} — Tier {ctx.get('city_tier')}")

    cost = ctx.get("cost") or {}
    total = cost.get("total", [0, 0])
    proc  = cost.get("procedure", [0, 0])
    stay  = cost.get("stay", [0, 0])
    meds  = cost.get("medication", [0, 0])
    cont  = cost.get("contingency", [0, 0])
    lines.append(
        f"Total estimate: ₹{total[0]:,}–₹{total[1]:,}  "
        f"(procedure ₹{proc[0]:,}–₹{proc[1]:,} | "
        f"stay ₹{stay[0]:,}–₹{stay[1]:,} | "
        f"meds ₹{meds[0]:,}–₹{meds[1]:,} | "
        f"contingency ₹{cont[0]:,}–₹{cont[1]:,})"
    )

    per_proc = ctx.get("per_procedure_costs") or []
    if per_proc:
        ppc = "  " + "\n  ".join(
            f"{p['code']} {p['name']}: ₹{p['applied_cost']:,} (×{p['stacking_multiplier']})"
            for p in per_proc
        )
        lines.append(f"Procedure costs:\n{ppc}")

    pathway = ctx.get("pathway") or []
    if pathway:
        steps = "  " + "\n  ".join(
            f"Step {s.get('step')}: [{s.get('type')}] {s.get('title')}"
            + (f" [{s.get('procedure_code')}]" if s.get("procedure_code") else "")
            for s in pathway
        )
        lines.append(f"Pathway:\n{steps}")

    return "\n".join(lines)


class QueryRequest(BaseModel):
    query: str
    city: str | None = None
    budget_inr: int | None = None
    age: int | None = None


def _build_query(req: QueryRequest) -> str:
    q = req.query
    if req.city and req.city.lower() not in q.lower():
        q += f", {req.city}"
    if req.budget_inr:
        q += f", budget {req.budget_inr}"
    if req.age:
        q += f", age {req.age}"
    return q


class ChatRequest(BaseModel):
    question: str
    result_context: dict


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
def analyze(req: QueryRequest):
    q = _build_query(req)
    t0 = time.time()
    log.info("POST /analyze — %r", q)
    try:
        result = run(q)
        log.info("  → status=%s condition=%s city_tier=%s  (%.1fs)",
                 result.get("status"), result.get("condition"),
                 result.get("city_tier"), time.time() - t0)
        return result
    except RuntimeError as e:
        msg = str(e)
        log.warning("  → RuntimeError: %s", msg)
        raise HTTPException(status_code=503, detail=msg)
    except Exception as e:
        log.error("  → ERROR: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze-stream")
async def analyze_stream(req: QueryRequest):
    q = _build_query(req)
    log.info("POST /analyze-stream — %r", q)
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def on_progress(step: int, status: str):
        asyncio.run_coroutine_threadsafe(
            queue.put({"step": step, "status": status}), loop
        )

    def _run():
        try:
            result = run(q, on_progress)
            asyncio.run_coroutine_threadsafe(
                queue.put({"done": True, "result": result}), loop
            )
        except RuntimeError as e:
            asyncio.run_coroutine_threadsafe(
                queue.put({"error": str(e)}), loop
            )
        except Exception as e:
            log.error("stream pipeline error: %s", e, exc_info=True)
            asyncio.run_coroutine_threadsafe(
                queue.put({"error": "Analysis failed. Please try again."}), loop
            )

    async def generate():
        loop.run_in_executor(None, _run)
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event, default=str)}\n\n"
            if event.get("done") or event.get("error"):
                break

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/chat")
def chat(req: ChatRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question is required")

    result_summary = _condense_result(req.result_context)
    system = _CHAT_SYSTEM.format(
        knowledge=_HBP_KNOWLEDGE,
        result_summary=result_summary,
    )
    log.info("POST /chat — %r", req.question[:80])
    try:
        resp = _openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": req.question},
            ],
            temperature=0.3,
            max_tokens=400,
        )
        answer = (resp.choices[0].message.content or "").strip()
        log.info("  → chat answered (%d chars)", len(answer))
        return {"answer": answer}
    except openai.RateLimitError:
        raise HTTPException(status_code=429, detail="Rate limit reached. Please try again shortly.")
    except Exception as e:
        log.error("  → chat ERROR: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Chat unavailable. Please try again.")


@app.get("/hospital/{hospital_id}/reviews")
def hospital_reviews(
    hospital_id: str,
    name: str = Query(default=""),
    address: str = Query(default=""),
):
    cache_key = f"reviews:{hospital_id}"
    cached = cache_get(cache_key)
    if cached:
        log.info("GET /hospital/%s/reviews — cache hit", hospital_id)
        return cached

    empty = {"rating": None, "total_ratings": None, "source_title": None,
             "source_url": None, "google_maps_url": None}

    if not SERPER_API_KEY:
        return empty

    search_q = f"{name} {address}".strip() or name or hospital_id
    result = dict(empty)

    # /places — get CID for a direct Google Maps link
    try:
        pr = _requests.post(
            "https://google.serper.dev/places",
            headers=_SERPER_HEADERS,
            json={"q": search_q, "gl": "in", "hl": "en"},
            timeout=6,
        )
        pr.raise_for_status()
        places = pr.json().get("places", [])
        if places:
            cid = places[0].get("cid")
            if cid:
                result["google_maps_url"] = f"https://www.google.com/maps?cid={cid}"
    except Exception as e:
        log.warning("Serper /places failed: %s", e)

    # /search — get aggregate rating from organic results
    try:
        sr = _requests.post(
            "https://google.serper.dev/search",
            headers=_SERPER_HEADERS,
            json={"q": f"{name} reviews", "gl": "in", "hl": "en", "num": 5},
            timeout=6,
        )
        sr.raise_for_status()
        organic = sr.json().get("organic", [])
        for item in organic:
            if item.get("rating") and item.get("ratingCount"):
                result["rating"] = item["rating"]
                result["total_ratings"] = item["ratingCount"]
                result["source_title"] = item.get("title", "")
                result["source_url"] = item.get("link", "")
                break
    except Exception as e:
        log.warning("Serper /search failed: %s", e)

    cache_set(cache_key, result)
    log.info("GET /hospital/%s/reviews — fetched & cached (rating=%s)", hospital_id, result["rating"])
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
