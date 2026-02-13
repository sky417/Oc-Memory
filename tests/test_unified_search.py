"""Tests for lib/unified_search.py"""

import pytest
from pathlib import Path
from datetime import datetime

from lib.unified_search import UnifiedSearch, SearchResult, create_unified_search
from lib.obsidian_client import ObsidianClient


class TestSearchResult:
    def test_init(self):
        r = SearchResult(title="T", content="C", tier="hot", score=0.9)
        assert r.title == "T"
        assert r.tier == "hot"
        assert r.score == 0.9

    def test_to_dict(self):
        r = SearchResult(title="T", content="C", tier="warm", score=0.5)
        d = r.to_dict()
        assert d['title'] == "T"
        assert d['tier'] == "warm"
        assert d['score'] == 0.5

    def test_repr(self):
        r = SearchResult(title="T", content="C", tier="cold", score=0.3)
        assert "cold" in repr(r)
        assert "0.300" in repr(r)


class TestUnifiedSearchWarm:
    def test_search_warm_exact_match(self, temp_dir):
        archive = temp_dir / "archive"
        archive.mkdir()
        (archive / "note1.md").write_text("ChromaDB is a vector database", encoding="utf-8")
        (archive / "note2.md").write_text("Nothing relevant here", encoding="utf-8")

        search = UnifiedSearch(archive_dir=str(archive))
        results = search.search_warm("ChromaDB")
        assert len(results) == 1
        assert results[0].tier == "warm"
        assert results[0].score > 0

    def test_search_warm_partial_match(self, temp_dir):
        archive = temp_dir / "archive"
        archive.mkdir()
        (archive / "doc.md").write_text("Memory system with vector search", encoding="utf-8")

        search = UnifiedSearch(archive_dir=str(archive))
        results = search.search_warm("vector search")
        assert len(results) == 1

    def test_search_warm_no_match(self, temp_dir):
        archive = temp_dir / "archive"
        archive.mkdir()
        (archive / "doc.md").write_text("Unrelated content", encoding="utf-8")

        search = UnifiedSearch(archive_dir=str(archive))
        results = search.search_warm("quantum physics")
        assert len(results) == 0

    def test_search_warm_no_archive(self):
        search = UnifiedSearch(archive_dir=None)
        results = search.search_warm("test")
        assert results == []

    def test_search_warm_word_match(self, temp_dir):
        archive = temp_dir / "archive"
        archive.mkdir()
        (archive / "doc.md").write_text("The memory system is great", encoding="utf-8")

        search = UnifiedSearch(archive_dir=str(archive))
        results = search.search_warm("memory system")
        assert len(results) == 1


class TestUnifiedSearchCold:
    def test_search_cold_obsidian(self, temp_dir):
        vault = temp_dir / "vault"
        client = ObsidianClient(vault_path=str(vault))
        client.create_note(title="ColdNote", content="Cold storage test data")

        search = UnifiedSearch(obsidian_client=client)
        results = search.search_cold("Cold storage")
        assert len(results) == 1
        assert results[0].tier == "cold"
        assert results[0].source == "obsidian"

    def test_search_cold_no_clients(self):
        search = UnifiedSearch()
        results = search.search_cold("test")
        assert results == []


class TestUnifiedSearchMultiTier:
    def test_search_all_tiers(self, temp_dir):
        # Set up warm tier
        archive = temp_dir / "archive"
        archive.mkdir()
        (archive / "warm_note.md").write_text("Warm memory about testing", encoding="utf-8")

        # Set up cold tier
        vault = temp_dir / "vault"
        client = ObsidianClient(vault_path=str(vault))
        client.create_note(title="ColdNote", content="Cold testing content")

        search = UnifiedSearch(
            archive_dir=str(archive),
            obsidian_client=client,
        )

        # Search across warm + cold (skip hot since no MemoryStore)
        results = search.search("testing", tiers=['warm', 'cold'])
        assert len(results) >= 1

        # Results should be sorted by score (descending)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_specific_tier(self, temp_dir):
        archive = temp_dir / "archive"
        archive.mkdir()
        (archive / "note.md").write_text("Some content", encoding="utf-8")

        search = UnifiedSearch(archive_dir=str(archive))
        results = search.search("content", tiers=['warm'])
        assert all(r.tier == 'warm' for r in results)

    def test_search_unknown_tier(self, temp_dir):
        search = UnifiedSearch()
        # Should not raise, just skip unknown tier
        results = search.search("test", tiers=['unknown'])
        assert results == []

    def test_search_respects_n_results(self, temp_dir):
        archive = temp_dir / "archive"
        archive.mkdir()
        for i in range(10):
            (archive / f"note_{i}.md").write_text(f"Content about topic {i}", encoding="utf-8")

        search = UnifiedSearch(archive_dir=str(archive))
        results = search.search("Content", n_results=3)
        assert len(results) <= 3


class TestUnifiedSearchStats:
    def test_stats_empty(self):
        search = UnifiedSearch()
        stats = search.get_stats()
        assert stats['hot_configured'] is False
        assert stats['warm_configured'] is False
        assert stats['cold_obsidian_configured'] is False
        assert stats['tiers_available'] == []

    def test_stats_with_warm(self, temp_dir):
        archive = temp_dir / "archive"
        archive.mkdir()
        search = UnifiedSearch(archive_dir=str(archive))
        stats = search.get_stats()
        assert 'warm' in stats['tiers_available']

    def test_stats_with_obsidian(self, temp_dir):
        vault = temp_dir / "vault"
        client = ObsidianClient(vault_path=str(vault))
        search = UnifiedSearch(obsidian_client=client)
        stats = search.get_stats()
        assert 'cold' in stats['tiers_available']


class TestCreateUnifiedSearch:
    def test_create_from_config(self, temp_dir):
        config = {
            'memory': {
                'dir': str(temp_dir / 'mem'),
                'archive_dir': str(temp_dir / 'archive'),
            }
        }
        search = create_unified_search(config)
        assert search.archive_dir is not None

    def test_create_with_defaults(self):
        search = create_unified_search({})
        assert search is not None

    def test_extract_snippet(self):
        content = "The quick brown fox jumps over the lazy dog"
        snippet = UnifiedSearch._extract_snippet(content, "fox", context_chars=10)
        assert "fox" in snippet
