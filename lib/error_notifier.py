"""
Error Notifier for OC-Memory
HTTP API notification system for error alerts

Sends error notifications to OpenClaw and external
services when critical failures occur.
"""

import json
import logging
import urllib.request
import urllib.error
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# Error Notifier
# =============================================================================

class ErrorNotifier:
    """
    Sends error notifications via HTTP API.

    Supports:
    - OpenClaw webhook (POST /hooks/agent)
    - Custom webhook URLs
    """

    def __init__(
        self,
        openclaw_api: Optional[str] = None,
        webhook_url: Optional[str] = None,
        timeout: float = 5.0,
    ):
        """
        Args:
            openclaw_api: OpenClaw API base URL
            webhook_url: Custom webhook URL for notifications
            timeout: HTTP request timeout in seconds
        """
        self.openclaw_api = openclaw_api
        self.webhook_url = webhook_url
        self.timeout = timeout

        # Statistics
        self.total_sent = 0
        self.total_failed = 0

    def notify(self, error_details: Dict[str, Any]) -> bool:
        """
        Send error notification.

        Args:
            error_details: Error details dict with keys:
                - component: str (e.g., 'Observer', 'Reflector')
                - error_type: str (e.g., 'TimeoutError')
                - error_message: str
                - severity: str ('low', 'medium', 'high', 'critical')
                - retry_count: int (optional)

        Returns:
            True if notification sent successfully
        """
        payload = self._build_payload(error_details)
        success = False

        # Try OpenClaw webhook
        if self.openclaw_api:
            url = f"{self.openclaw_api}/hooks/agent"
            if self._send_http(url, payload):
                success = True

        # Try custom webhook
        if self.webhook_url:
            if self._send_http(self.webhook_url, payload):
                success = True

        if success:
            self.total_sent += 1
        else:
            self.total_failed += 1

        if not self.openclaw_api and not self.webhook_url:
            logger.debug("No notification endpoints configured")
            return False

        return success

    def notify_compression_failed(
        self,
        component: str,
        error: Exception,
        token_count: int = 0,
        retry_count: int = 0,
    ) -> bool:
        """Send compression failure notification"""
        return self.notify({
            'component': component,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'severity': 'high',
            'retry_count': retry_count,
            'token_count': token_count,
            'event': 'compression_failed',
        })

    def notify_health_check_failed(
        self,
        component: str,
        message: str,
    ) -> bool:
        """Send health check failure notification"""
        return self.notify({
            'component': component,
            'error_type': 'HealthCheckFailed',
            'error_message': message,
            'severity': 'medium',
            'event': 'health_check_failed',
        })

    def _build_payload(self, error_details: Dict[str, Any]) -> Dict[str, Any]:
        """Build notification payload"""
        return {
            'source': 'oc-memory',
            'event': error_details.get('event', 'error'),
            'severity': error_details.get('severity', 'medium'),
            'timestamp': datetime.now().isoformat(),
            'details': {
                'component': error_details.get('component', 'unknown'),
                'error_type': error_details.get('error_type', 'UnknownError'),
                'error_message': error_details.get('error_message', ''),
                'retry_count': error_details.get('retry_count', 0),
                'token_count': error_details.get('token_count', 0),
            },
            'action_required': error_details.get('severity', 'medium') in ('high', 'critical'),
        }

    def _send_http(self, url: str, payload: Dict[str, Any]) -> bool:
        """
        Send HTTP POST request.

        Args:
            url: Target URL
            payload: JSON payload

        Returns:
            True if request successful (2xx status)
        """
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'OC-Memory/0.1.0',
                },
                method='POST',
            )

            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                if resp.status < 300:
                    logger.info(f"Notification sent to {url}")
                    return True
                else:
                    logger.warning(
                        f"Notification response {resp.status} from {url}"
                    )
                    return False

        except urllib.error.URLError as e:
            logger.warning(f"Failed to send notification to {url}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending notification: {e}")
            return False

    def get_stats(self) -> Dict[str, int]:
        """Get notification statistics"""
        return {
            'total_sent': self.total_sent,
            'total_failed': self.total_failed,
        }


def create_error_notifier(config: Dict[str, Any]) -> ErrorNotifier:
    """Create an ErrorNotifier from config dictionary"""
    error_config = config.get('error_notification', {})

    return ErrorNotifier(
        openclaw_api=error_config.get('openclaw_api'),
        webhook_url=error_config.get('webhook_url'),
    )
