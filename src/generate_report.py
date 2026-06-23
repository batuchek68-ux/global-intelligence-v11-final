import json
import os
from datetime import datetime

def main():

    with open("data/trends.json", "r") as f:
        trends = json.load(f)

    dashboard = {
        "keywords": trends,
        "topics": [
            {"name": k, "count": v}
            for k, v in trends[:10]
        ],
        "updated_at": str(datetime.now())
    }

    os.makedirs("output", exist_ok=True)

    with open("output/dashboard.json", "w") as f:
        json.dump(dashboard, f, indent=2)

    print("[OK] dashboard generated")

if __name__ == "__main__":
    main()
