from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    self_correct: bool = True


class Attempt(BaseModel):
    sql: str
    ok: bool
    error: str | None = None


class AskResponse(BaseModel):
    success: bool
    sql: str
    columns: list[str] = []
    rows: list[list] = []
    attempts: int
    self_corrected: bool
    error: str | None = None
    attempts_log: list[Attempt] = []
