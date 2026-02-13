# OC-Guardian

Rust-based process guardian for managing OpenClaw and OC-Memory processes.

## Features

- **Process Management**: Start, stop, restart processes in dependency order
- **5-Level Health Checks**: Process alive, log activity, JSON config validation, resource monitoring, HTTP endpoint
- **6 Recovery Scenarios**: invalid_json, process_crash, unresponsive, memory_leak, network_timeout, llm_error
- **Log Rotation**: Size-based rotation with generational backups
- **Memory Compression**: Dual-trigger (token threshold + scheduled) with LLM integration
- **macOS Sleep Prevention**: Automatic caffeinate management
- **Email Notifications**: SMTP alerts for process crashes, health failures, and recovery events
- **Cross-Platform**: Windows, macOS, Linux

## Quick Start

```bash
# Build
cargo build --release

# Run with config
./target/release/oc-guardian start --config guardian.toml

# Check status
./target/release/oc-guardian status

# Stop all
./target/release/oc-guardian stop
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `start` | Start all processes in dependency order |
| `stop` | Stop all processes gracefully |
| `restart [name]` | Restart a process or all processes |
| `status` | Show process status table |
| `logs [name] [-f] [-n 50]` | View process logs |

## Configuration

See `guardian.toml.example` for full configuration reference.

```toml
[processes.openclaw]
name = "openclaw"
command = "openclaw"
args = ["chat"]
working_dir = "~/.openclaw"

[processes.oc-memory]
name = "oc-memory"
command = "python"
args = ["memory_observer.py"]
depends_on = ["openclaw"]

[recovery]
max_restarts = 5
backoff_strategy = "exponential"

[logging]
output = "guardian.log"
level = "info"
max_size = "50MB"
```

## Health Check Levels

| Level | Check | Description |
|-------|-------|-------------|
| 1 | Process Alive | Verify PID exists via sysinfo |
| 2 | Log Activity | Monitor log file modification time |
| 3 | Config Validation | JSON config parsing + auto-backup |
| 4 | Resources | CPU/memory thresholds with sustained monitoring |
| 5 | HTTP Endpoint | Health endpoint with retry logic |

## Recovery Scenarios

| Scenario | Trigger | Action |
|----------|---------|--------|
| invalid_json | Config validation failed | Restore backup + restart |
| process_crash | Exit code != 0 | Restart with dependencies |
| unresponsive | Log activity timeout | Graceful restart |
| memory_leak | Memory > threshold | Graceful restart |
| network_timeout | HTTP endpoint timeout | Exponential backoff |
| llm_error | Log pattern match | Log warning only |

## System Service

### Linux (systemd)
```bash
cd guardian/service
sudo ./install-service.sh install
sudo systemctl start oc-guardian
```

### macOS (launchd)
```bash
cd guardian/service
./install-service.sh install
```

### Windows (Scheduled Task)
```powershell
cd guardian\service
.\install-service.ps1 -Action install
```

## Project Structure

```
guardian/
├── Cargo.toml
├── src/
│   ├── main.rs          # CLI + supervisor loop
│   ├── config.rs        # TOML config parsing
│   ├── process.rs       # Process management
│   ├── health.rs        # 5-level health checker
│   ├── recovery.rs      # Recovery engine
│   ├── log_rotation.rs  # Log rotation
│   ├── compression.rs   # Memory compression
│   ├── macos.rs         # macOS sleep prevention
│   ├── notification.rs  # Email notifications
│   ├── logger.rs        # Logging setup
│   └── lib.rs           # Module declarations
├── service/             # System service templates
└── guardian.toml.example
```

## Build

```bash
# Debug build
cargo build

# Release build (optimized, ~3MB)
cargo build --release

# Run tests
cargo test
```

## Requirements

- Rust 1.70+
- Python 3.8+ (optional, for LLM compression and email)
