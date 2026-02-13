"""
OpenClaw API Detector for OC-Memory
Auto-detection of OpenClaw API endpoints

Provides multiple detection methods to find running
OpenClaw instances without manual configuration.
"""

import json
import logging
import os
import socket
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


# =============================================================================
# API Detector
# =============================================================================

class OpenClawAPIDetector:
    """
    Auto-detects OpenClaw API endpoint using multiple methods.

    Detection priority:
    1. Config file (~/.openclaw/config.yaml)
    2. Environment variable (OPENCLAW_API_URL)
    3. Process port scan (psutil)
    4. Default port probing (8080, 8000, 3000, 18789)
    """

    DEFAULT_PORTS = [18789, 8080, 8000, 3000]
    TIMEOUT = 2.0  # seconds

    def __init__(self):
        self.detected_endpoint: Optional[str] = None
        self.detection_method: Optional[str] = None

    def detect_api_endpoint(self) -> Optional[str]:
        """
        Try all detection methods in priority order.

        Returns:
            Detected API endpoint URL, or None if not found
        """
        methods = [
            ("config_file", self._read_openclaw_config),
            ("env_variable", self._check_env_variable),
            ("process_scan", self._scan_openclaw_process),
            ("port_probe", self._probe_default_ports),
        ]

        for method_name, method_func in methods:
            try:
                endpoint = method_func()
                if endpoint and self._test_connection(endpoint):
                    self.detected_endpoint = endpoint
                    self.detection_method = method_name
                    logger.info(
                        f"OpenClaw API detected: {endpoint} "
                        f"(method: {method_name})"
                    )
                    return endpoint
            except Exception as e:
                logger.debug(f"Detection method '{method_name}' failed: {e}")

        logger.warning("Could not auto-detect OpenClaw API endpoint")
        return None

    def _read_openclaw_config(self) -> Optional[str]:
        """Method 1: Read OpenClaw config file"""
        config_paths = [
            Path.home() / ".openclaw" / "config.yaml",
            Path.home() / ".openclaw" / "config.json",
        ]

        for config_path in config_paths:
            if not config_path.exists():
                continue

            try:
                if config_path.suffix == '.yaml':
                    import yaml
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                else:
                    with open(config_path, 'r') as f:
                        config = json.load(f)

                # Look for API endpoint in various locations
                endpoint = None
                if isinstance(config, dict):
                    endpoint = (
                        config.get('http_api', {}).get('endpoint')
                        or config.get('api', {}).get('url')
                        or config.get('api_url')
                    )

                if endpoint:
                    logger.debug(f"Found endpoint in config: {endpoint}")
                    return endpoint

            except Exception as e:
                logger.debug(f"Failed to parse {config_path}: {e}")

        return None

    def _check_env_variable(self) -> Optional[str]:
        """Method 2: Check environment variable"""
        env_vars = ['OPENCLAW_API_URL', 'OPENCLAW_URL', 'OC_API_URL']

        for var in env_vars:
            value = os.environ.get(var)
            if value:
                logger.debug(f"Found endpoint in {var}: {value}")
                return value

        return None

    def _scan_openclaw_process(self) -> Optional[str]:
        """Method 3: Scan for 'openclaw gateway' process using psutil"""
        try:
            import psutil
        except ImportError:
            logger.debug("psutil not installed, skipping process scan")
            return None

        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                name = proc.info.get('name', '').lower()
                cmdline_parts = proc.info.get('cmdline', []) or []
                cmdline = ' '.join(cmdline_parts).lower()

                # Match 'openclaw gateway' command specifically
                is_gateway = (
                    ('openclaw' in name and 'gateway' in cmdline)
                    or 'openclaw gateway' in cmdline
                )

                if is_gateway:
                    # Try to find listening ports
                    connections = proc.net_connections(kind='inet')
                    for conn in connections:
                        if conn.status == 'LISTEN':
                            port = conn.laddr.port
                            endpoint = f"http://localhost:{port}"
                            logger.debug(
                                f"Found 'openclaw gateway' process "
                                f"(PID {proc.pid}) listening on port {port}"
                            )
                            return endpoint
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return None

    def _probe_default_ports(self) -> Optional[str]:
        """Method 4: Probe default ports"""
        for port in self.DEFAULT_PORTS:
            endpoint = f"http://localhost:{port}"
            if self._is_port_open("localhost", port):
                logger.debug(f"Port {port} is open")
                return endpoint

        return None

    def _test_connection(self, endpoint: str) -> bool:
        """
        Test if an endpoint is reachable and responding.

        Args:
            endpoint: URL to test

        Returns:
            True if connection successful
        """
        try:
            import urllib.request
            import urllib.error

            # Try health endpoint
            health_urls = [
                f"{endpoint}/health",
                f"{endpoint}/api/health",
                endpoint,
            ]

            for url in health_urls:
                try:
                    req = urllib.request.Request(url, method='GET')
                    with urllib.request.urlopen(req, timeout=self.TIMEOUT) as resp:
                        if resp.status < 500:
                            return True
                except urllib.error.URLError:
                    continue

        except Exception as e:
            logger.debug(f"Connection test failed for {endpoint}: {e}")

        return False

    @staticmethod
    def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
        """Check if a TCP port is open"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def get_result(self) -> dict:
        """Get detection result"""
        return {
            'endpoint': self.detected_endpoint,
            'method': self.detection_method,
            'success': self.detected_endpoint is not None,
        }
