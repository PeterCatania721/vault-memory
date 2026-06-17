from pathlib import Path

from vault_memory_mcp.obsidian import chunk_text, keyword_search, list_notes, read_note, write_note

from conftest import FIXTURE_IGNORE, FIXTURES, fixture_note_count


def test_list_notes():
    notes = list_notes(FIXTURES, FIXTURE_IGNORE)
    assert "project-alpha.md" in notes
    assert len(notes) == fixture_note_count()


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


def test_write_note_roundtrip(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    write_note(vault, "notes/new.md", "# Hello\n\nBody")
    note = read_note(vault, "notes/new.md")
    assert note.title == "new"
    assert "Hello" in note.content


def test_list_notes_respects_ignore(tmp_path: Path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian" / "cache.md").write_text("skip")
    (vault / "keep.md").write_text("keep")
    notes = list_notes(vault, [".obsidian/**"])
    assert notes == ["keep.md"]