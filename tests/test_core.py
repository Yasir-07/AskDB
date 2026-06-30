from app.agent import Agent
from app.db import is_safe
from app.llm import LLMResult
from app.load_data import infer_type, sanitize


# ---------- safety guard (pure function) ----------
def test_blocks_writes():
    for bad in ["DROP TABLE customers", "DELETE FROM orders",
                "INSERT INTO products VALUES (9)", "SELECT 1; DROP TABLE x",
                "update customers set name='x'"]:
        assert is_safe(bad) is False


def test_allows_reads():
    assert is_safe("SELECT * FROM customers")
    assert is_safe("WITH t AS (SELECT 1) SELECT * FROM t")


# ---------- CSV type inference (pure functions) ----------
def test_infer_type():
    assert infer_type(["1", "2", "3"]) == "INTEGER"
    assert infer_type(["1.5", "2", ""]) == "NUMERIC"
    assert infer_type(["Alice", "Bob"]) == "TEXT"
    assert infer_type(["", ""]) == "TEXT"


def test_sanitize():
    assert sanitize("First Name!") == "first_name"
    assert sanitize("2024 total") == "c_2024_total"


# ---------- self-correction loop (fake AI + fake DB) ----------
class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, system, user, max_tokens=400):
        text = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return LLMResult(text=text, input_tokens=10, output_tokens=10, latency_s=0.0)


class FakeDB:
    """Pretends a query with the word 'nope' is broken, anything else works."""
    def schema_text(self):
        return "customers(id integer, name text)"

    def run_select(self, sql, limit=50):
        if "nope" in sql.lower():
            return False, "SQL error: relation \"nope\" does not exist"
        return True, {"columns": ["name"], "rows": [["Alice"]]}


def test_first_try_succeeds():
    agent = Agent(FakeDB(), FakeLLM(["SELECT name FROM customers"]))
    r = agent.answer("names")
    assert r["success"] and r["attempts"] == 1 and r["self_corrected"] is False


def test_recovers_after_bad_query():
    agent = Agent(FakeDB(), FakeLLM(["SELECT * FROM nope", "SELECT name FROM customers"]))
    r = agent.answer("names")
    assert r["success"] is True and r["attempts"] == 2 and r["self_corrected"] is True


def test_loop_off_does_not_retry():
    agent = Agent(FakeDB(), FakeLLM(["SELECT * FROM nope", "SELECT name FROM customers"]))
    r = agent.answer("names", self_correct=False)
    assert r["success"] is False and r["attempts"] == 1
