from pathlib import Path

from vault_memory_mcp.obsidian import chunk_text, keyword_search, list_notes, read_note

FIXTURES = Path(__file__).parent / "fixtures" / "vault"


def test_list_notes():
    notes = list_notes(FIXTURES)
    assert "project-alpha.md" in notes
    assert len(notes) == 2


def test_read_note_wikilinks():
    note = read_note(FIXTURES, "project-alpha.md")
    assert note.title == "project-alpha"
    assert "architecture-notes" in note.wikilinks
    assert note.content_hash


def test_keyword_search():
    hits = keyword_search(FIXTURES, "Qdrant", limit=5)
    assert len(hits) == 1
    assert hits[0]["path"] == "project-alpha.md"


def test_chunk_text():
    text = "# Title\n\n" + ("word " * 200)
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    assert len(chunks) >= 2
    assert all(len(c) <= 110 for c in chunks)