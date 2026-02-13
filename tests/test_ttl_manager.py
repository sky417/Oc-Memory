"""Tests for lib/ttl_manager.py"""

import os
import time
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from lib.ttl_manager import TTLManager, ArchiveResult, create_ttl_manager


class TestTTLManager:
    def test_init_creates_directories(self, temp_dir):
        mem_dir = temp_dir / "mem"
        archive_dir = temp_dir / "archive"
        mgr = TTLManager(str(mem_dir), str(archive_dir))
        assert mem_dir.exists()
        assert archive_dir.exists()

    def test_check_no_files(self, temp_dir):
        mgr = TTLManager(str(temp_dir / "mem"), str(temp_dir / "archive"))
        result = mgr.check_and_archive()
        assert result.hot_to_warm == 0
        assert result.errors == 0

    def test_active_memory_not_archived(self, temp_dir):
        mem_dir = temp_dir / "mem"
        mem_dir.mkdir(parents=True)

        # Create active_memory.md with old mtime
        active = mem_dir / "active_memory.md"
        active.write_text("# Active Memory")
        old_time = time.time() - (100 * 86400)  # 100 days ago
        os.utime(active, (old_time, old_time))

        mgr = TTLManager(str(mem_dir), hot_ttl_days=90)
        result = mgr.check_and_archive()
        assert result.hot_to_warm == 0
        assert active.exists()  # Should NOT be moved

    def test_old_file_archived(self, temp_dir):
        mem_dir = temp_dir / "mem"
        mem_dir.mkdir(parents=True)

        # Create old file
        old_file = mem_dir / "old_note.md"
        old_file.write_text("# Old Note")
        old_time = time.time() - (100 * 86400)  # 100 days ago
        os.utime(old_file, (old_time, old_time))

        mgr = TTLManager(str(mem_dir), str(temp_dir / "archive"), hot_ttl_days=90)
        result = mgr.check_and_archive()
        assert result.hot_to_warm == 1
        assert not old_file.exists()  # Should be moved

    def test_recent_file_not_archived(self, temp_dir):
        mem_dir = temp_dir / "mem"
        mem_dir.mkdir(parents=True)

        # Create recent file
        recent = mem_dir / "recent.md"
        recent.write_text("# Recent Note")

        mgr = TTLManager(str(mem_dir), str(temp_dir / "archive"), hot_ttl_days=90)
        result = mgr.check_and_archive()
        assert result.hot_to_warm == 0
        assert recent.exists()

    def test_get_stats(self, temp_dir):
        mem_dir = temp_dir / "mem"
        mem_dir.mkdir(parents=True)
        (mem_dir / "file1.md").write_text("content")
        (mem_dir / "file2.md").write_text("content")

        mgr = TTLManager(str(mem_dir), str(temp_dir / "archive"))
        stats = mgr.get_stats()
        assert stats['hot']['files'] == 2
        assert stats['warm']['files'] == 0
        assert stats['hot_ttl_days'] == 90

    def test_get_cold_candidates(self, temp_dir):
        archive_dir = temp_dir / "archive"
        archive_dir.mkdir(parents=True)

        # Create old archive file
        old = archive_dir / "old.md"
        old.write_text("old content")
        old_time = time.time() - (400 * 86400)  # 400 days
        os.utime(old, (old_time, old_time))

        mgr = TTLManager(str(temp_dir / "mem"), str(archive_dir), warm_ttl_days=365)
        candidates = mgr.get_cold_candidates()
        assert len(candidates) == 1

    def test_archive_to_cold(self, temp_dir):
        archive_dir = temp_dir / "archive"
        cold_dir = temp_dir / "cold"
        archive_dir.mkdir(parents=True)

        test_file = archive_dir / "to_cold.md"
        test_file.write_text("cold content")

        mgr = TTLManager(str(temp_dir / "mem"), str(archive_dir))
        result = mgr.archive_to_cold(test_file, cold_dir)

        assert result is not None
        assert result.exists()
        assert not test_file.exists()

    def test_archive_to_cold_no_dir(self, temp_dir):
        mgr = TTLManager(str(temp_dir / "mem"))
        result = mgr.archive_to_cold(temp_dir / "nonexistent.md")
        assert result is None


class TestCreateTTLManager:
    def test_create_from_config(self, temp_dir):
        config = {
            'memory': {'dir': str(temp_dir)},
            'hot_memory': {'ttl_days': 60},
        }
        mgr = create_ttl_manager(config)
        assert mgr.hot_ttl_days == 60
