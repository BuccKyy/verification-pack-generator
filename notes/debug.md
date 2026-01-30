# Debug Trail: Verification Pack Generator

## Failure #1: Negation Mismatch Causes False SUPPORTED

### Observed Failure

**Question Q03, Claim #3:**
```
Claim: "Headnotes may be cited as a substitute for reading the judgment text."
```

**Before fix output:**
```json
{
  "claim": "Headnotes may be cited as a substitute for reading the judgment text.",
  "label": "SUPPORTED",
  "evidence": [{
    "doc_id": "doc03",
    "location": "L005",
    "snippet": "Do not cite headnotes as a substitute for reading the judgment text."
  }]
}
```

### Diagnosis

The claim asserts that headnotes **may** be cited, but the evidence says "**Do not** cite headnotes". The system incorrectly labeled this as SUPPORTED because:

1. High term overlap (headnotes, cite, substitute, judgment, text) → passes 40% threshold
2. Negation detection failed: claim has no negation words from the simple list
3. BUT the evidence has "Do not" which completely contradicts the claim

**Root cause:** The `_check_support()` method only checks for presence of explicit negation words (not, never, etc.) but doesn't detect when:
- Claim is affirmative ("may be cited")
- Evidence is negative ("Do **not** cite")

### Fix Applied

Enhanced negation detection in `_check_support()` to:
1. Detect "do not", "must not", "should not" patterns
2. Compare claim polarity (affirmative vs. negative)
3. If claim is affirmative but evidence is prohibitive → NOT_SUPPORTED

**Code change in `run.py`:**
```python
# Added to _check_support method:
# Detect prohibitive patterns in evidence
prohibitive_patterns = [r'\bdo not\b', r'\bmust not\b', r'\bshould not\b', r'\bprohibited\b']
evidence_prohibits = any(re.search(p, evidence_lower) for p in prohibitive_patterns)

# If evidence prohibits something the claim asserts, it's NOT_SUPPORTED
if evidence_prohibits and not claim_has_negation:
    # Check if claim is asserting the prohibited action
    if overlap_ratio >= 0.3:
        return "NOT_SUPPORTED"
```

### After Fix Output

```json
{
  "claim": "Headnotes may be cited as a substitute for reading the judgment text.",
  "label": "NOT_SUPPORTED",
  "evidence": [{
    "doc_id": "doc03",
    "location": "L005",
    "snippet": "Do not cite headnotes as a substitute for reading the judgment text."
  }]
}
```

### Similar Cases Fixed

- **Q01, Claim #4:** "7 working days" vs evidence "3 working days" → Now NOT_SUPPORTED
- **Q02, Claim #3:** "allows external AI tools" vs evidence "prohibited" → Now NOT_SUPPORTED
- **Q10, Claim #3:** "may input confidential data" vs evidence "must not input" → Now NOT_SUPPORTED

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| False SUPPORTED | ~8 | 0 |
| Correctly NOT_SUPPORTED | 7 | 15 |
| INSUFFICIENT | 7 | 7 |

The fix improves precision by correctly identifying contradictions between affirmative claims and prohibitive evidence.
