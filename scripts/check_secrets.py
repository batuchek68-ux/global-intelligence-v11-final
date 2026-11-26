# -*- coding: utf-8 -*-
"""扫描 git 跟踪的文本文件，发现疑似明文密钥则 exit 1。供 pre-commit 与 CI 复用。"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PATTERNS = [
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(r"xoxb-[A-Za-z0-9-]{20,}"),
    re.compile(r"BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY"),
]

# 与 system_integrity.check_secret_leaks 保持一致：二进制/数据文件不当文本扫。
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".pdf",
    ".zip", ".gz", ".tar", ".7z", ".exe", ".msi", ".dll", ".so",
    ".pyc", ".pyo", ".db", ".db-wal", ".db-shm", ".sqlite",
    ".sqlite3", ".bin", ".parquet", ".onnx", ".wasm", ".woff", ".woff2",
}


def tracked_files():
    out = subprocess.check_output(
        ["git", "ls-files"], cwd=str(ROOT), text=True, encoding="utf-8", errors="replace"
    )
    return [ROOT / line for line in out.splitlines() if line.strip()]


def main():
    files = tracked_files()
    hits = []
    for path in files:
        if not path.is_file() or path.suffix.lower() in BINARY_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if any(p.search(text) for p in PATTERNS):
            hits.append(path.relative_to(ROOT).as_posix())
    if hits:
        print("BLOCKED: possible plaintext secrets in:")
        for h in hits:
            print("  " + h)
        return 1
    print("secret scan clean: %d tracked files" % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
