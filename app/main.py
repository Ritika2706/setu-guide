"""Run entry point: uvicorn app.main:app --reload --port 8000

The application itself lives in app/api/main.py (app/api is the routes folder
per the repo layout); this module only re-exports it so both run commands work:
    uvicorn app.main:app --reload --port 8000
    uvicorn app.api.main:app --reload
"""
from app.api.main import app

__all__ = ["app"]
