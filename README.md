# HealthNav — AI Healthcare Cost Navigator for India

> Hackathon PS 4B — AI-powered pre-decision cost intelligence for Indian patients

HealthNav takes a vague natural language query ("chest pain in Nagpur, budget 2 lakhs") and returns a structured cost estimate, matched hospitals, and clinical pathway — before the patient commits to any hospital.

## Pipeline

```
Natural language query
  → Disease + severity extraction (OpenAI gpt-4o-mini + ICD-10)
  → Clinical pathway mapping (HBP 2022 pre-auth logic)
  → Cost estimation (HBP rates × city tier × hospital type multiplier)
  → Provider matching (hospital DB + Serper ratings + OSRM distances)
  → Real-time SSE streaming to frontend
```

## Stack

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · pyodbc |
| LLM | OpenAI gpt-4o-mini |
| Cost data | HBP 2022 (AB-PMJAY rates) |
| Hospital DB | Azure SQL Server |
| Ratings | Serper.dev (cached 90 days in Azure SQL) |
| Routing | OSRM public API |
| Frontend | React · Vite · Tailwind CSS |

## Setup

### Backend
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
python -m src.api.main
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Required `.env` keys
```
OPENAI_API_KEY=
SERPER_API_KEY=
GOOGLE_API_KEY=
DB_SERVER=
DB_NAME=
DB_USER=
DB_PASSWORD=
```

## Features

- **Real-time pipeline progress** via SSE — watch each stage complete live
- **City-tier cost adjustment** — Tier 1/2/3 rates per HBP 2022
- **Hospital matching** with NABH status, bed count, specialty tags
- **Live ratings** fetched from Serper + cached in Azure SQL (90-day TTL)
- **Drive distance + time** via OSRM routing from user's location
- **Hospital detail sheet** with map embed, ratings, cost breakdown
- **AI chat assistant** — ask questions about your result in plain English

## Data Sources

- **HBP 2022** — AB-PMJAY procedure rates (NHA)
- **NHP Hospital Directory** — data.gov.in (~3,000 hospitals)
- **CHSI Study** — BMC Health Services Research (tier multiplier basis)
- **Serper.dev** — Google search ratings proxy
