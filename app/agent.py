import re
from typing import Protocol


class DB(Protocol):
    def schema_text(self) -> str: ...
    def run_select(self, sql: str, limit: int = 50): ...


class LLM(Protocol):
    def complete(self, system: str, user: str, max_tokens: int = 400): ...


GEN_SYSTEM = (
    "You convert a question into ONE PostgreSQL SELECT query. "
    "Return ONLY the SQL — no explanation, no markdown fences. "
    "Use only the tables and columns listed in the schema."
)
FIX_SYSTEM = (
    "Your previous PostgreSQL query failed. Given the schema, the question, the "
    "broken query and the error, return ONE corrected SELECT query. "
    "Return ONLY the SQL — no explanation, no markdown fences."
)


def _clean(sql: str) -> str:
    sql = sql.strip()
    sql = re.sub(r"^```(?:sql)?", "", sql).strip()
    sql = re.sub(r"```$", "", sql).strip()
    return sql


class Agent:
    def __init__(self, db: DB, llm: LLM, max_retries: int = 3, row_limit: int = 50):
        self.db = db
        self.llm = llm
        self.max_retries = max_retries
        self.row_limit = row_limit

    def _generate(self, schema: str, question: str) -> str:
        user = f"Schema:\n{schema}\n\nQuestion: {question}\n\nSQL:"
        return _clean(self.llm.complete(GEN_SYSTEM, user).text)

    def _fix(self, schema: str, question: str, bad_sql: str, error: str) -> str:
        user = (f"Schema:\n{schema}\n\nQuestion: {question}\n\n"
                f"Broken query:\n{bad_sql}\n\nError:\n{error}\n\nCorrected SQL:")
        return _clean(self.llm.complete(FIX_SYSTEM, user).text)

    def answer(self, question: str, self_correct: bool = True) -> dict:
        schema = self.db.schema_text()
        sql = self._generate(schema, question)
        tries = self.max_retries if self_correct else 0
        log = []  # the trail: every query tried, and its error if it failed

        for i in range(tries + 1):
            ok, payload = self.db.run_select(sql, self.row_limit)
            log.append({"sql": sql, "ok": ok, "error": None if ok else payload})
            if ok:
                return {
                    "success": True, "sql": sql,
                    "columns": payload["columns"], "rows": payload["rows"],
                    "attempts": i + 1, "self_corrected": i > 0,
                    "attempts_log": log,
                }
            if i < tries:
                sql = self._fix(schema, question, sql, payload)

        return {
            "success": False, "sql": sql, "error": log[-1]["error"],
            "attempts": len(log), "self_corrected": len(log) > 1,
            "attempts_log": log,
        }
