"""Tests for lib/error_notifier.py"""

import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from lib.error_notifier import ErrorNotifier, create_error_notifier


class TestErrorNotifier:
    def test_init(self):
        notifier = ErrorNotifier(
            openclaw_api="http://localhost:8080",
            webhook_url="http://example.com/hook",
        )
        assert notifier.openclaw_api == "http://localhost:8080"
        assert notifier.webhook_url == "http://example.com/hook"

    def test_no_endpoints_configured(self):
        notifier = ErrorNotifier()
        result = notifier.notify({
            'component': 'test',
            'error_type': 'TestError',
            'error_message': 'test',
        })
        assert result is False

    def test_build_payload(self):
        notifier = ErrorNotifier()
        payload = notifier._build_payload({
            'component': 'Observer',
            'error_type': 'TimeoutError',
            'error_message': 'Request timed out',
            'severity': 'high',
            'event': 'compression_failed',
            'retry_count': 3,
            'token_count': 35000,
        })

        assert payload['source'] == 'oc-memory'
        assert payload['event'] == 'compression_failed'
        assert payload['severity'] == 'high'
        assert payload['details']['component'] == 'Observer'
        assert payload['details']['retry_count'] == 3
        assert payload['action_required'] is True
        assert 'timestamp' in payload

    def test_build_payload_low_severity(self):
        notifier = ErrorNotifier()
        payload = notifier._build_payload({
            'severity': 'low',
        })
        assert payload['action_required'] is False

    def test_get_stats(self):
        notifier = ErrorNotifier()
        stats = notifier.get_stats()
        assert stats['total_sent'] == 0
        assert stats['total_failed'] == 0

    @patch('lib.error_notifier.urllib.request.urlopen')
    def test_send_http_success(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        notifier = ErrorNotifier()
        result = notifier._send_http("http://example.com/hook", {"test": True})
        assert result is True


class TestCreateErrorNotifier:
    def test_create_from_config(self):
        config = {
            'error_notification': {
                'openclaw_api': 'http://localhost:8080',
                'webhook_url': 'http://hooks.example.com',
            }
        }
        notifier = create_error_notifier(config)
        assert notifier.openclaw_api == 'http://localhost:8080'

    def test_create_with_defaults(self):
        notifier = create_error_notifier({})
        assert notifier.openclaw_api is None
        assert notifier.webhook_url is None
