"""
Shared test fixtures for OC-Memory test suite
"""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Provide a temporary directory that's cleaned up after test"""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_config(temp_dir):
    """Provide a sample configuration dictionary"""
    return {
        'watch': {
            'dirs': [str(temp_dir / 'watch')],
            'recursive': True,
            'poll_interval': 1.0,
        },
        'memory': {
            'dir': str(temp_dir / 'memory'),
            'auto_categorize': True,
            'max_file_size': 10485760,
        },
        'logging': {
            'level': 'DEBUG',
            'file': str(temp_dir / 'test.log'),
            'console': False,
        },
        'hot_memory': {
            'ttl_days': 90,
            'max_observations': 10000,
        },
        'llm': {
            'provider': 'openai',
            'model': 'gpt-4o-mini',
            'api_key_env': 'OPENAI_API_KEY',
            'enabled': False,
        },
        'obsidian': {'enabled': False},
        'dropbox': {'enabled': False},
    }


@pytest.fixture
def sample_config_file(temp_dir, sample_config):
    """Create a sample config.yaml file and return its path"""
    import yaml
    config_path = temp_dir / 'config.yaml'
    with open(config_path, 'w') as f:
        yaml.dump(sample_config, f)
    return config_path


@pytest.fixture
def memory_dir(temp_dir):
    """Provide a temporary memory directory"""
    d = temp_dir / 'memory'
    d.mkdir(parents=True)
    return d


@pytest.fixture
def watch_dir(temp_dir):
    """Provide a temporary watch directory"""
    d = temp_dir / 'watch'
    d.mkdir(parents=True)
    return d


@pytest.fixture
def sample_markdown():
    """Provide sample markdown content"""
    return """# Test Note

## Overview
This is a test memory file for unit testing.

## Key Points
- Point 1: Important fact about the project
- Point 2: User prefers Python over JavaScript
- Point 3: Decision to use ChromaDB for vector storage
"""


@pytest.fixture
def sample_messages():
    """Provide sample conversation messages"""
    return [
        {"role": "user", "content": "I prefer using Python for this project."},
        {"role": "assistant", "content": "Got it, we'll use Python."},
        {"role": "user", "content": "Let's use ChromaDB for vector storage. The deadline is March 15."},
        {"role": "assistant", "content": "I'll set up ChromaDB. March 15 noted as deadline."},
        {"role": "user", "content": "Always use type hints in the code."},
    ]
