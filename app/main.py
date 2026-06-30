from fastapi import FastAPI
from fastapi.responses import FileResponse

from .agent import Agent
from .config import get_settings
from .db import PostgresDatabase
from .llm import LLMClient
from .schemas import AskRequest, AskResponse

app = FastAPI(title="AskDB", description="Ask your database questions in plain English")

_s = get_settings()
_db = PostgresDatabase(_s.database_url)
_agent: Agent | None = None


def agent() -> Agent:
    global _agent
    if _agent is None:  # built on first use so importing the app needs no key/DB
        _agent = Agent(_db, LLMClient(_s), _s.max_retries, _s.row_limit)
    return _agent


@app.get("/health")
def health():
    return {"status": "ok", "provider": _s.llm_provider, "model": _s.llm_model}


@app.get("/schema")
def schema():
    return {"schema": _db.schema_text()}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    return AskResponse(**agent().answer(req.question, self_correct=req.self_correct))


@app.get("/")
def home():
    return FileResponse("static/index.html")
