import json
import re
import os

def clean(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff ]", "", text)
    return text

def main():

    with open("data/raw_news.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    seen = set()
    cleaned = []

    for item in data:
        title = item.get("title", "")

        if not title:
            continue

        ctitle = clean(title)

        if ctitle in seen:
            continue

        seen.add(ctitle)

        cleaned.append({
            "title": ctitle,
            "source": item.get("source", "")
        })

    os.makedirs("data", exist_ok=True)

    with open("data/clean_news.json", "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)

    print(f"[OK] cleaned {len(cleaned)}")

if __name__ == "__main__":
    main()
