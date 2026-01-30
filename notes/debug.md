# Debug Trail

## Bug: False SUPPORTED on negation

Found a tricky bug in Q03. The claim said headnotes "may be cited" but the evidence said "Do not cite headnotes" - yet the system marked it SUPPORTED.

### What happened

The claim:
```
Headnotes may be cited as a substitute for reading the judgment text.
```

Got matched to this evidence:
```
Do not cite headnotes as a substitute for reading the judgment text. 
```

Problem was the word overlap was high enough (headnotes, cite, substitute, judgment, text) that it passed the 40% threshold. But obviously they mean opposite things.

### The fix

Added detection for prohibition patterns like "do not", "must not", etc. If the evidence has these patterns but the claim doesn't have negation, we return NOT_SUPPORTED.

```python
prohibition_patterns = [r'\bdo not\b', r'\bmust not\b', r'\bshould not\b', ...]
ev_prohibits = any(re.search(p, ev_low) for p in prohibition_patterns)

if ev_prohibits and not claim_negated and overlap_pct >= 0.3:
    return "NOT_SUPPORTED"
```

Also added check for numeric mismatches (eg "7 days" vs "3 days").

### Result

Before: 8 false SUPPORTED cases
After: fixed those, now correctly marking as NOT_SUPPORTED

Similar bugs fixed:
- Q01: "7 working days" vs "3 working days" 
- Q02: "allows external AI" vs "prohibited"
- Q10: "may input confidential data" vs "must not input"
