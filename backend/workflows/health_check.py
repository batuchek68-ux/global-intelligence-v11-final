from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.storage import ensure_dirs


def main() -> None:
    ensure_dirs()
    checks = {
        "python": sys.version.split()[0],
        "openai_api_key": bool(os.getenv("OPENAI_API_KEY")),
        "bing_search_key": bool(os.getenv("BING_SEARCH_KEY")),
        "wechat_webhook_url": bool(os.getenv("WECHAT_WEBHOOK_URL")),
        "root": str(ROOT),
    }
    for key, value in checks.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
