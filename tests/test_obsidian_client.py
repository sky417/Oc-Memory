"""Tests for lib/obsidian_client.py"""

import pytest
from pathlib import Path

from lib.obsidian_client import ObsidianClient, ObsidianNote, create_obsidian_client


class TestObsidianNote:
    def test_to_markdown_basic(self):
        note = ObsidianNote(title="Test Note", content="Hello world")
        md = note.to_markdown()
        assert "---" in md
        assert "# Test Note" in md
        assert "Hello world" in md
        assert "source: oc-memory" in md

    def test_to_markdown_with_tags(self):
        note = ObsidianNote(title="Tagged", content="body", tags=["a", "b"])
        md = note.to_markdown()
        assert "- a" in md
        assert "- b" in md

    def test_to_markdown_with_metadata(self):
        note = ObsidianNote(title="Meta", content="body", metadata={"tier": "cold"})
        md = note.to_markdown()
        assert "tier: cold" in md


class TestObsidianClient:
    def test_init_creates_vault(self, temp_dir):
        vault = temp_dir / "vault"
        client = ObsidianClient(vault_path=str(vault))
        assert vault.exists()

    def test_create_note(self, temp_dir):
        client = ObsidianClient(vault_path=str(temp_dir))
        path = client.create_note(title="Test", content="Some content")
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "# Test" in text
        assert "Some content" in text

    def test_create_note_conflict(self, temp_dir):
        client = ObsidianClient(vault_path=str(temp_dir))
        p1 = client.create_note(title="Same", content="First")
        p2 = client.create_note(title="Same", content="Second")
        assert p1 != p2
        assert p1.exists()
        assert p2.exists()

    def test_create_archive_note(self, temp_dir):
        # Create a source file
        src = temp_dir / "source.md"
        src.write_text("# Archive Me\nOld content", encoding="utf-8")

        vault = temp_dir / "vault"
        client = ObsidianClient(vault_path=str(vault))
        path = client.create_archive_note(src)
        assert path.exists()
        assert "Archive Me" in path.read_text(encoding="utf-8")

    def test_create_archive_note_missing_source(self, temp_dir):
        client = ObsidianClient(vault_path=str(temp_dir))
        with pytest.raises(FileNotFoundError):
            client.create_archive_note(Path("/nonexistent/file.md"))

    def test_search_notes(self, temp_dir):
        client = ObsidianClient(vault_path=str(temp_dir))
        client.create_note(title="Alpha", content="ChromaDB is great")
        client.create_note(title="Beta", content="No match here")

        results = client.search_notes("ChromaDB")
        assert len(results) == 1
        assert results[0]['title'] == "Alpha"
        assert "ChromaDB" in results[0]['snippet']

    def test_search_notes_empty(self, temp_dir):
        client = ObsidianClient(vault_path=str(temp_dir))
        results = client.search_notes("nonexistent")
        assert results == []

    def test_get_note(self, temp_dir):
        client = ObsidianClient(vault_path=str(temp_dir))
        path = client.create_note(title="Read Me", content="Details here")

        note = client.get_note(str(path))
        assert note is not None
        assert note['title'] == "Read Me"
        assert "Details here" in note['content']

    def test_get_note_not_found(self, temp_dir):
        client = ObsidianClient(vault_path=str(temp_dir))
        assert client.get_note("nonexistent.md") is None

    def test_list_notes(self, temp_dir):
        client = ObsidianClient(vault_path=str(temp_dir))
        client.create_note(title="Note1", content="a")
        client.create_note(title="Note2", content="b")

        notes = client.list_notes()
        assert len(notes) == 2
        titles = [n['title'] for n in notes]
        assert "Note1" in titles
        assert "Note2" in titles

    def test_list_notes_empty(self, temp_dir):
        client = ObsidianClient(vault_path=str(temp_dir))
        assert client.list_notes() == []

    def test_get_stats(self, temp_dir):
        client = ObsidianClient(vault_path=str(temp_dir))
        client.create_note(title="Stats", content="body")

        stats = client.get_stats()
        assert stats['total_notes'] == 1
        assert stats['total_size_bytes'] > 0

    def test_get_stats_empty(self, temp_dir):
        client = ObsidianClient(vault_path=str(temp_dir))
        stats = client.get_stats()
        assert stats['total_notes'] == 0

    def test_sanitize_filename(self):
        assert ObsidianClient._sanitize_filename("hello/world") == "hello_world"
        assert ObsidianClient._sanitize_filename('a<b>c:d"e') == "a_b_c_d_e"
        assert ObsidianClient._sanitize_filename("normal") == "normal"

    def test_parse_frontmatter(self):
        raw = '---\ntitle: "Test"\nsource: oc-memory\n---\n\nContent here'
        fm, content = ObsidianClient._parse_frontmatter(raw)
        assert fm['title'] == 'Test'
        assert fm['source'] == 'oc-memory'
        assert 'Content here' in content

    def test_parse_frontmatter_none(self):
        raw = "Just content, no frontmatter"
        fm, content = ObsidianClient._parse_frontmatter(raw)
        assert fm == {}
        assert content == raw


class TestCreateObsidianClient:
    def test_disabled(self):
        client = create_obsidian_client({'obsidian': {'enabled': False}})
        assert client is None

    def test_enabled(self, temp_dir):
        config = {
            'obsidian': {
                'enabled': True,
                'vault_path': str(temp_dir / 'vault'),
            }
        }
        client = create_obsidian_client(config)
        assert client is not None

    def test_not_configured(self):
        assert create_obsidian_client({}) is None
