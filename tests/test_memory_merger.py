"""Tests for lib/memory_merger.py"""

import pytest
from datetime import datetime
from pathlib import Path

from lib.memory_merger import MemoryMerger, estimate_tokens, create_merger
from lib.observer import Observation


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_single_word(self):
        tokens = estimate_tokens("hello")
        assert tokens == 1  # 1 word * 1.3 = 1.3 -> 1

    def test_sentence(self):
        text = "The quick brown fox jumps over the lazy dog"
        tokens = estimate_tokens(text)
        assert 9 <= tokens <= 15  # ~9 words * 1.3 = ~11.7

    def test_long_text(self):
        text = " ".join(["word"] * 1000)
        tokens = estimate_tokens(text)
        assert 1200 <= tokens <= 1400  # ~1000 * 1.3


class TestMemoryMerger:
    def test_init_creates_directory(self, temp_dir):
        mem_dir = temp_dir / "new_mem"
        merger = MemoryMerger(str(mem_dir))
        assert mem_dir.exists()

    def test_load_empty(self, memory_dir):
        merger = MemoryMerger(str(memory_dir))
        sections = merger.load()
        assert len(sections) == 5
        for entries in sections.values():
            assert entries == []

    def test_save_and_load(self, memory_dir):
        merger = MemoryMerger(str(memory_dir))
        sections = merger.load()
        sections["Current Context"] = ["Working on OC-Memory project"]
        sections["Observations Log"] = ["- Fact 1", "- Fact 2"]
        merger.save(sections)

        # Reload and verify
        loaded = merger.load()
        assert "Working on OC-Memory project" in loaded["Current Context"]
        assert len(loaded["Observations Log"]) == 2

    def test_save_creates_file(self, memory_dir):
        merger = MemoryMerger(str(memory_dir))
        sections = {s: [] for s in merger.SECTIONS}
        path = merger.save(sections)
        assert path.exists()
        content = path.read_text()
        assert "# Active Memory" in content
        assert "## Current Context" in content

    def test_add_observations(self, memory_dir):
        merger = MemoryMerger(str(memory_dir))
        observations = [
            Observation(
                id="obs_001",
                timestamp=datetime.now(),
                priority="high",
                category="decision",
                content="Use ChromaDB",
            ),
            Observation(
                id="obs_002",
                timestamp=datetime.now(),
                priority="low",
                category="preference",
                content="Dark mode preferred",
            ),
        ]
        added = merger.add_observations(observations)
        assert added == 2

        # Verify sections
        sections = merger.load()
        assert any("ChromaDB" in line for line in sections["Critical Decisions"])
        assert any("Dark mode" in line for line in sections["User Constraints"])

    def test_add_observations_empty(self, memory_dir):
        merger = MemoryMerger(str(memory_dir))
        assert merger.add_observations([]) == 0

    def test_add_context(self, memory_dir):
        merger = MemoryMerger(str(memory_dir))
        merger.add_context("Currently implementing Phase 2")
        sections = merger.load()
        assert "Phase 2" in sections["Current Context"][0]

    def test_add_entry(self, memory_dir):
        merger = MemoryMerger(str(memory_dir))
        result = merger.add_entry("Completed Tasks", "- Implemented FileWatcher")
        assert result is True
        sections = merger.load()
        assert any("FileWatcher" in line for line in sections["Completed Tasks"])

    def test_add_entry_invalid_section(self, memory_dir):
        merger = MemoryMerger(str(memory_dir))
        result = merger.add_entry("Nonexistent Section", "test")
        assert result is False

    def test_get_token_count(self, memory_dir):
        merger = MemoryMerger(str(memory_dir))
        # Empty file
        assert merger.get_token_count() == 0

        # After adding content
        sections = merger.load()
        sections["Observations Log"] = ["- " + "word " * 100]
        merger.save(sections)
        assert merger.get_token_count() > 0

    def test_clear_section(self, memory_dir):
        merger = MemoryMerger(str(memory_dir))
        merger.add_entry("Observations Log", "- Test entry")
        merger.clear_section("Observations Log")
        sections = merger.load()
        # After clearing, save writes "_No entries yet._" as placeholder
        assert not any("Test entry" in line for line in sections["Observations Log"])

    def test_category_to_section_mapping(self, memory_dir):
        merger = MemoryMerger(str(memory_dir))
        assert merger._map_category_to_section("preference") == "User Constraints"
        assert merger._map_category_to_section("constraint") == "User Constraints"
        assert merger._map_category_to_section("decision") == "Critical Decisions"
        assert merger._map_category_to_section("task") == "Completed Tasks"
        assert merger._map_category_to_section("fact") == "Observations Log"
        assert merger._map_category_to_section("unknown") == "Observations Log"

    def test_token_limit_trimming(self, memory_dir):
        merger = MemoryMerger(str(memory_dir), max_tokens=50)

        # Add many observations to exceed limit
        observations = []
        for i in range(20):
            observations.append(Observation(
                id=f"obs_{i:03d}",
                timestamp=datetime.now(),
                priority="low",
                category="fact",
                content=f"Observation number {i} with some extra words to consume tokens",
            ))

        merger.add_observations(observations)

        # Token count should be within limit (or close)
        token_count = merger.get_token_count()
        # Allow some overhead for headers
        assert token_count < 200  # reasonable bound given small max_tokens


class TestCreateMerger:
    def test_create_from_config(self, temp_dir):
        config = {
            'memory': {
                'dir': str(temp_dir / 'mem'),
                'max_tokens': 20000,
            }
        }
        merger = create_merger(config)
        assert merger.max_tokens == 20000

    def test_create_with_defaults(self, temp_dir):
        merger = create_merger({})
        assert merger.max_tokens == 30000
