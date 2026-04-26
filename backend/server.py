"""Supervisor entry point — re-exports the FastAPI app from app.main.

Local supervisor runs `uvicorn server:app` from /app/backend.
Render runs `uvicorn app.main:app` from /app/backend.
Both resolve to the same FastAPI instance.
"""
from app.main import app  # noqa: F401
