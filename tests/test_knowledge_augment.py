from __future__ import annotations

from backend.services import knowledge_ingest_service as kis
from backend.services.knowledge_augment_service import augment_brief


CONTENT = "# Daily Intelligence Brief\n\nOriginal rules-based content.\n"


def _fake_result(n: int = 1) -> dict:
    results = []
    for i in range(n):
        results.append({
            "text": f"Retrieved evidence chunk {i + 1} about customs clearance.",
            "metadata": {
                "source": "wiki",
                "title": f"note-{i + 1}",
                "path": f"F:/Documents/Obsidian Vault/wiki/note-{i + 1}.md",
                "chunk": i,
            },
            "distance": 0.1 + i,
        })
    return {"ok": True, "results": results}


def test_augment_brief_appends_evidence(monkeypatch):
    monkeypatch.setattr(kis, "query", lambda text, n=5: _fake_result(1))

    new_content, source = augment_brief(CONTENT, "Kazakhstan customs")

    assert source == "rag"
    assert "## Local Knowledge Evidence" in new_content
    assert "Source: wiki" in new_content
    assert "Title: note-1" in new_content
    assert "Path: F:/Documents/Obsidian Vault/wiki/note-1.md" in new_content
    assert "Retrieved evidence chunk 1" in new_content
    assert "Original rules-based content." in new_content


def test_augment_brief_respects_n(monkeypatch):
    monkeypatch.setattr(kis, "query", lambda text, n=5: _fake_result(4))

    new_content, source = augment_brief(CONTENT, "customs", n=2)

    assert source == "rag"
    assert "Retrieved evidence chunk 1" in new_content
    assert "Retrieved evidence chunk 2" in new_content
    assert "Retrieved evidence chunk 3" not in new_content


def test_augment_brief_falls_back_on_no_results(monkeypatch):
    monkeypatch.setattr(kis, "query", lambda text, n=5: {"ok": True, "results": []})

    new_content, source = augment_brief(CONTENT, "nothing indexed")

    assert source == "rules"
    assert new_content == CONTENT
    assert "## Local Knowledge Evidence" not in new_content


def test_augment_brief_falls_back_on_failed_query(monkeypatch):
    def broken_query(text, n=5):
        raise RuntimeError("index unavailable")

    monkeypatch.setattr(kis, "query", broken_query)

    new_content, source = augment_brief(CONTENT, "anything")

    assert source == "rules"
    assert new_content == CONTENT
