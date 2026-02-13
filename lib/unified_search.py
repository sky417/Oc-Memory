"""
Unified Search Engine for OC-Memory
Searches across all memory tiers (Hot/Warm/Cold)

Aggregates results from ChromaDB (Hot), Markdown archives (Warm),
and Obsidian/Dropbox (Cold) into a ranked result set.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Search Result
# =============================================================================

class SearchResult:
    """A single search result from any tier"""

    def __init__(
        self,
        title: str,
        content: str,
        tier: str,
        score: float = 0.0,
        source: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.title = title
        self.content = content
        self.tier = tier  # 'hot', 'warm', 'cold'
        self.score = score
        self.source = source
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'title': self.title,
            'content': self.content,
            'tier': self.tier,
            'score': self.score,
            'source': self.source,
            'metadata': self.metadata,
        }

    def __repr__(self):
        return f"SearchResult(title='{self.title}', tier='{self.tier}', score={self.score:.3f})"


# =============================================================================
# Unified Search Engine
# =============================================================================

class UnifiedSearch:
    """
    Searches across all memory tiers:
    1. Hot: ChromaDB semantic search
    2. Warm: Markdown file grep
    3. Cold: Obsidian vault search
    """

    def __init__(
        self,
        memory_store=None,
        archive_dir: Optional[str] = None,
        obsidian_client=None,
        dropbox_sync=None,
    ):
        """
        Args:
            memory_store: MemoryStore instance (Hot tier)
            archive_dir: Warm archive directory path
            obsidian_client: ObsidianClient instance (Cold tier)
            dropbox_sync: DropboxSync instance (Cold tier, optional)
        """
        self.memory_store = memory_store
        self.archive_dir = Path(archive_dir).expanduser().resolve() if archive_dir else None
        self.obsidian_client = obsidian_client
        self.dropbox_sync = dropbox_sync

    def search(
        self,
        query: str,
        tiers: Optional[List[str]] = None,
        n_results: int = 10,
        priority: Optional[str] = None,
    ) -> List[SearchResult]:
        """
        Search across specified memory tiers.

        Args:
            query: Search query string
            tiers: List of tiers to search ('hot', 'warm', 'cold'); all if None
            n_results: Maximum results per tier
            priority: Filter by priority ('high', 'medium', 'low')

        Returns:
            List of SearchResult objects, ranked by score
        """
        if tiers is None:
            tiers = ['hot', 'warm', 'cold']

        all_results = []

        for tier in tiers:
            try:
                if tier == 'hot':
                    results = self._search_hot(query, n_results, priority)
                elif tier == 'warm':
                    results = self._search_warm(query, n_results)
                elif tier == 'cold':
                    results = self._search_cold(query, n_results)
                else:
                    logger.warning(f"Unknown tier: {tier}")
                    continue

                all_results.extend(results)
            except Exception as e:
                logger.error(f"Error searching {tier} tier: {e}")

        # Sort by score (descending)
        all_results.sort(key=lambda r: r.score, reverse=True)

        # Limit total results
        return all_results[:n_results]

    def search_hot(
        self,
        query: str,
        n_results: int = 5,
        priority: Optional[str] = None,
    ) -> List[SearchResult]:
        """Search Hot tier only (ChromaDB)"""
        return self._search_hot(query, n_results, priority)

    def search_warm(self, query: str, n_results: int = 5) -> List[SearchResult]:
        """Search Warm tier only (archives)"""
        return self._search_warm(query, n_results)

    def search_cold(self, query: str, n_results: int = 5) -> List[SearchResult]:
        """Search Cold tier only (Obsidian/Dropbox)"""
        return self._search_cold(query, n_results)

    # =========================================================================
    # Tier-specific search implementations
    # =========================================================================

    def _search_hot(
        self,
        query: str,
        n_results: int,
        priority: Optional[str] = None,
    ) -> List[SearchResult]:
        """Search Hot tier via ChromaDB semantic search"""
        if self.memory_store is None:
            return []

        where = None
        if priority:
            where = {"priority": priority}

        try:
            results = self.memory_store.search(
                query=query,
                n_results=n_results,
                where=where,
            )
        except Exception as e:
            logger.error(f"ChromaDB search failed: {e}")
            return []

        search_results = []
        for item in results:
            # ChromaDB distance: 0 = identical, 2 = opposite
            # Convert to score: 1.0 = best, 0.0 = worst
            distance = item.get('distance', 1.0)
            score = max(0.0, 1.0 - (distance / 2.0))

            search_results.append(SearchResult(
                title=item.get('id', ''),
                content=item.get('content', ''),
                tier='hot',
                score=score,
                source='chromadb',
                metadata=item.get('metadata', {}),
            ))

        return search_results

    def _search_warm(self, query: str, n_results: int) -> List[SearchResult]:
        """Search Warm tier via markdown file grep"""
        if self.archive_dir is None or not self.archive_dir.exists():
            return []

        results = []
        query_lower = query.lower()
        query_words = query_lower.split()

        for md_file in self.archive_dir.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                content_lower = content.lower()

                # Calculate relevance score based on word matches
                if query_lower not in content_lower:
                    # Check individual words
                    word_matches = sum(1 for w in query_words if w in content_lower)
                    if word_matches == 0:
                        continue
                    score = word_matches / len(query_words) * 0.5  # partial match
                else:
                    # Exact query match
                    count = content_lower.count(query_lower)
                    score = min(0.9, 0.5 + count * 0.1)  # cap at 0.9

                # Extract snippet
                snippet = self._extract_snippet(content, query)

                results.append(SearchResult(
                    title=md_file.stem,
                    content=snippet,
                    tier='warm',
                    score=score,
                    source=str(md_file),
                    metadata={
                        'path': str(md_file),
                        'modified': datetime.fromtimestamp(
                            md_file.stat().st_mtime
                        ).isoformat(),
                    },
                ))

                if len(results) >= n_results:
                    break
            except Exception as e:
                logger.debug(f"Error reading {md_file}: {e}")

        # Sort warm results by score
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:n_results]

    def _search_cold(self, query: str, n_results: int) -> List[SearchResult]:
        """Search Cold tier via Obsidian and/or Dropbox"""
        results = []

        # Search Obsidian vault
        if self.obsidian_client is not None:
            try:
                obsidian_results = self.obsidian_client.search_notes(
                    query=query,
                    max_results=n_results,
                )
                for item in obsidian_results:
                    results.append(SearchResult(
                        title=item.get('title', ''),
                        content=item.get('snippet', ''),
                        tier='cold',
                        score=0.4,  # Cold tier gets lower base score
                        source='obsidian',
                        metadata={
                            'path': item.get('path', ''),
                            'folder': item.get('folder', ''),
                        },
                    ))
            except Exception as e:
                logger.error(f"Obsidian search failed: {e}")

        # Search Dropbox
        if self.dropbox_sync is not None and self.dropbox_sync.is_configured:
            try:
                dropbox_results = self.dropbox_sync.search(
                    query=query,
                    max_results=n_results,
                )
                for item in dropbox_results:
                    results.append(SearchResult(
                        title=item.get('name', ''),
                        content='',  # Content not available from search
                        tier='cold',
                        score=0.3,  # Dropbox results get lower score
                        source='dropbox',
                        metadata={
                            'path': item.get('path', ''),
                            'modified': str(item.get('modified', '')),
                        },
                    ))
            except Exception as e:
                logger.error(f"Dropbox search failed: {e}")

        return results[:n_results]

    # =========================================================================
    # Helpers
    # =========================================================================

    @staticmethod
    def _extract_snippet(content: str, query: str, context_chars: int = 150) -> str:
        """Extract a snippet around the first match"""
        idx = content.lower().find(query.lower())
        if idx == -1:
            return content[:300]

        start = max(0, idx - context_chars)
        end = min(len(content), idx + len(query) + context_chars)

        snippet = content[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet

    def get_stats(self) -> Dict[str, Any]:
        """Get search engine statistics"""
        stats = {
            'tiers_available': [],
            'hot_configured': self.memory_store is not None,
            'warm_configured': self.archive_dir is not None and self.archive_dir.exists(),
            'cold_obsidian_configured': self.obsidian_client is not None,
            'cold_dropbox_configured': (
                self.dropbox_sync is not None and self.dropbox_sync.is_configured
            ),
        }

        if stats['hot_configured']:
            stats['tiers_available'].append('hot')
        if stats['warm_configured']:
            stats['tiers_available'].append('warm')
        if stats['cold_obsidian_configured'] or stats['cold_dropbox_configured']:
            stats['tiers_available'].append('cold')

        return stats


# =============================================================================
# Factory
# =============================================================================

def create_unified_search(
    config: Dict[str, Any],
    memory_store=None,
    obsidian_client=None,
    dropbox_sync=None,
) -> UnifiedSearch:
    """
    Create a UnifiedSearch from config dictionary.

    Args:
        config: Configuration dict
        memory_store: Optional MemoryStore instance
        obsidian_client: Optional ObsidianClient instance
        dropbox_sync: Optional DropboxSync instance
    """
    memory_config = config.get('memory', {})
    archive_dir = memory_config.get('archive_dir')

    if archive_dir is None:
        mem_dir = memory_config.get('dir', '~/.openclaw/workspace/memory')
        archive_dir = str(Path(mem_dir).expanduser() / 'archive')

    return UnifiedSearch(
        memory_store=memory_store,
        archive_dir=archive_dir,
        obsidian_client=obsidian_client,
        dropbox_sync=dropbox_sync,
    )
