# Setu Guide POC
Stage-aware Setu Guide assistant for the Chat with Setu Guide screen (Sambandh Setu).

## Run
    pip install -r requirements.txt
    uvicorn app.api.main:app --reload
    pytest -q

## Endpoint
POST /v1/guide/chat. Schema: app/schemas/guide.py (frozen by lead).
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
