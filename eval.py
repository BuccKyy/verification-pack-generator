#!/usr/bin/env python3
"""
Quick evaluation script for verification packs.
Prints basic stats and quality checks.
"""

import json
import sys
from pathlib import Path


def evaluate(packs_path):
    # Load packs
    packs = []
    with open(packs_path) as f:
        for line in f:
            if line.strip():
                packs.append(json.loads(line))
    
    # Count labels
    total = 0
    counts = {"SUPPORTED": 0, "NOT_SUPPORTED": 0, "INSUFFICIENT": 0}
    with_evidence = 0
    
    for pack in packs:
        for claim in pack["claims"]:
            total += 1
            counts[claim["label"]] += 1
            if claim.get("evidence"):
                with_evidence += 1
    
    # Print report
    print("=" * 50)
    print("Verification Pack Evaluation")
    print("=" * 50)
    
    print(f"\nLabel Distribution ({total} claims):")
    for label, count in counts.items():
        pct = 100 * count / total if total else 0
        print(f"  {label}: {count} ({pct:.0f}%)")
    
    print(f"\nEvidence Coverage:")
    print(f"  Claims with evidence: {with_evidence}/{total}")
    print(f"  Packs with candidates: {sum(1 for p in packs if p.get('retrieval_log', {}).get('candidates'))}/{len(packs)}")
    
    # Warn on potential issues
    print(f"\nQuality Checks:")
    if counts["INSUFFICIENT"] < total * 0.05:
        print("  [!] Low INSUFFICIENT rate - may be over-confident")
    elif counts["SUPPORTED"] > total * 0.9:
        print("  [!] Very high SUPPORTED rate - double check negation handling")
    else:
        print("  [OK] All checks passed")
    
    print("=" * 50)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "./outputs/packs.jsonl"
    
    if not Path(path).exists():
        print(f"File not found: {path}")
        sys.exit(1)
    
    evaluate(path)
