import json
import sys
import time

from app.agent import Agent
from app.config import get_settings
from app.db import PostgresDatabase
from app.llm import LLMClient

PAUSE_SECONDS = 2.0   # gap between questions; raise to 6 if you still hit limits


def load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def is_correct(result: dict, expected: str) -> bool:
    if not result.get("success"):
        return False
    blob = " ".join(str(c) for row in result["rows"] for c in row).lower()
    return expected.lower() in blob


def safe_answer(agent: Agent, question: str) -> dict:
    """Never let one failed question crash the whole run."""
    try:
        return agent.answer(question, self_correct=True)
    except Exception as e:
        return {"success": False, "rows": [], "attempts": 0, "error": str(e)}


def run(path: str):
    s = get_settings()
    agent = Agent(PostgresDatabase(s.database_url), LLMClient(s), s.max_retries, s.row_limit)
    items = load(path)

    off = on = 0
    for it in items:
        q, expected = it["question"], it["expected_contains"]
        result = safe_answer(agent, q)

        ok_on = is_correct(result, expected)                       # with self-correction
        ok_off = ok_on and result.get("attempts") == 1            # right on first try

        on += ok_on
        off += ok_off
        if ok_on and not ok_off:
            mark = "OK  <-- fixed by self-correction"
        elif ok_on:
            mark = "OK "
        else:
            mark = "XX "
        print(f"{mark} {q}")
        time.sleep(PAUSE_SECONDS)

    n = len(items)
    print("=" * 60)
    print(f"Questions                    : {n}")
    print(f"Accuracy WITHOUT self-correct: {off / n:.0%}")
    print(f"Accuracy WITH self-correct   : {on / n:.0%}")
    print(f"Improvement                  : +{(on - off) / n:.0%}")
    print("=" * 60)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "eval/eval_set.jsonl")
