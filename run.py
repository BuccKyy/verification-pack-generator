#!/usr/bin/env python3
"""
Verification Pack Generator for Veracia Track A

Generates JSON verification packs that map claims to supporting evidence
from a corpus of legal documents.
"""

import argparse
import json
import os
import re
from pathlib import Path
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi


# --- Data structures ---

@dataclass
class DocLine:
    """Single line from a document with its metadata."""
    doc_id: str
    line_num: str   # e.g. "L001"
    content: str
    
    @property
    def location(self):
        return self.line_num


@dataclass
class Evidence:
    doc_id: str
    location: str
    snippet: str


@dataclass 
class ClaimResult:
    claim: str
    label: str  # SUPPORTED | NOT_SUPPORTED | INSUFFICIENT
    evidence: list = field(default_factory=list)


@dataclass
class Candidate:
    doc_id: str
    score: float
    location: str


# --- Document loading ---

class DocumentLoader:
    """Loads documents and extracts L-prefixed content lines."""
    
    def __init__(self, docs_dir):
        self.docs_dir = Path(docs_dir)
        self.documents = {}
        self.all_lines = []
        
    def load_all(self):
        for doc_path in sorted(self.docs_dir.glob("*.txt")):
            doc_id = doc_path.stem
            lines = self._parse_doc(doc_id, doc_path)
            self.documents[doc_id] = lines
            self.all_lines.extend(lines)
        
        print(f"Loaded {len(self.documents)} docs, {len(self.all_lines)} lines")
    
    def _parse_doc(self, doc_id, path):
        """Extract lines matching pattern L001: content..."""
        lines = []
        with open(path, 'r', encoding='utf-8') as f:
            for raw_line in f:
                raw_line = raw_line.strip()
                match = re.match(r'^(L\d+):\s*(.+)$', raw_line)
                if match:
                    line_num, content = match.groups()
                    lines.append(DocLine(doc_id, line_num, content))
        return lines


# --- BM25 retrieval ---

class Retriever:
    """Simple BM25-based retriever."""
    
    def __init__(self, lines):
        self.lines = lines
        # Build corpus for BM25
        corpus = [self._tokenize(ln.content) for ln in lines]
        self.bm25 = BM25Okapi(corpus)
        print(f"Indexed {len(lines)} lines for retrieval")
    
    def _tokenize(self, text):
        # Basic tokenization - could use nltk or spacy but this works fine
        return re.findall(r'\w+', text.lower())
    
    def search(self, query, top_k=10):
        """Return top-k (DocLine, score) pairs."""
        tokens = self._tokenize(query)
        scores = self.bm25.get_scores(tokens)
        
        # Sort by score descending
        ranked = sorted(enumerate(scores), key=lambda x: -x[1])[:top_k]
        
        results = []
        for idx, score in ranked:
            if score > 0:
                results.append((self.lines[idx], score))
        return results


# --- Claim verification ---

class ClaimVerifier:
    """Checks if retrieved evidence supports/contradicts claims."""
    
    # Words indicating negation
    # TODO: might want to expand this list based on testing
    NEGATION_WORDS = {'not', 'never', 'no', 'cannot', 'prohibited'}
    
    # BM25 score threshold - below this we consider it weak match
    # FIXME: 3.0 works ok for this dataset but may need tuning
    MIN_SCORE = 3.0
    
    def __init__(self, retriever):
        self.retriever = retriever
    
    def verify(self, claim, question):
        """Verify claim and return (ClaimResult, list of candidates)."""
        
        # Combine question + claim for better retrieval
        query = f"{question} {claim}"
        hits = self.retriever.search(query, top_k=10)
        
        # Build candidate list for logging
        candidates = [
            Candidate(doc_id=ln.doc_id, score=round(sc, 2), location=ln.location)
            for ln, sc in hits
        ]
        
        # Try to find supporting or contradicting evidence
        for line, score in hits:
            if score < self.MIN_SCORE:
                continue
            
            verdict = self._check_support(claim, line.content)
            
            if verdict in ("SUPPORTED", "NOT_SUPPORTED"):
                ev = Evidence(doc_id=line.doc_id, location=line.location, 
                             snippet=line.content)
                return ClaimResult(claim, verdict, [ev]), candidates
        
        # No strong evidence found
        return ClaimResult(claim, "INSUFFICIENT", []), candidates
    
    def _check_support(self, claim, evidence):
        """
        Compare claim against evidence text.
        Returns: SUPPORTED, NOT_SUPPORTED, or INSUFFICIENT
        """
        claim_low = claim.lower()
        ev_low = evidence.lower()
        
        # Get word sets
        claim_words = set(re.findall(r'\w+', claim_low))
        ev_words = set(re.findall(r'\w+', ev_low))
        
        # Calculate overlap
        overlap = claim_words & ev_words
        overlap_pct = len(overlap) / len(claim_words) if claim_words else 0
        
        # Check for negation mismatch
        claim_negated = any(neg in claim_low for neg in self.NEGATION_WORDS)
        ev_negated = any(neg in ev_low for neg in self.NEGATION_WORDS)
        
        # Handle "do not", "must not" patterns - this fixed a nasty bug
        # where "may cite" was matching "Do not cite" as SUPPORTED
        prohibition_patterns = [r'\bdo not\b', r'\bmust not\b', r'\bshould not\b', 
                               r'\bprohibited\b', r'\bnever\b', r'\bcannot\b']
        ev_prohibits = any(re.search(p, ev_low) for p in prohibition_patterns)
        
        if ev_prohibits and not claim_negated and overlap_pct >= 0.3:
            return "NOT_SUPPORTED"
        
        # Check for numeric mismatch (e.g. "7 days" vs "3 days")
        claim_nums = re.findall(r'\b(\d+)\s*(?:working\s+)?days?\b', claim_low)
        ev_nums = re.findall(r'\b(\d+)\s*(?:working\s+)?days?\b', ev_low)
        if claim_nums and ev_nums and claim_nums[0] != ev_nums[0]:
            return "NOT_SUPPORTED"
        
        # High overlap with matching polarity = supported
        if overlap_pct >= 0.4:
            if claim_negated != ev_negated:
                return "NOT_SUPPORTED"
            return "SUPPORTED"
        
        return "INSUFFICIENT"


# --- Helpers ---

def load_jsonl(path):
    """Load a JSONL file into a list of dicts."""
    items = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    return items


def make_pack(qid, question, claims, verifier):
    """Generates verification pack for a single question."""
    results = []
    all_candidates = []
    
    for claim in claims:
        result, candidates = verifier.verify(claim, question)
        results.append(result)
        all_candidates.extend(candidates)
    
    # Build answer from supported claims
    supported = [r.claim for r in results if r.label == "SUPPORTED"]
    answer = "; ".join(supported) if supported else "Insufficient evidence to answer."
    
    # Deduplicate candidates
    seen = set()
    unique = []
    # Sort by score for better quality
    for c in sorted(all_candidates, key=lambda x: -x.score):
        key = (c.doc_id, c.location)
        if key not in seen:
            seen.add(key)
            unique.append(c)
    
    return {
        "qid": qid,
        "answer": answer,
        "claims": [
            {
                "claim": r.claim,
                "label": r.label,
                "evidence": [{"doc_id": e.doc_id, "location": e.location, 
                              "snippet": e.snippet} for e in r.evidence]
            }
            for r in results
        ],
        "retrieval_log": {
            "top_k": 10,
            "candidates": [{"doc_id": c.doc_id, "score": c.score, 
                           "location": c.location} for c in unique[:10]]
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Generate verification packs")
    parser.add_argument("--docs", required=True, help="Documents directory")
    parser.add_argument("--questions", required=True, help="questions.jsonl path")
    parser.add_argument("--claims", required=True, help="claims.jsonl path")
    parser.add_argument("--out", required=True, help="Output directory")
    args = parser.parse_args()
    
    # Setup pipeline
    loader = DocumentLoader(args.docs)
    loader.load_all()
    
    retriever = Retriever(loader.all_lines)
    verifier = ClaimVerifier(retriever)
    
    # Load input data
    questions = {q["qid"]: q["question"] for q in load_jsonl(args.questions)}
    claims_map = {c["qid"]: c["claims"] for c in load_jsonl(args.claims)}
    
    # Generate packs
    os.makedirs(args.out, exist_ok=True)
    out_path = os.path.join(args.out, "packs.jsonl")
    
    packs = []
    for qid in sorted(questions.keys()):
        # Merged PackGenerator into a single function here
        # Feels more like a script than an app now
        pack = make_pack(qid, questions[qid], claims_map.get(qid, []), verifier)
        packs.append(pack)
        print(f"Generated {qid}")
    
    # Write output
    with open(out_path, 'w', encoding='utf-8') as f:
        for p in packs:
            f.write(json.dumps(p, ensure_ascii=False) + '\n')
    
    print(f"\nDone! Wrote {len(packs)} packs to {out_path}")
    
    # Quick stats
    total = sum(len(p["claims"]) for p in packs)
    sup = sum(1 for p in packs for c in p["claims"] if c["label"] == "SUPPORTED")
    notsup = sum(1 for p in packs for c in p["claims"] if c["label"] == "NOT_SUPPORTED")
    insuf = total - sup - notsup
    
    print(f"\nStats: {total} claims total")
    print(f"  SUPPORTED: {sup} ({100*sup//total}%)")
    print(f"  NOT_SUPPORTED: {notsup} ({100*notsup//total}%)")
    print(f"  INSUFFICIENT: {insuf} ({100*insuf//total}%)")


if __name__ == "__main__":
    main()
