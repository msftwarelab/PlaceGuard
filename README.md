# 🛡️ PlaceGuard — VOYGR Place Validation Service

> **Production-grade LangGraph ReAct agent that validates LLM-generated place recommendations for VOYGR (YC W26).**

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-green.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28-red.svg)](https://streamlit.io)

---

## The Problem

VOYGR's LLM recommendations sometimes suggest places that are **closed**, **mispriced**, **hallucinated**, or **outdated**. PlaceGuard is the validation layer between LLM output and end users.

---

## Architecture

```
User Query / LLM Output
        │
        ▼
┌─────────────────────────────────────────┐
│  FastAPI  POST /validate-place          │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│  LangGraph ReAct Agent                  │
│  1. validate_place_existence            │
│  2. check_operating_hours               │
│  3. verify_pricing                      │
│  4. assess_safety_and_risk              │
│  5. enrich_place_data                   │
│  6. lookup_similar_alternatives         │
└────────────────┬────────────────────────┘
                 │
                 ▼
        ValidationResult JSON
        (VOYGR Business Validation API format)
```

---

## Quickstart

```bash
# 1. Install
pip install -e ".[dev]"

# 2. Configure
cp .env.example .env
# Set OPENAI_API_KEY in .env

# 3. Run API
make serve        # http://localhost:8000/docs

# 4. Run Dashboard
make dashboard    # http://localhost:8501
```

---

## API

### POST /validate-place

```bash
curl -X POST http://localhost:8000/validate-place \
  -H "Content-Type: application/json" \
  -d '{"query": "Rooftop bar in Gangnam under $20 cocktails", "context": {"city": "Seoul"}}'
```

Response:
```json
{
  "place_id": "sky-lounge-gangnam",
  "name": "Sky Lounge Gangnam",
  "status": "valid",
  "confidence": 0.87,
  "exists": true,
  "operating": true,
  "price_verified": true,
  "safety_score": 0.92,
  "details": {"hours": "Mon-Sun 6PM-2AM", "price_tier": "$$"},
  "issues": [],
  "reasoning_chain": ["Found: Sky Lounge Gangnam", "Verified hours", "Price confirmed under $20"]
}
```

---

## VOYGR Benchmark Suite (6 Scenarios)

| ID | Scenario | Expected |
|----|----------|----------|
| bench_01 | Valid rooftop bar Gangnam | valid |
| bench_02 | Hallucinated place | invalid |
| bench_03 | Permanently closed restaurant | invalid |
| bench_04 | Stale data (6 months old) | uncertain |
| bench_05 | Nobu Tokyo fine dining | valid |
| bench_06 | Ambiguous Myeongdong query | valid |

```bash
make benchmarks       # Run via curl
make test-benchmarks  # Run via pytest
```

---

## Project Structure

```
src/
  agent/
    graph.py         # LangGraph ReAct agent
    tools.py         # 6 validation tools
    schemas.py       # Pydantic models
    data_layer.py    # Mock DB (→ PostgreSQL in prod)
    llm_provider.py  # OpenAI/Anthropic/Gemini abstraction
    benchmarks.py    # 6 test scenarios
  api/
    main.py          # FastAPI endpoints
  dashboard/
    app.py           # Streamlit dark theme UI
tests/
  unit_tests/        # Schema, data layer, tool tests
  integration_tests/ # API endpoint + benchmark tests
```

---

## Deploy to Railway

1. Push to GitHub
2. New Railway project → Deploy from GitHub
3. Set env: `OPENAI_API_KEY=sk-...`, `PYTHONPATH=src`
4. Start command: `uvicorn api.main:app --host 0.0.0.0 --port $PORT`

---

## Multi-LLM Support

Set whichever key you have — falls back in order: OpenAI → Anthropic → Gemini.

```bash
OPENAI_API_KEY=sk-...        # gpt-4-turbo-preview
ANTHROPIC_API_KEY=sk-ant-... # claude-3-opus
GOOGLE_API_KEY=...           # gemini-pro
```

---

## Docker

```bash
docker-compose up --build
# API: localhost:8000  Dashboard: localhost:8501
```

---

*Built for VOYGR (YC W26) · May 2026*
