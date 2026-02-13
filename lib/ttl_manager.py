"""
TTL Manager for OC-Memory
3-Tier memory lifecycle management (Hot/Warm/Cold)

Automatically transitions observations between tiers
based on age and configurable policies.
"""

import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

class ArchiveResult:
    """Result of an archive operation"""
    def __init__(self):
        self.hot_to_warm: int = 0
        self.warm_to_cold: int = 0
        self.errors: int = 0
        self.files_checked: int = 0

    def __repr__(self):
        return (
            f"ArchiveResult(hot_to_warm={self.hot_to_warm}, "
            f"warm_to_cold={self.warm_to_cold}, "
            f"errors={self.errors})"
        )


# =============================================================================
# TTL Manager
# =============================================================================

class TTLManager:
    """
    Manages memory lifecycle across 3 tiers:
    - Hot (0-90 days): ChromaDB + active_memory.md
    - Warm (90-365 days): Markdown archives
    - Cold (365+ days): Obsidian/Dropbox (manual approval)
    """

    def __init__(
        self,
        memory_dir: str,
        archive_dir: Optional[str] = None,
        hot_ttl_days: int = 90,
        warm_ttl_days: int = 365,
    ):
        """
        Args:
            memory_dir: Hot memory directory (OpenClaw memory)
            archive_dir: Warm archive directory
            hot_ttl_days: Days before Hot -> Warm transition
            warm_ttl_days: Days before Warm -> Cold transition
        """
        self.memory_dir = Path(memory_dir).expanduser().resolve()
        self.archive_dir = Path(
            archive_dir or str(self.memory_dir / "archive")
        ).expanduser().resolve()
        self.hot_ttl_days = hot_ttl_days
        self.warm_ttl_days = warm_ttl_days

        # Ensure directories exist
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def check_and_archive(self) -> ArchiveResult:
        """
        Check all files and archive as needed.

        Returns:
            ArchiveResult with counts
        """
        result = ArchiveResult()
        now = datetime.now()
        hot_cutoff = now - timedelta(days=self.hot_ttl_days)

        # Check Hot -> Warm
        for md_file in self.memory_dir.glob("**/*.md"):
            # Skip archive directory
            if self.archive_dir in md_file.parents or md_file.parent == self.archive_dir:
                continue

            # Skip active_memory.md (always stays in Hot)
            if md_file.name == "active_memory.md":
                continue

            result.files_checked += 1

            try:
                mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
                if mtime < hot_cutoff:
                    self._archive_to_warm(md_file)
                    result.hot_to_warm += 1
            except Exception as e:
                logger.error(f"Error checking {md_file}: {e}")
                result.errors += 1

        # Check Warm -> Cold candidates (just log, need manual approval)
        warm_cutoff = now - timedelta(days=self.warm_ttl_days)
        cold_candidates = []

        for md_file in self.archive_dir.glob("**/*.md"):
            try:
                mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
                if mtime < warm_cutoff:
                    cold_candidates.append(md_file)
            except Exception as e:
                logger.error(f"Error checking archive {md_file}: {e}")

        if cold_candidates:
            logger.info(
                f"{len(cold_candidates)} files eligible for Cold archive "
                f"(requires manual approval)"
            )

        if result.hot_to_warm > 0:
            logger.info(
                f"Archived {result.hot_to_warm} files from Hot to Warm "
                f"(checked {result.files_checked} files)"
            )

        return result

    def _archive_to_warm(self, file_path: Path) -> Path:
        """
        Move a file from Hot to Warm tier.

        Args:
            file_path: Path to file to archive

        Returns:
            Path to archived file
        """
        # Create year/month subdirectory
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        target_dir = self.archive_dir / mtime.strftime("%Y") / mtime.strftime("%m")
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / file_path.name

        # Handle conflicts
        if target_file.exists():
            stem = file_path.stem
            suffix = file_path.suffix
            timestamp = mtime.strftime("%Y%m%d_%H%M%S")
            target_file = target_dir / f"{stem}_{timestamp}{suffix}"

        shutil.move(str(file_path), str(target_file))
        logger.info(f"Archived to Warm: {file_path.name} -> {target_file}")
        return target_file

    def archive_to_cold(
        self,
        file_path: Path,
        cold_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        Move a file from Warm to Cold tier (requires explicit call).

        Args:
            file_path: Path to file to archive
            cold_dir: Cold storage directory (e.g., Obsidian vault)

        Returns:
            Path to cold-archived file, or None if cold_dir not configured
        """
        if cold_dir is None:
            logger.warning("Cold storage directory not configured")
            return None

        cold_dir = Path(cold_dir).expanduser().resolve()
        cold_dir.mkdir(parents=True, exist_ok=True)

        target_file = cold_dir / file_path.name

        # Handle conflicts
        if target_file.exists():
            stem = file_path.stem
            suffix = file_path.suffix
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_file = cold_dir / f"{stem}_{timestamp}{suffix}"

        shutil.move(str(file_path), str(target_file))
        logger.info(f"Archived to Cold: {file_path.name} -> {target_file}")
        return target_file

    def get_cold_candidates(self) -> List[Path]:
        """Get files eligible for Cold archive"""
        cutoff = datetime.now() - timedelta(days=self.warm_ttl_days)
        candidates = []

        for md_file in self.archive_dir.glob("**/*.md"):
            try:
                mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
                if mtime < cutoff:
                    candidates.append(md_file)
            except Exception:
                continue

        return candidates

    def get_stats(self) -> Dict[str, Any]:
        """Get tier statistics"""
        hot_files = list(self.memory_dir.glob("**/*.md"))
        # Exclude archive files from hot count
        hot_files = [
            f for f in hot_files
            if self.archive_dir not in f.parents and f.parent != self.archive_dir
        ]
        warm_files = list(self.archive_dir.glob("**/*.md"))

        hot_size = sum(f.stat().st_size for f in hot_files if f.exists())
        warm_size = sum(f.stat().st_size for f in warm_files if f.exists())

        return {
            'hot': {
                'files': len(hot_files),
                'size_bytes': hot_size,
            },
            'warm': {
                'files': len(warm_files),
                'size_bytes': warm_size,
            },
            'hot_ttl_days': self.hot_ttl_days,
            'warm_ttl_days': self.warm_ttl_days,
        }


def create_ttl_manager(config: Dict[str, Any]) -> TTLManager:
    """Create a TTLManager from config dictionary"""
    memory_config = config.get('memory', {})
    hot_memory_config = config.get('hot_memory', {})

    return TTLManager(
        memory_dir=memory_config.get('dir', '~/.openclaw/workspace/memory'),
        hot_ttl_days=hot_memory_config.get('ttl_days', 90),
    )
