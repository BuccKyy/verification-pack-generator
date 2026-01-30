# Veracia Track A Homework — Verification Pack Generator (Mock Public Dataset)

This package contains:
- `docs/` : 10 mock public documents with line-numbered text (L001, L002, ...).
- `questions.jsonl` : 20 questions.
- `claims.jsonl` : 3–5 claims per question to verify.

## Your task
Build a runnable script that outputs `outputs/packs.jsonl` (one JSON object per question), containing:
- an `answer`
- a claim → evidence map
- pinpoint citations using `doc_id` + line ranges (e.g. `doc03:L001-L004`)
- a retrieval log (top candidates + scores)
- labels: `SUPPORTED`, `NOT_SUPPORTED`, `INSUFFICIENT`

Correctness > coverage. If evidence does not directly support a claim, label `INSUFFICIENT` rather than guessing.

## Run command (required)
Your repo must run with ONE command:

python run.py --docs ./docs --questions ./questions.jsonl --claims ./claims.jsonl --out ./outputs

## Output schema (example)
{
  "qid": "Q01",
  "answer": "...",
  "claims": [
    {
      "claim": "...",
      "label": "SUPPORTED|NOT_SUPPORTED|INSUFFICIENT",
      "evidence": [
        {"doc_id":"doc01", "location":"L002-L004", "snippet":"..."}
      ]
    }
  ],
  "retrieval_log": {
    "top_k": 10,
    "candidates": [{"doc_id":"doc01","score":0.82,"location":"L001-L005"}]
  }
}

## Anti-ChatGPT constraint (required)
Include:
1) `notes/debug.md` describing one real failure you observed + diagnosis + fix + before/after excerpt.
2) At least 3 git commits:
   - `init: baseline pipeline`
   - `fix: ...` (must match `notes/debug.md`)
   - `eval: ...` (adds a check or metric)

Good luck.
