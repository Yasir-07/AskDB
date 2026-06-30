# AskDB — ask your database questions in plain English

Type a normal question like *"which customers are from Canada?"* and this tool
turns it into a database query, **runs it**, and shows you the answer. If the
query it wrote is wrong, it **reads the error and fixes itself**, then tries
again.

## What's actually in here (in plain words)

- **A sample database** so you have data to ask about immediately.
- **An "agent"** = the part that writes a query, runs it, and *repairs its own
  mistakes* if the query fails. This is the impressive bit.
- **A safety lock** = it will only ever *read* data. Any attempt to change or
  delete data is blocked two different ways. (Real concern: you never want an AI
  running `DELETE` on a real database.)
- **A scorer** = runs a list of test questions and tells you what % it gets
  right — once with the self-fixing turned off, once with it on — so you can
  prove the self-fixing helps.
- **A simple web page** to try it by hand.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt


# try it by hand
uvicorn app.main:app --reload
# open http://localhost:8000  and ask a question

# score it
python -m eval.run_eval eval/eval_set.jsonl

# run the tests (no AI key needed)
pytest -q
```