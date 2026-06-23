import json
from collections import Counter

STOPWORDS = {"the","is","and","to","of","in","for","on","a","an"}

def main():

    with open("data/clean_news.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    words = []

    for item in data:
        words += item["title"].split()

    words = [
        w for w in words
        if w not in STOPWORDS and len(w) > 2
    ]

    counter = Counter(words)

    top = counter.most_common(20)

    with open("data/trends.json", "w", encoding="utf-8") as f:
        json.dump(top, f, indent=2)

    print("[OK] trends generated")

if __name__ == "__main__":
    main()
