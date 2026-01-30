#!/usr/bin/env python3
"""
Verification Pack Generator
===========================
Generates JSON verification packs for claims using document evidence.

Usage:
    python run.py --docs ./docs --questions ./questions.jsonl --claims ./claims.jsonl --out ./outputs
"""

import argparse
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

from rank_bm25 import BM25Okapi


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class DocumentLine:
    """A single line from a document."""
    doc_id: str
    line_num: str  # e.g., "L001"
    content: str
    
    @property
    def location(self) -> str:
        return self.line_num


@dataclass
class Evidence:
    """Evidence supporting or refuting a claim."""
    doc_id: str
    location: str
    snippet: str


@dataclass
class ClaimResult:
    """Result of verifying a single claim."""
    claim: str
    label: str  # SUPPORTED, NOT_SUPPORTED, INSUFFICIENT
    evidence: List[Evidence] = field(default_factory=list)


@dataclass
class RetrievalCandidate:
    """A candidate document for retrieval."""
    doc_id: str
    score: float
    location: str


# ============================================================================
# Document Loader
# ============================================================================

class DocumentLoader:
    """Loads and parses documents with L-prefixed lines."""
    
    def __init__(self, docs_dir: str):
        self.docs_dir = Path(docs_dir)
        self.documents: Dict[str, List[DocumentLine]] = {}
        self.all_lines: List[DocumentLine] = []
        
    def load_all(self) -> None:
        """Load all documents from the directory."""
        for doc_path in sorted(self.docs_dir.glob("*.txt")):
            doc_id = doc_path.stem  # e.g., "doc01"
            self.documents[doc_id] = self._parse_document(doc_id, doc_path)
            self.all_lines.extend(self.documents[doc_id])
        
        print(f"[DocumentLoader] Loaded {len(self.documents)} documents, {len(self.all_lines)} lines total")
    
    def _parse_document(self, doc_id: str, path: Path) -> List[DocumentLine]:
        """Parse a document and extract L-prefixed lines."""
        lines = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Match lines like "L001: content..."
                match = re.match(r'^(L\d+):\s*(.+)$', line)
                if match:
                    line_num, content = match.groups()
                    lines.append(DocumentLine(doc_id, line_num, content))
        return lines
    
    def get_line(self, doc_id: str, line_num: str) -> Optional[DocumentLine]:
        """Get a specific line from a document."""
        if doc_id in self.documents:
            for line in self.documents[doc_id]:
                if line.line_num == line_num:
                    return line
        return None


# ============================================================================
# BM25 Retriever
# ============================================================================

class BM25Retriever:
    """BM25-based text retrieval system."""
    
    def __init__(self, lines: List[DocumentLine]):
        self.lines = lines
        self.corpus = [self._tokenize(line.content) for line in lines]
        self.bm25 = BM25Okapi(self.corpus)
        print(f"[BM25Retriever] Indexed {len(lines)} lines")
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization: lowercase and split on non-alphanumeric."""
        return re.findall(r'\w+', text.lower())
    
    def search(self, query: str, top_k: int = 10) -> List[Tuple[DocumentLine, float]]:
        """Search for relevant lines."""
        query_tokens = self._tokenize(query)
        scores = self.bm25.get_scores(query_tokens)
        
        # Get top-k indices
        scored_indices = sorted(
            enumerate(scores), 
            key=lambda x: x[1], 
            reverse=True
        )[:top_k]
        
        results = []
        for idx, score in scored_indices:
            if score > 0:  # Only include non-zero scores
                results.append((self.lines[idx], score))
        
        return results


# ============================================================================
# Claim Verifier
# ============================================================================

class ClaimVerifier:
    """Verifies claims against retrieved evidence."""
    
    # Keywords that often indicate negation or contradiction
    NEGATION_WORDS = {'not', 'never', 'no', 'cannot', 'prohibited', 'must not', 'should not'}
    
    # Similarity threshold for considering evidence as supporting
    SUPPORT_THRESHOLD = 3.0  # BM25 score threshold
    
    def __init__(self, retriever: BM25Retriever, loader: DocumentLoader):
        self.retriever = retriever
        self.loader = loader
    
    def verify_claim(self, claim: str, question: str) -> Tuple[ClaimResult, List[RetrievalCandidate]]:
        """Verify a single claim and return result with retrieval candidates."""
        # Search using combined query
        query = f"{question} {claim}"
        candidates = self.retriever.search(query, top_k=10)
        
        # Build retrieval log
        retrieval_candidates = [
            RetrievalCandidate(
                doc_id=line.doc_id,
                score=round(score, 2),
                location=line.location
            )
            for line, score in candidates
        ]
        
        # Find supporting evidence
        evidence_list = []
        label = "INSUFFICIENT"
        
        for line, score in candidates:
            if score < self.SUPPORT_THRESHOLD:
                continue
                
            # Check if the line content supports the claim
            support_type = self._check_support(claim, line.content)
            
            if support_type == "SUPPORTED":
                evidence_list.append(Evidence(
                    doc_id=line.doc_id,
                    location=line.location,
                    snippet=line.content
                ))
                label = "SUPPORTED"
                break  # Found supporting evidence
            elif support_type == "NOT_SUPPORTED":
                evidence_list.append(Evidence(
                    doc_id=line.doc_id,
                    location=line.location,
                    snippet=line.content
                ))
                label = "NOT_SUPPORTED"
                break  # Found contradicting evidence
        
        return (
            ClaimResult(claim=claim, label=label, evidence=evidence_list),
            retrieval_candidates
        )
    
    def _check_support(self, claim: str, evidence: str) -> str:
        """
        Check if evidence supports, contradicts, or is insufficient for the claim.
        
        Returns: "SUPPORTED", "NOT_SUPPORTED", or "INSUFFICIENT"
        """
        claim_lower = claim.lower()
        evidence_lower = evidence.lower()
        
        # Extract key terms from claim
        claim_terms = set(re.findall(r'\w+', claim_lower))
        evidence_terms = set(re.findall(r'\w+', evidence_lower))
        
        # Calculate term overlap
        overlap = claim_terms & evidence_terms
        overlap_ratio = len(overlap) / len(claim_terms) if claim_terms else 0
        
        # Check for explicit negation mismatch
        claim_has_negation = any(neg in claim_lower for neg in self.NEGATION_WORDS)
        evidence_has_negation = any(neg in evidence_lower for neg in self.NEGATION_WORDS)
        
        # Enhanced: Detect prohibitive patterns in evidence
        prohibitive_patterns = [r'\bdo not\b', r'\bmust not\b', r'\bshould not\b', 
                                r'\bprohibited\b', r'\bnever\b', r'\bcannot\b']
        evidence_prohibits = any(re.search(p, evidence_lower) for p in prohibitive_patterns)
        
        # Enhanced: Check if claim is affirmative but evidence prohibits
        if evidence_prohibits and not claim_has_negation and overlap_ratio >= 0.3:
            return "NOT_SUPPORTED"
        
        # Check for numeric mismatches (e.g., "7 days" vs "3 days")
        claim_numbers = re.findall(r'\b(\d+)\s*(?:working\s+)?days?\b', claim_lower)
        evidence_numbers = re.findall(r'\b(\d+)\s*(?:working\s+)?days?\b', evidence_lower)
        if claim_numbers and evidence_numbers:
            if claim_numbers[0] != evidence_numbers[0]:
                return "NOT_SUPPORTED"
        
        # If high overlap and matching polarity -> SUPPORTED
        if overlap_ratio >= 0.4:
            # Check for polarity conflict
            if claim_has_negation != evidence_has_negation:
                # One has negation, other doesn't - likely contradiction
                return "NOT_SUPPORTED"
            return "SUPPORTED"
        
        # Check for explicit contradiction keywords
        if self._is_contradiction(claim_lower, evidence_lower):
            return "NOT_SUPPORTED"
        
        return "INSUFFICIENT"
    
    def _is_contradiction(self, claim: str, evidence: str) -> bool:
        """Check if evidence explicitly contradicts the claim."""
        # Pattern pairs that indicate contradiction
        contradiction_pairs = [
            (r'must\s+be\s+submitted.*?(\d+)', r'must\s+be\s+submitted.*?(\d+)'),  # Different numbers
            (r'allowed', r'prohibited'),
            (r'required', r'not required'),
            (r'can\s+be', r'cannot\s+be'),
        ]
        
        for claim_pattern, evidence_pattern in contradiction_pairs:
            claim_match = re.search(claim_pattern, claim)
            evidence_match = re.search(evidence_pattern, evidence)
            if claim_match and evidence_match:
                if claim_match.group() != evidence_match.group():
                    return True
        
        return False


# ============================================================================
# Pack Generator
# ============================================================================

class PackGenerator:
    """Generates the final verification packs."""
    
    def __init__(self, loader: DocumentLoader, retriever: BM25Retriever, verifier: ClaimVerifier):
        self.loader = loader
        self.retriever = retriever
        self.verifier = verifier
    
    def generate_pack(self, qid: str, question: str, claims: List[str]) -> dict:
        """Generate a verification pack for a single question."""
        claim_results = []
        all_candidates = []
        
        for claim in claims:
            result, candidates = self.verifier.verify_claim(claim, question)
            claim_results.append(result)
            all_candidates.extend(candidates)
        
        # Generate answer from supported claims
        supported_claims = [r for r in claim_results if r.label == "SUPPORTED"]
        if supported_claims:
            answer = "; ".join([r.claim for r in supported_claims])
        else:
            answer = "Insufficient evidence to provide a definitive answer."
        
        # Deduplicate candidates by (doc_id, location)
        seen = set()
        unique_candidates = []
        for c in sorted(all_candidates, key=lambda x: x.score, reverse=True):
            key = (c.doc_id, c.location)
            if key not in seen:
                seen.add(key)
                unique_candidates.append(c)
        
        return {
            "qid": qid,
            "answer": answer,
            "claims": [
                {
                    "claim": r.claim,
                    "label": r.label,
                    "evidence": [
                        {"doc_id": e.doc_id, "location": e.location, "snippet": e.snippet}
                        for e in r.evidence
                    ]
                }
                for r in claim_results
            ],
            "retrieval_log": {
                "top_k": 10,
                "candidates": [
                    {"doc_id": c.doc_id, "score": c.score, "location": c.location}
                    for c in unique_candidates[:10]
                ]
            }
        }


# ============================================================================
# Main Pipeline
# ============================================================================

def load_jsonl(path: str) -> List[dict]:
    """Load a JSONL file."""
    items = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def main():
    parser = argparse.ArgumentParser(description="Verification Pack Generator")
    parser.add_argument("--docs", required=True, help="Path to documents directory")
    parser.add_argument("--questions", required=True, help="Path to questions.jsonl")
    parser.add_argument("--claims", required=True, help="Path to claims.jsonl")
    parser.add_argument("--out", required=True, help="Output directory")
    args = parser.parse_args()
    
    # Load documents
    loader = DocumentLoader(args.docs)
    loader.load_all()
    
    # Build retriever
    retriever = BM25Retriever(loader.all_lines)
    
    # Build verifier
    verifier = ClaimVerifier(retriever, loader)
    
    # Build generator
    generator = PackGenerator(loader, retriever, verifier)
    
    # Load questions and claims
    questions = {q["qid"]: q["question"] for q in load_jsonl(args.questions)}
    claims_by_qid = {c["qid"]: c["claims"] for c in load_jsonl(args.claims)}
    
    # Generate packs
    os.makedirs(args.out, exist_ok=True)
    output_path = os.path.join(args.out, "packs.jsonl")
    
    packs = []
    for qid in sorted(questions.keys()):
        question = questions[qid]
        claims = claims_by_qid.get(qid, [])
        
        pack = generator.generate_pack(qid, question, claims)
        packs.append(pack)
        print(f"[Pipeline] Generated pack for {qid}")
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        for pack in packs:
            f.write(json.dumps(pack, ensure_ascii=False) + '\n')
    
    print(f"\n[Pipeline] Complete! Output written to {output_path}")
    print(f"[Pipeline] Total packs: {len(packs)}")
    
    # Print summary statistics
    total_claims = sum(len(p["claims"]) for p in packs)
    supported = sum(1 for p in packs for c in p["claims"] if c["label"] == "SUPPORTED")
    not_supported = sum(1 for p in packs for c in p["claims"] if c["label"] == "NOT_SUPPORTED")
    insufficient = sum(1 for p in packs for c in p["claims"] if c["label"] == "INSUFFICIENT")
    
    print(f"\n[Stats] Claims Summary:")
    print(f"  - Total claims: {total_claims}")
    print(f"  - SUPPORTED: {supported} ({100*supported/total_claims:.1f}%)")
    print(f"  - NOT_SUPPORTED: {not_supported} ({100*not_supported/total_claims:.1f}%)")
    print(f"  - INSUFFICIENT: {insufficient} ({100*insufficient/total_claims:.1f}%)")


if __name__ == "__main__":
    main()
