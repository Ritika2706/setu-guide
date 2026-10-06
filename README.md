# Setu Guide POC
Stage-aware Setu Guide assistant for the Chat with Setu Guide screen (Sambandh Setu).

## Run
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8000      # app.api.main:app is the same app
    pytest -q

Swagger: http://localhost:8000/docs

## Endpoint
POST /v1/guide/chat. Schema: app/schemas/guide.py (frozen by lead).
GET /health -> {"status": "ok"} (liveness for CI and deploys).
Express (requireAuth) calls this service and sends only consented fields in `context` ({"viewer": {...}, "match": {...}}).
This service never reads MongoDB.

## Layout
    app/api       FastAPI routes
    app/schemas   frozen request/response models
    app/core      orchestrator (route, context, retrieve, generate)
    app/rag       knowledge base and retrieval
    app/safety    safety guard
    data/         synthetic profiles and test conversations
    tests/        pytest
    docs/         API docs, evaluation report, integration notes

Each person's tasks: docs/team/<role>.md
See CONTRIBUTING.md for branch rules and owners.
