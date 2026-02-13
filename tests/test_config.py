"""Tests for lib/config.py"""

import pytest
import yaml
from pathlib import Path

from lib.config import load_config, validate_config, expand_paths, get_config, ConfigError


class TestLoadConfig:
    def test_load_valid_config(self, sample_config_file):
        config = load_config(str(sample_config_file))
        assert 'watch' in config
        assert 'memory' in config

    def test_load_missing_file(self):
        with pytest.raises(ConfigError, match="not found"):
            load_config("nonexistent.yaml")

    def test_load_invalid_yaml(self, temp_dir):
        bad_file = temp_dir / "bad.yaml"
        bad_file.write_text("{ invalid yaml: [")
        with pytest.raises(ConfigError, match="Invalid YAML"):
            load_config(str(bad_file))

    def test_load_missing_required_section(self, temp_dir):
        incomplete = temp_dir / "incomplete.yaml"
        with open(incomplete, 'w') as f:
            yaml.dump({'watch': {'dirs': ['/tmp']}}, f)
        with pytest.raises(ConfigError, match="Missing required section"):
            load_config(str(incomplete))


class TestValidateConfig:
    def test_valid_config(self, sample_config):
        assert validate_config(sample_config) is True

    def test_missing_dirs(self, sample_config):
        del sample_config['watch']['dirs']
        with pytest.raises(ConfigError, match="Missing 'dirs'"):
            validate_config(sample_config)

    def test_dirs_not_list(self, sample_config):
        sample_config['watch']['dirs'] = "/single/path"
        with pytest.raises(ConfigError, match="must be a list"):
            validate_config(sample_config)

    def test_missing_memory_dir(self, sample_config):
        del sample_config['memory']['dir']
        with pytest.raises(ConfigError, match="Missing 'dir'"):
            validate_config(sample_config)


class TestExpandPaths:
    def test_expand_tilde(self):
        config = {
            'watch': {'dirs': ['~/test']},
            'memory': {'dir': '~/memory'},
        }
        expanded = expand_paths(config)
        assert '~' not in expanded['watch']['dirs'][0]
        assert '~' not in expanded['memory']['dir']

    def test_expand_preserves_other_keys(self):
        config = {
            'watch': {'dirs': ['/tmp'], 'recursive': True},
            'memory': {'dir': '/tmp/mem'},
            'extra': 'value',
        }
        expanded = expand_paths(config)
        assert expanded['watch']['recursive'] is True
        assert expanded['extra'] == 'value'


class TestGetConfig:
    def test_get_config_integration(self, sample_config_file):
        config = get_config(str(sample_config_file))
        assert 'watch' in config
        assert 'memory' in config
        # Paths should be expanded
        assert '~' not in config['memory']['dir']
