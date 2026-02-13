"""
Obsidian CLI Client for OC-Memory
Manages Cold memory storage in Obsidian vaults

Provides create/search/read operations on Obsidian notes
via either the obsidian-cli tool or direct file manipulation.
"""

import logging
import re
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================

class ObsidianNote:
    """Represents an Obsidian note"""

    def __init__(
        self,
        title: str,
        content: str,
        folder: str = "",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.title = title
        self.content = content
        self.folder = folder
        self.tags = tags or []
        self.metadata = metadata or {}

    def to_markdown(self) -> str:
        """Convert note to Obsidian-compatible markdown with frontmatter"""
        lines = ["---"]

        # YAML frontmatter
        lines.append(f"title: \"{self.title}\"")
        lines.append(f"created: {datetime.now().isoformat()}")
        lines.append(f"source: oc-memory")

        if self.tags:
            lines.append("tags:")
            for tag in self.tags:
                lines.append(f"  - {tag}")

        for key, value in self.metadata.items():
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"{key}: {value}")

        lines.append("---")
        lines.append("")
        lines.append(f"# {self.title}")
        lines.append("")
        lines.append(self.content)

        return "\n".join(lines)


# =============================================================================
# Obsidian Client
# =============================================================================

class ObsidianClient:
    """
    Client for interacting with Obsidian vault.
    Supports both obsidian-cli and direct file manipulation.
    """

    def __init__(
        self,
        vault_path: str,
        cli_path: Optional[str] = None,
        default_folder: str = "OC-Memory",
    ):
        """
        Args:
            vault_path: Path to Obsidian vault root
            cli_path: Path to obsidian-cli binary (auto-detected if None)
            default_folder: Default folder for OC-Memory notes
        """
        self.vault_path = Path(vault_path).expanduser().resolve()
        self.cli_path = cli_path or self._find_cli()
        self.default_folder = default_folder

        # Ensure vault directory exists
        self.vault_path.mkdir(parents=True, exist_ok=True)

    def _find_cli(self) -> Optional[str]:
        """Try to find obsidian-cli in PATH"""
        return shutil.which("obsidian-cli") or shutil.which("obsidian")

    @property
    def has_cli(self) -> bool:
        """Check if obsidian-cli is available"""
        return self.cli_path is not None

    def create_note(
        self,
        title: str,
        content: str,
        folder: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Create a new note in the Obsidian vault.

        Args:
            title: Note title
            content: Markdown content
            folder: Subfolder (uses default_folder if None)
            tags: List of tags
            metadata: Additional frontmatter metadata

        Returns:
            Path to the created note file
        """
        folder = folder or self.default_folder
        note = ObsidianNote(
            title=title,
            content=content,
            folder=folder,
            tags=tags or ["oc-memory", "cold-archive"],
            metadata=metadata or {},
        )

        # Create target directory
        target_dir = self.vault_path / folder
        target_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_title = self._sanitize_filename(title)
        note_path = target_dir / f"{safe_title}.md"

        # Handle conflicts
        if note_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            note_path = target_dir / f"{safe_title}_{timestamp}.md"

        note_path.write_text(note.to_markdown(), encoding="utf-8")
        logger.info(f"Created Obsidian note: {note_path}")
        return note_path

    def create_archive_note(
        self,
        source_file: Path,
        folder: Optional[str] = None,
    ) -> Path:
        """
        Create an archive note from an existing markdown file.

        Args:
            source_file: Source markdown file to archive
            folder: Subfolder in vault (uses default_folder/archive if None)

        Returns:
            Path to the created archive note
        """
        source_file = Path(source_file)
        if not source_file.exists():
            raise FileNotFoundError(f"Source file not found: {source_file}")

        content = source_file.read_text(encoding="utf-8")
        title = source_file.stem
        folder = folder or f"{self.default_folder}/archive"

        metadata = {
            "original_path": str(source_file),
            "archived_date": datetime.now().isoformat(),
            "tier": "cold",
        }

        return self.create_note(
            title=title,
            content=content,
            folder=folder,
            tags=["oc-memory", "cold-archive", "archived"],
            metadata=metadata,
        )

    def search_notes(
        self,
        query: str,
        folder: Optional[str] = None,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search notes in the Obsidian vault.

        Uses simple text matching (grep-like).

        Args:
            query: Search query string
            folder: Subfolder to search in (searches all if None)
            max_results: Maximum number of results

        Returns:
            List of result dicts with 'path', 'title', 'snippet'
        """
        search_dir = self.vault_path / folder if folder else self.vault_path
        if not search_dir.exists():
            return []

        results = []
        query_lower = query.lower()

        for md_file in search_dir.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                if query_lower in content.lower():
                    # Extract snippet around the match
                    snippet = self._extract_snippet(content, query)
                    title = md_file.stem

                    results.append({
                        'path': str(md_file),
                        'title': title,
                        'snippet': snippet,
                        'folder': str(md_file.parent.relative_to(self.vault_path)),
                    })

                    if len(results) >= max_results:
                        break
            except Exception as e:
                logger.debug(f"Error reading {md_file}: {e}")
                continue

        return results

    def get_note(self, note_path: str) -> Optional[Dict[str, Any]]:
        """
        Read a note from the vault.

        Args:
            note_path: Path relative to vault root, or absolute path

        Returns:
            Dict with 'title', 'content', 'frontmatter', 'path' or None
        """
        path = Path(note_path)
        if not path.is_absolute():
            path = self.vault_path / path

        if not path.exists():
            return None

        try:
            raw = path.read_text(encoding="utf-8")
            frontmatter, content = self._parse_frontmatter(raw)

            return {
                'title': path.stem,
                'content': content,
                'frontmatter': frontmatter,
                'path': str(path),
            }
        except Exception as e:
            logger.error(f"Error reading note {path}: {e}")
            return None

    def list_notes(
        self,
        folder: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """
        List notes in a folder.

        Args:
            folder: Subfolder to list (lists default folder if None)

        Returns:
            List of dicts with 'title', 'path', 'modified'
        """
        target = self.vault_path / (folder or self.default_folder)
        if not target.exists():
            return []

        notes = []
        for md_file in sorted(target.rglob("*.md")):
            mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
            notes.append({
                'title': md_file.stem,
                'path': str(md_file.relative_to(self.vault_path)),
                'modified': mtime.isoformat(),
            })

        return notes

    def get_stats(self) -> Dict[str, Any]:
        """Get vault statistics"""
        target = self.vault_path / self.default_folder
        if not target.exists():
            return {'total_notes': 0, 'total_size_bytes': 0, 'has_cli': self.has_cli}

        notes = list(target.rglob("*.md"))
        total_size = sum(f.stat().st_size for f in notes if f.exists())

        return {
            'total_notes': len(notes),
            'total_size_bytes': total_size,
            'vault_path': str(self.vault_path),
            'has_cli': self.has_cli,
        }

    # =========================================================================
    # Private helpers
    # =========================================================================

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize a string for use as a filename"""
        # Remove or replace invalid characters
        safe = re.sub(r'[<>:"/\\|?*]', '_', name)
        safe = safe.strip('. ')
        return safe[:200]  # Limit length

    @staticmethod
    def _extract_snippet(content: str, query: str, context_chars: int = 100) -> str:
        """Extract a snippet around the first match of query in content"""
        idx = content.lower().find(query.lower())
        if idx == -1:
            return content[:200]

        start = max(0, idx - context_chars)
        end = min(len(content), idx + len(query) + context_chars)

        snippet = content[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."

        return snippet

    @staticmethod
    def _parse_frontmatter(raw: str) -> tuple:
        """Parse YAML frontmatter from markdown content"""
        frontmatter = {}
        content = raw

        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1].strip()
                content = parts[2].strip()

                # Simple YAML-like parsing
                for line in fm_text.split("\n"):
                    line = line.strip()
                    if ": " in line and not line.startswith("-"):
                        key, _, value = line.partition(": ")
                        frontmatter[key.strip()] = value.strip().strip('"')

        return frontmatter, content


# =============================================================================
# Factory
# =============================================================================

def create_obsidian_client(config: Dict[str, Any]) -> Optional[ObsidianClient]:
    """Create an ObsidianClient from config dictionary"""
    obsidian_config = config.get('obsidian', {})

    if not obsidian_config.get('enabled', False):
        return None

    vault_path = obsidian_config.get('vault_path', '~/Documents/ObsidianVault')
    return ObsidianClient(vault_path=vault_path)
