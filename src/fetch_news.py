import feedparser
import json
import os

RSS_FEEDS = [
    "https://rss.cnn.com/rss/edition.rss",
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml"
]

def fetch_news():
    all_news = []

    for url in RSS_FEEDS:
        feed = feedparser.parse(url)

        for item in feed.entries[:20]:
            all_news.append({
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "source": url
            })

    os.makedirs("data", exist_ok=True)

    with open("data/raw_news.json", "w", encoding="utf-8") as f:
        json.dump(all_news, f, indent=2, ensure_ascii=False)

    print(f"[OK] fetched {len(all_news)} news")

if __name__ == "__main__":
    fetch_news()
