"""Tests for lib/memory_writer.py"""

import pytest
from pathlib import Path
from datetime import datetime

from lib.memory_writer import MemoryWriter, MemoryWriterError


class TestMemoryWriter:
    def test_init_creates_directory(self, temp_dir):
        mem_dir = temp_dir / "new_memory"
        writer = MemoryWriter(str(mem_dir))
        assert mem_dir.exists()

    def test_write_memory_entry(self, memory_dir):
        writer = MemoryWriter(str(memory_dir))
        path = writer.write_memory_entry(
            content="# Test\nContent here",
            filename="test.md",
        )
        assert path.exists()
        assert path.read_text().strip() == "# Test\nContent here"

    def test_write_with_category(self, memory_dir):
        writer = MemoryWriter(str(memory_dir))
        path = writer.write_memory_entry(
            content="# Note",
            filename="note.md",
            category="notes",
        )
        assert "notes" in str(path)
        assert path.exists()

    def test_copy_to_memory(self, memory_dir, temp_dir):
        writer = MemoryWriter(str(memory_dir))

        # Create source file
        source = temp_dir / "source.md"
        source.write_text("# Source File")

        target = writer.copy_to_memory(source)
        assert target.exists()
        assert target.read_text().startswith("# Source File")

    def test_copy_nonexistent_file(self, memory_dir, temp_dir):
        writer = MemoryWriter(str(memory_dir))
        fake = temp_dir / "nonexistent.md"
        with pytest.raises(MemoryWriterError, match="not found"):
            writer.copy_to_memory(fake)

    def test_copy_handles_conflict(self, memory_dir, temp_dir):
        writer = MemoryWriter(str(memory_dir))

        source = temp_dir / "dup.md"
        source.write_text("# Version 1")

        # Copy twice
        path1 = writer.copy_to_memory(source)
        source.write_text("# Version 2")
        path2 = writer.copy_to_memory(source)

        assert path1 != path2
        assert path1.exists()
        assert path2.exists()

    def test_add_metadata(self, memory_dir):
        writer = MemoryWriter(str(memory_dir))

        path = writer.write_memory_entry(
            content="# Test",
            filename="meta_test.md",
        )

        writer.add_metadata(path, {
            "created": "2026-01-01",
            "category": "test",
            "tags": ["unit", "test"],
        })

        content = path.read_text()
        assert content.startswith("---")
        assert "category: test" in content
        assert "- unit" in content

    def test_add_metadata_replaces_existing(self, memory_dir):
        writer = MemoryWriter(str(memory_dir))

        path = writer.write_memory_entry(
            content="# Test",
            filename="replace_meta.md",
        )

        # Add metadata twice
        writer.add_metadata(path, {"v": "1"})
        writer.add_metadata(path, {"v": "2"})

        content = path.read_text()
        assert content.count("---") == 2  # opening and closing
        assert "v: 2" in content

    def test_get_category_from_path(self, memory_dir):
        writer = MemoryWriter(str(memory_dir))

        assert writer.get_category_from_path(Path("/user/projects/foo.md")) == "projects"
        assert writer.get_category_from_path(Path("/user/notes/bar.md")) == "notes"
        assert writer.get_category_from_path(Path("/user/docs/baz.md")) == "documents"
        assert writer.get_category_from_path(Path("/user/random/qux.md")) == "general"
