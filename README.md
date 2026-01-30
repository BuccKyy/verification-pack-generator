# ⚖️ Verification Pack Generator

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Completed-success?style=for-the-badge)

> **Veracia Track A Homework** - An automated system for verifying legal claims against document evidence with pinpoint accuracy.

---

## 📖 Overview

This tool automatically verifies claims by cross-referencing them against a corpus of legal documents. It uses **BM25 retrieval** to find relevant context and a robust logic engine to determine if a claim is `SUPPORTED`, `NOT_SUPPORTED`, or `INSUFFICIENT`.

**Core Philosophy:** *Correctness > Coverage*. We'd rather say "I don't know" (`INSUFFICIENT`) than guess wrong.

---

## 🚀 Quick Start

Get up and running in seconds.

### 1. Setup
```bash
# Install dependencies
pip install -r requirements.txt
```

### 2. Run Verification
This single command runs the entire pipeline:

```bash
python run.py --docs ./docs --questions ./questions.jsonl --claims ./claims.jsonl --out ./outputs
```

> **Artifacts Produced:** Check `outputs/packs.jsonl` for the results!

---

## 🛠️ Engineering Insights (Short Note)

### 🧠 What I Implemented
I built a specialized **BM25-based verification pipeline** designed for legal text precision. The system processes 64 unique claims across 20 questions, extracting **pinpoint citations** (document ID + specific line numbers).

Key Technical Features:
*   **Conservative Abstention:** The system defaults to `INSUFFICIENT` if evidence is weak.
*   **3-Way Labeling:** Distinguishes between `SUPPORTED`, `NOT_SUPPORTED` (contradiction), and `INSUFFICIENT`.

### 🐞 Failure Modes & Fixes

| Failure Type | Observation | Status |
| :--- | :--- | :--- |
| **Negation Mismatch** | Claim *"may be cited"* matched evidence *"Do not cite"*. High keyword overlap caused a false positive `SUPPORTED`. | ✅ **FIXED** (Added prohibitive pattern detection) |
| **Synonym Gap** | BM25 missed the link between *"written approval"* and *"must obtain consent"*. | ⚠️ **OBSERVED** (Needs semantic search) |

### 🔮 Future Roadmap
*   **Semantic Search:** Integrate `Sentence-BERT` to bridge the synonym gap.
*   **Multi-line Citations:** Logic to capture evidence spanning multiple paragraphs.
*   **Confidence Scoring:** Expose internal confidence metrics to the API response.

---

## 📂 Project Structure

```
.
├── 📄 run.py             # Main pipeline (The Brain)
├── 📄 eval.py            # Quality assurance script
├── 📄 requirements.txt   # Dependencies
├── 📂 docs/              # Corpus of documents
├── 📂 notes/             # Debug trail & Fix documentation
└── 📂 outputs/           # generated results
```

---

## 🧪 Quality Assurance

We take correctness seriously. A dedicated evaluation script is included to metrics:

```bash
python eval.py
```

**Current Benchmark Results:**
- ✅ **76%** Supported
- ✅ **12%** Not Supported (Contradictions correctly caught)
- ✅ **11%** Insufficient (Correctly abstained)

---

<p align="center">
  Made with ❤️ by [Your Name/Handle]
</p>
