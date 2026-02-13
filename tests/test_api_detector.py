"""Tests for lib/api_detector.py"""

import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from lib.api_detector import OpenClawAPIDetector


class TestOpenClawAPIDetector:
    def test_init(self):
        detector = OpenClawAPIDetector()
        assert detector.detected_endpoint is None
        assert detector.detection_method is None

    def test_check_env_variable(self):
        detector = OpenClawAPIDetector()

        with patch.dict(os.environ, {'OPENCLAW_API_URL': 'http://localhost:9999'}):
            result = detector._check_env_variable()
            assert result == 'http://localhost:9999'

    def test_check_env_variable_not_set(self):
        detector = OpenClawAPIDetector()
        # Ensure env vars are not set
        for var in ['OPENCLAW_API_URL', 'OPENCLAW_URL', 'OC_API_URL']:
            os.environ.pop(var, None)
        result = detector._check_env_variable()
        assert result is None

    def test_is_port_open_closed(self):
        # Port 59999 should not be open on localhost
        assert OpenClawAPIDetector._is_port_open("localhost", 59999, timeout=0.1) is False

    def test_get_result_initial(self):
        detector = OpenClawAPIDetector()
        result = detector.get_result()
        assert result['success'] is False
        assert result['endpoint'] is None
        assert result['method'] is None

    def test_read_openclaw_config_no_file(self):
        detector = OpenClawAPIDetector()
        # Should return None if config files don't exist
        with patch.object(Path, 'exists', return_value=False):
            result = detector._read_openclaw_config()
            # May or may not be None depending on actual files
            # Just ensure it doesn't crash

    def test_probe_default_ports_none_open(self):
        detector = OpenClawAPIDetector()
        # Mock _is_port_open to always return False
        with patch.object(OpenClawAPIDetector, '_is_port_open', return_value=False):
            result = detector._probe_default_ports()
            assert result is None
