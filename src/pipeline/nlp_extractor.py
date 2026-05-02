import json
import os
import openai
from dotenv import load_dotenv

load_dotenv()

_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_MODELS = ["gpt-4o-mini"]


def _chat_create(**kwargs):
    """Wrapper that retries with max_completion_tokens if model rejects max_tokens."""
    create = _client.chat.completions.create
    try:
        return create(**kwargs)
    except openai.BadRequestError as e:
        if "max_tokens" in str(e) and "max_completion_tokens" in str(e):
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
            return create(**kwargs)
        raise


_SYSTEM_PROMPT = """
You are a medical triage assistant for an Indian healthcare cost estimation platform.

Extract structured information from the user's health query. Return ONLY valid JSON — no markdown, no explanation, no code fences.

Output schema (all fields required):
{
  "symptoms": [<string>],
  "body_system": <string>,
  "duration_signal": <string or null>,
  "comorbidities": [<string>],
  "city": <string or null>,
  "budget_inr": <integer or null>,
  "age": <integer or null>,
  "conditions": [
    {"name": <string>, "icd10": <string>, "confidence": <float 0.0-1.0>, "severity": <"mild"|"moderate"|"severe">},
    ...
  ],
  "top_condition": <string>,
  "top_icd10": <string>,
  "top_confidence": <float>,
  "top_severity": <"mild"|"moderate"|"severe">,
  "needs_clarification": <boolean>,
  "clarification_question": <string or null>
}

Rules:
- List top 3 most likely conditions ranked by probability descending
- confidence: float 0.0-1.0 per condition (values don't need to sum to 1.0)
- severity: "mild" | "moderate" | "severe" based on symptom description
- budget_inr: convert "3 lakhs" → 300000, "50k" → 50000, "2.5 lakhs" → 250000, else null
- needs_clarification: true ONLY if top condition confidence < 0.60 OR city is null
- clarification_question: one short question if needs_clarification is true, else null
- OPD-only queries (cold, flu, routine checkup): set severity "mild", keep needs_clarification false if city is given
- Never diagnose or recommend treatments — this is for cost planning only
""".strip()


def _parse_raw(raw: str | None) -> dict | None:
    """Strip markdown fences and parse JSON. Returns None if empty or unparseable."""
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def extract(query: str) -> dict:
    last_err = None
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user",   "content": query},
    ]
    for model in _MODELS:
        # Pass 1: with response_format for guaranteed JSON
        try:
            resp = _chat_create(
                model=model,
                messages=messages,
                temperature=1,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            result = _parse_raw(resp.choices[0].message.content)
            if result is not None:
                return result
            # Empty content — fall through to plain retry
        except openai.RateLimitError as e:
            last_err = e
            continue
        except openai.NotFoundError:
            continue
        except openai.APIError:
            pass  # response_format unsupported — fall through

        # Pass 2: without response_format (plain text → parse manually)
        try:
            resp = _chat_create(
                model=model,
                messages=messages,
                temperature=1,
                max_tokens=1024,
            )
            result = _parse_raw(resp.choices[0].message.content)
            if result is not None:
                return result
        except openai.RateLimitError as e:
            last_err = e
            continue
        except openai.NotFoundError:
            continue
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(
        "OpenAI API unavailable or credits exhausted. "
        "Check your API key and credit balance at platform.openai.com."
    ) from last_err


if __name__ == "__main__":
    tests = [
        "knee pain for 3 months, age 58, Nagpur, budget 2.5 lakhs",
        "chest pain sometimes, age 55, Mumbai",
        "fever and cold for 2 days",
    ]
    for q in tests:
        print(f"\nQuery: {q}")
        result = extract(q)
        print(json.dumps(result, indent=2))
