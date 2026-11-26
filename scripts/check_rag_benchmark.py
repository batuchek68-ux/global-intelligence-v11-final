# -*- coding: utf-8 -*-
"""CI gate: run the RAG gold-set benchmark and enforce quality thresholds."""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from backend.services.rag_benchmark_service import evaluate  # noqa: E402


def main() -> int:
    acc_min = float(os.getenv("RAG_ACC_MIN", "0.75"))
    cite_min = float(os.getenv("RAG_CITATION_MIN", "0.95"))
    report = evaluate()
    acc = float(report["accuracy"])
    cite = float(report["citation_accuracy"])
    total = int(report["total"])
    hits = int(report["hits"])
    report_path = REPO / "backend" / "reports" / "benchmark" / "rag_quality.json"

    print(
        "RAG_BENCHMARK total=%d hits=%d accuracy=%.4f (min=%.2f) citation=%.4f (min=%.2f)"
        % (total, hits, acc, acc_min, cite, cite_min)
    )
    print("REPORT=%s" % report_path)

    failures = []
    if acc < acc_min:
        failures.append("accuracy %.4f < %.2f" % (acc, acc_min))
    if cite < cite_min:
        failures.append("citation %.4f < %.2f" % (cite, cite_min))
    if failures:
        print("FAILED: " + "; ".join(failures))
        return 1
    print("PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
