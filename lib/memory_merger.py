"""
Memory Merger for OC-Memory
Manages active_memory.md generation and section-based updates

Merges observations into a structured memory file that OpenClaw
automatically indexes and uses for context.
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Approximate tokens per word ratio
TOKENS_PER_WORD = 1.3


# =============================================================================
# Token Estimation
# =============================================================================

def estimate_tokens(text: str) -> int:
    """Estimate token count from text (approximate)"""
    if not text:
        return 0
    words = len(text.split())
    return int(words * TOKENS_PER_WORD)


# =============================================================================
# Memory Merger
# =============================================================================

class MemoryMerger:
    """
    Manages the active_memory.md file.
    Organizes observations into sections and enforces token limits.
    """

    # Section headers in order
    SECTIONS = [
        "Current Context",
        "Observations Log",
        "User Constraints",
        "Completed Tasks",
        "Critical Decisions",
    ]

    def __init__(
        self,
        memory_dir: str,
        filename: str = "active_memory.md",
        max_tokens: int = 30000,
    ):
        """
        Args:
            memory_dir: OpenClaw memory directory
            filename: Memory file name
            max_tokens: Maximum token limit for the file
        """
        self.memory_dir = Path(memory_dir).expanduser().resolve()
        self.memory_file = self.memory_dir / filename
        self.max_tokens = max_tokens

        # Ensure directory exists
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def get_memory_file(self) -> Path:
        """Get path to active memory file"""
        return self.memory_file

    def load(self) -> Dict[str, List[str]]:
        """
        Load and parse the current memory file into sections.

        Returns:
            Dict mapping section names to lists of content lines
        """
        sections: Dict[str, List[str]] = {s: [] for s in self.SECTIONS}

        if not self.memory_file.exists():
            return sections

        try:
            content = self.memory_file.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to read memory file: {e}")
            return sections

        current_section = None

        for line in content.split('\n'):
            # Check if line is a section header
            header_match = re.match(r'^## (.+)$', line.strip())
            if header_match:
                header_name = header_match.group(1).strip()
                if header_name in sections:
                    current_section = header_name
                continue

            # Add line to current section
            if current_section and line.strip():
                sections[current_section].append(line)

        return sections

    def save(self, sections: Dict[str, List[str]]) -> Path:
        """
        Save sections to the memory file.

        Args:
            sections: Dict mapping section names to content lines

        Returns:
            Path to saved file
        """
        lines = [
            "# Active Memory",
            f"<!-- Updated: {datetime.now().isoformat()} -->",
            f"<!-- Token estimate: {self._estimate_section_tokens(sections)} -->",
            "",
        ]

        for section_name in self.SECTIONS:
            lines.append(f"## {section_name}")
            lines.append("")

            section_lines = sections.get(section_name, [])
            if section_lines:
                lines.extend(section_lines)
            else:
                lines.append("_No entries yet._")
            lines.append("")

        content = '\n'.join(lines)

        try:
            self.memory_file.write_text(content, encoding='utf-8')
            logger.info(f"Memory file saved: {self.memory_file}")
            return self.memory_file
        except Exception as e:
            logger.error(f"Failed to save memory file: {e}")
            raise

    def add_observations(self, observations: list) -> int:
        """
        Add observations to the memory file.

        Args:
            observations: List of Observation objects (from observer.py)

        Returns:
            Number of observations added
        """
        if not observations:
            return 0

        sections = self.load()
        added = 0

        for obs in observations:
            md_line = obs.to_markdown()
            section = self._map_category_to_section(obs.category)

            # Check token limit before adding
            sections[section].insert(0, md_line)  # newest first
            if self._estimate_section_tokens(sections) > self.max_tokens:
                # Remove oldest entries from Observations Log first
                sections[section].pop(0)  # undo
                self._trim_to_fit(sections)
                # Try again after trimming
                if self._estimate_section_tokens(sections) < self.max_tokens:
                    sections[section].insert(0, md_line)
                    added += 1
                else:
                    logger.warning("Token limit reached, skipping observation")
            else:
                added += 1

        if added > 0:
            self.save(sections)
            logger.info(f"Added {added} observations to memory")

        return added

    def add_context(self, context: str) -> None:
        """
        Update the Current Context section.

        Args:
            context: New context text
        """
        sections = self.load()
        sections["Current Context"] = [context]
        self.save(sections)

    def add_entry(self, section: str, entry: str) -> bool:
        """
        Add a single entry to a specific section.

        Args:
            section: Section name
            entry: Entry text

        Returns:
            True if added successfully
        """
        if section not in self.SECTIONS:
            logger.error(f"Unknown section: {section}")
            return False

        sections = self.load()
        sections[section].insert(0, entry)

        if self._estimate_section_tokens(sections) > self.max_tokens:
            self._trim_to_fit(sections)

        self.save(sections)
        return True

    def get_token_count(self) -> int:
        """Get current token count of memory file"""
        if not self.memory_file.exists():
            return 0
        content = self.memory_file.read_text(encoding='utf-8')
        return estimate_tokens(content)

    def clear_section(self, section: str) -> None:
        """Clear all entries in a section"""
        if section not in self.SECTIONS:
            logger.error(f"Unknown section: {section}")
            return

        sections = self.load()
        sections[section] = []
        self.save(sections)

    @staticmethod
    def _map_category_to_section(category: str) -> str:
        """Map observation category to memory section"""
        mapping = {
            'preference': 'User Constraints',
            'constraint': 'User Constraints',
            'decision': 'Critical Decisions',
            'task': 'Completed Tasks',
            'fact': 'Observations Log',
        }
        return mapping.get(category, 'Observations Log')

    def _estimate_section_tokens(self, sections: Dict[str, List[str]]) -> int:
        """Estimate total tokens across all sections"""
        total_text = ""
        for lines in sections.values():
            total_text += '\n'.join(lines) + '\n'
        return estimate_tokens(total_text)

    def _trim_to_fit(self, sections: Dict[str, List[str]]) -> None:
        """
        Trim sections to fit within token limit.
        Removes oldest entries from Observations Log first.
        """
        while self._estimate_section_tokens(sections) > self.max_tokens:
            # Try removing from Observations Log first (oldest = last)
            if sections["Observations Log"]:
                removed = sections["Observations Log"].pop()
                logger.debug(f"Trimmed observation: {removed[:50]}...")
                continue

            # Then from Completed Tasks
            if sections["Completed Tasks"]:
                sections["Completed Tasks"].pop()
                continue

            # Last resort: trim other sections
            for section_name in reversed(self.SECTIONS):
                if sections[section_name]:
                    sections[section_name].pop()
                    break
            else:
                break  # Nothing left to trim


# =============================================================================
# Convenience functions
# =============================================================================

def create_merger(config: Dict) -> MemoryMerger:
    """
    Create a MemoryMerger from config dictionary.

    Args:
        config: Configuration dict with 'memory' section

    Returns:
        Configured MemoryMerger instance
    """
    memory_config = config.get('memory', {})
    memory_dir = memory_config.get('dir', '~/.openclaw/workspace/memory')
    max_tokens = memory_config.get('max_tokens', 30000)

    return MemoryMerger(
        memory_dir=memory_dir,
        max_tokens=max_tokens,
    )
