#!/usr/bin/env python3
"""
OC-Memory Observer Daemon
Monitors user directories, extracts observations via LLM,
manages 3-tier memory lifecycle, and syncs to OpenClaw Memory.

Usage:
    python memory_observer.py [--config CONFIG_PATH]
"""

import argparse
import logging
import signal
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from lib import __version__
from lib.config import get_config, ConfigError
from lib.file_watcher import FileWatcher
from lib.memory_writer import MemoryWriter, MemoryWriterError
from lib.observer import Observer, create_observer
from lib.memory_merger import MemoryMerger, create_merger
from lib.reflector import Reflector, create_reflector
from lib.ttl_manager import TTLManager, create_ttl_manager
from lib.error_handler import LLMRetryPolicy


class MemoryObserver:
    """
    Main daemon process for OC-Memory.
    Orchestrates all core engines:
    - FileWatcher: directory monitoring
    - MemoryWriter: file copying to OpenClaw memory
    - Observer: LLM-based observation extraction
    - MemoryMerger: active_memory.md management
    - Reflector: memory compression
    - TTLManager: Hot/Warm/Cold tier transitions
    """

    # Intervals in seconds
    TTL_CHECK_INTERVAL = 3600       # 1 hour
    COMPRESSION_CHECK_INTERVAL = 300  # 5 minutes

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.logger = logging.getLogger(__name__)

        # Load configuration
        try:
            self.config = get_config(config_path)
            self.logger.info(f"Configuration loaded from: {config_path}")
        except ConfigError as e:
            self.logger.error(f"Configuration error: {e}")
            raise

        # --- Core components (always initialized) ---
        self.memory_writer = MemoryWriter(
            memory_dir=self.config['memory']['dir']
        )

        self.file_watcher = FileWatcher(
            watch_dirs=self.config['watch']['dirs'],
            callback=self.on_file_change,
            recursive=self.config['watch'].get('recursive', True)
        )

        self.merger = create_merger(self.config)

        self.ttl_manager = create_ttl_manager(self.config)

        # --- Optional LLM components (need API key) ---
        self.observer: Optional[Observer] = None
        self.reflector: Optional[Reflector] = None
        self._init_llm_components()

        # --- Optional vector store (needs chromadb) ---
        self.memory_store = None
        self._init_memory_store()

        # --- Retry policy for LLM calls ---
        self.retry_policy = LLMRetryPolicy(
            max_attempts=3, base_delay=2.0, max_delay=30.0
        )

        # --- State ---
        self.running = False
        self.files_processed = 0
        self.observations_extracted = 0
        self.compressions_run = 0
        self.errors = 0
        self._last_ttl_check = 0.0
        self._last_compression_check = 0.0

    def _init_llm_components(self):
        """Initialize Observer and Reflector if LLM config is present."""
        llm_config = self.config.get('llm', {})
        if not llm_config:
            self.logger.info("No LLM config found, Observer/Reflector disabled")
            return

        try:
            self.observer = create_observer(self.config)
            self.reflector = create_reflector(self.config)
            if self.observer.api_key:
                self.logger.info(
                    f"Observer initialized: {self.observer.provider}/{self.observer.model}"
                )
            else:
                self.logger.warning("Observer created but no API key configured")
                self.observer = None
                self.reflector = None
        except Exception as e:
            self.logger.warning(f"LLM components unavailable: {e}")

    def _init_memory_store(self):
        """Initialize ChromaDB MemoryStore if available."""
        try:
            from lib.memory_store import create_memory_store
            self.memory_store = create_memory_store(self.config)
            self.logger.info("MemoryStore (ChromaDB) initialized")
        except ImportError:
            self.logger.info(
                "chromadb not installed, MemoryStore disabled. "
                "Run: pip install chromadb"
            )
        except Exception as e:
            self.logger.warning(f"MemoryStore unavailable: {e}")

    def on_file_change(self, file_path: Path, event_type: str) -> None:
        """Handle file change events from FileWatcher."""
        try:
            self.logger.info(f"Processing file: {file_path} ({event_type})")

            # 1. Copy to memory directory
            category = self._detect_category(file_path)
            target_file = self.memory_writer.copy_to_memory(
                source_file=file_path,
                category=category
            )

            metadata = {
                "source": str(file_path),
                "synced_at": datetime.now().isoformat(),
                "category": category,
                "event_type": event_type,
                "oc_memory_version": __version__,
            }
            self.memory_writer.add_metadata(target_file, metadata)
            self.files_processed += 1

            # 2. Extract observations via LLM (if available)
            if self.observer:
                self._extract_observations_from_file(file_path)

            self.logger.info(
                f"Synced to memory: {target_file} "
                f"(files: {self.files_processed}, "
                f"observations: {self.observations_extracted})"
            )

        except MemoryWriterError as e:
            self.errors += 1
            self.logger.error(f"Error processing file {file_path}: {e}")
        except Exception as e:
            self.errors += 1
            self.logger.exception(f"Unexpected error processing {file_path}: {e}")

    def _extract_observations_from_file(self, file_path: Path):
        """Read a markdown file and extract observations via LLM."""
        try:
            content = file_path.read_text(encoding='utf-8')
            if not content.strip():
                return

            messages = [{"role": "user", "content": content}]
            observations = self.retry_policy.call_with_retry(
                self.observer.observe, messages
            )

            if not observations:
                return

            # Add to MemoryMerger (active_memory.md)
            added = self.merger.add_observations(observations)

            # Add to ChromaDB (if available)
            if self.memory_store:
                try:
                    self.memory_store.add_observations(observations)
                except Exception as e:
                    self.logger.warning(f"Failed to add to MemoryStore: {e}")

            self.observations_extracted += added
            self.logger.info(
                f"Extracted {added} observations from {file_path.name}"
            )

        except Exception as e:
            self.logger.warning(f"Observation extraction failed for {file_path}: {e}")

    def _run_periodic_tasks(self):
        """Run periodic maintenance tasks (compression, TTL)."""
        now = time.time()

        # TTL check (Hot -> Warm -> Cold)
        if now - self._last_ttl_check >= self.TTL_CHECK_INTERVAL:
            self._last_ttl_check = now
            try:
                result = self.ttl_manager.check_and_archive()
                if result.hot_to_warm > 0:
                    self.logger.info(
                        f"TTL archive: {result.hot_to_warm} files moved Hot->Warm"
                    )
            except Exception as e:
                self.logger.error(f"TTL check failed: {e}")

        # Compression check
        if now - self._last_compression_check >= self.COMPRESSION_CHECK_INTERVAL:
            self._last_compression_check = now
            self._check_compression()

    def _check_compression(self):
        """Check if memory compression is needed and run if so."""
        if not self.reflector:
            return

        token_count = self.merger.get_token_count()
        if not self.reflector.should_reflect(token_count):
            return

        level = self.reflector.suggest_level(token_count)
        if level == 0:
            return

        try:
            # Read current observations from active_memory.md
            sections = self.merger.load()
            obs_text = '\n'.join(sections.get('Observations Log', []))
            if not obs_text.strip():
                return

            result = self.retry_policy.call_with_retry(
                self.reflector.reflect, obs_text, level
            )

            if result.compression_ratio > 1.0:
                # Replace observations with compressed content
                sections['Observations Log'] = [result.compressed_content]
                self.merger.save(sections)
                self.compressions_run += 1
                self.logger.info(
                    f"Compression: {result.original_tokens} -> "
                    f"{result.compressed_tokens} tokens "
                    f"({result.compression_ratio:.1f}x)"
                )

        except Exception as e:
            self.logger.error(f"Compression failed: {e}")

    def _detect_category(self, file_path: Path) -> str:
        if not self.config['memory'].get('auto_categorize', True):
            return 'general'
        return self.memory_writer.get_category_from_path(file_path)

    def start(self) -> None:
        """Start the observer daemon."""
        self.logger.info("=" * 60)
        self.logger.info(f"Starting OC-Memory Observer v{__version__}")
        self.logger.info("=" * 60)
        self.logger.info(f"Watch directories: {self.config['watch']['dirs']}")
        self.logger.info(f"Memory directory: {self.config['memory']['dir']}")
        self.logger.info(f"Observer: {'enabled' if self.observer else 'disabled'}")
        self.logger.info(f"Reflector: {'enabled' if self.reflector else 'disabled'}")
        self.logger.info(f"MemoryStore: {'enabled' if self.memory_store else 'disabled'}")
        self.logger.info("=" * 60)

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        try:
            self.file_watcher.start()
        except Exception as e:
            self.logger.error(f"Failed to start FileWatcher: {e}")
            raise

        self.running = True
        self._last_ttl_check = time.time()
        self._last_compression_check = time.time()
        self.logger.info("OC-Memory Observer started successfully")
        self.logger.info("Monitoring for file changes... (Press Ctrl+C to stop)")

        # Main loop with periodic tasks
        try:
            while self.running:
                self._run_periodic_tasks()
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")

        self.stop()

    def stop(self) -> None:
        """Stop the observer daemon."""
        self.logger.info("Stopping OC-Memory Observer...")
        self.running = False

        if self.file_watcher.is_alive():
            self.file_watcher.stop()

        self.logger.info("=" * 60)
        self.logger.info("OC-Memory Observer Statistics")
        self.logger.info("=" * 60)
        self.logger.info(f"Files processed: {self.files_processed}")
        self.logger.info(f"Observations extracted: {self.observations_extracted}")
        self.logger.info(f"Compressions run: {self.compressions_run}")
        self.logger.info(f"Errors: {self.errors}")
        if self.reflector:
            stats = self.reflector.get_stats()
            self.logger.info(f"Compression stats: {stats}")
        self.logger.info("=" * 60)
        self.logger.info("OC-Memory Observer stopped")

    def _signal_handler(self, signum: int, frame) -> None:
        self.logger.info(f"Received signal {signum}")
        self.stop()
        sys.exit(0)


def setup_logging(config: dict) -> None:
    """Setup logging configuration."""
    log_config = config.get('logging', {})
    level = getattr(logging, log_config.get('level', 'INFO'))
    log_file = log_config.get('file', 'oc-memory.log')
    console = log_config.get('console', True)

    handlers = []

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    handlers.append(file_handler)

    if console:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S')
        )
        handlers.append(console_handler)

    logging.basicConfig(level=level, handlers=handlers)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description='OC-Memory Observer Daemon')
    parser.add_argument(
        '--config', default='config.yaml',
        help='Path to configuration file (default: config.yaml)'
    )
    parser.add_argument(
        '--version', action='version',
        version=f'OC-Memory {__version__}'
    )

    args = parser.parse_args()

    if not Path(args.config).exists():
        print(f"Error: Configuration file not found: {args.config}")
        print(f"Please copy config.example.yaml to {args.config} and customize it")
        sys.exit(1)

    try:
        config = get_config(args.config)
    except ConfigError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)

    setup_logging(config)

    try:
        observer = MemoryObserver(config_path=args.config)
        observer.start()
    except ConfigError as e:
        logging.error(f"Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logging.exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
