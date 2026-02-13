# Release v1.0.0 — OC-Memory + OC-Guardian

**Release Date**: 2026-02-13
**OC-Memory**: v0.4.0 | **OC-Guardian**: v1.0.0

---

## Overview

OC-Memory v1.0은 OpenClaw에 장기 기억 능력을 부여하는 외장형 사이드카 시스템의 첫 번째 안정 릴리즈입니다.
Zero-Core-Modification 원칙에 따라 OpenClaw 코드를 전혀 수정하지 않고도 90일 이상의 대화 맥락을 유지하며,
Rust 기반 프로세스 가디언(OC-Guardian)이 전체 시스템을 자동으로 관리합니다.

---

## Highlights

- **90%+ 토큰 절약** — 5-40x 압축률로 비용 대폭 절감
- **3-Tier Memory** — Hot(ChromaDB) / Warm(Archive) / Cold(Obsidian+Dropbox)
- **Zero-Core-Modification** — OpenClaw 소스 코드 수정 없이 완전히 독립 동작
- **3MB 단일 바이너리** — Rust 기반 Guardian이 프로세스 관리, 헬스체크, 자동 복구 수행
- **3-Platform 지원** — Windows, macOS, Linux

---

## OC-Memory (Python) — v0.4.0

### Modules (15)

| Module | Description |
|--------|-------------|
| `config.py` | YAML 기반 설정 관리 |
| `file_watcher.py` | 디렉토리 모니터링 (watchdog) |
| `memory_writer.py` | OpenClaw 메모리 디렉토리 기록 |
| `observer.py` | LLM 기반 정보 추출 |
| `memory_merger.py` | 메모리 병합 및 중복 제거 |
| `reflector.py` | 주기적 메모리 반성/요약 |
| `memory_store.py` | ChromaDB 벡터 저장소 |
| `ttl_manager.py` | Hot → Warm → Cold 자동 전이 |
| `error_handler.py` | 에러 핸들링 및 재시도 |
| `api_detector.py` | LLM API 자동 감지 |
| `error_notifier.py` | 에러 알림 시스템 |
| `obsidian_client.py` | Obsidian vault CRUD + frontmatter |
| `dropbox_sync.py` | Dropbox 업로드/다운로드/동기화 |
| `unified_search.py` | 3-Tier 통합 검색 (Hot/Warm/Cold) |
| `__init__.py` | 패키지 초기화 (v0.4.0) |

### Phase Summary

| Phase | Scope | Key Deliverables |
|-------|-------|-----------------|
| **Phase 1** | MVP | FileWatcher, MemoryWriter, Config, Setup Wizard |
| **Phase 2** | Enhanced | Observer, Reflector, ChromaDB, TTL Manager |
| **Phase 3** | Cloud | Obsidian, Dropbox, Unified Search |
| **Phase 4** | Production | Service files, pre-commit, CI/CD |

### Tests
- **173 tests** passing across 12 test files (+9 LLM integration tests)
- Coverage: config, file_watcher, memory_writer, observer, memory_merger, reflector, ttl_manager, error_handler, api_detector, error_notifier, obsidian_client, dropbox_sync, unified_search
- New: Observer/Reflector LLM mock integration tests

---

## OC-Guardian (Rust) — v1.0.0

### Modules (11)

| Module | Description |
|--------|-------------|
| `main.rs` | CLI (clap) + supervisor loop |
| `config.rs` | TOML 파싱, 검증, topological sort |
| `process.rs` | 프로세스 spawn/stop/restart, 의존성 기반 시작 |
| `health.rs` | 5-level 헬스체크 + ResourceHistory |
| `recovery.rs` | 6 시나리오 기반 복구 엔진 |
| `log_rotation.rs` | 크기 기반 로그 로테이션 |
| `compression.rs` | 이중 트리거 메모리 압축 |
| `macos.rs` | caffeinate 슬립 방지 (조건부 컴파일) |
| `notification.rs` | Python smtplib 기반 이메일 알림 |
| `logger.rs` | tracing 로깅 설정 |
| `lib.rs` | 모듈 선언 |

### Health Check Levels

| Level | Check | Interval |
|-------|-------|----------|
| 1 | Process alive (sysinfo PID) | 5s |
| 2 | Log activity (modification time) | 30s |
| 3 | JSON config validation + auto-backup | 60s |
| 4 | CPU/Memory thresholds (sustained) | 30s |
| 5 | HTTP endpoint with retry | 60s |

### Recovery Scenarios

| Scenario | Trigger | Action |
|----------|---------|--------|
| `invalid_json` | Config 파싱 실패 | Backup 복원 + restart |
| `process_crash` | Exit code ≠ 0 | 의존성 포함 restart |
| `unresponsive` | Log activity timeout | Graceful restart |
| `memory_leak` | Memory > threshold | Graceful restart |
| `network_timeout` | HTTP endpoint timeout | Exponential backoff |
| `llm_error` | Log 패턴 매칭 | Log warning only |

### Build
- **64 tests** passing
- Release binary: **3.1 MB** (target < 5 MB)
- Cross-platform: Windows (x86_64), macOS (x86_64/arm64), Linux (x86_64)

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| OC-Memory | Python 3.8+, ChromaDB, watchdog |
| OC-Guardian | Rust 2021, tokio, clap, sysinfo |
| LLM API | OpenAI, Google Gemini |
| Cloud | Obsidian vault, Dropbox API |
| Service | systemd, launchd, Windows Scheduled Task |
| CI/CD | GitHub Actions (multi-platform) |

---

## Installation

### Quick Install

```bash
git clone https://github.com/[username]/oc-memory.git
cd oc-memory

# Python dependencies
pip install -r requirements.txt

# Interactive setup
python setup.py
```

### Guardian Build

```bash
cd guardian
cargo build --release
# Binary: target/release/oc-guardian (~3MB)
```

### System Service

```bash
# Linux
cd guardian/service && sudo ./install-service.sh install

# macOS
cd guardian/service && ./install-service.sh install

# Windows
cd guardian\service && .\install-service.ps1 -Action install
```

---

## Implementation Timeline

| Phase | Duration | Guardian | Memory |
|-------|----------|----------|--------|
| Phase 1 | Week 1-4 | Process management + CLI | FileWatcher + MemoryWriter |
| Phase 2 | Week 5-7 | 5-level health + 6 recovery | Observer + ChromaDB + TTL |
| Phase 3 | Week 8-9 | Log rotation + compression + macOS | Obsidian + Dropbox + Search |
| Phase 4 | Week 10-11 | Service + CI/CD + docs | Pre-commit + CI + docs |

---

## Post-Release Fixes (2026-02-13)

### Critical Bugs Fixed

#### memory_observer.py Integration
- **Issue**: Core engines (Observer, MemoryMerger, Reflector, TTLManager) were implemented but not connected in main daemon
- **Fix**: Integrated all 6 core engines with graceful degradation
  - Observer: LLM-based observation extraction from file changes
  - MemoryMerger: active_memory.md management with token limits
  - Reflector: Automatic compression when token threshold exceeded
  - MemoryStore: Optional ChromaDB vector storage
  - TTLManager: Hot→Warm→Cold transitions (hourly check)
  - LLMRetryPolicy: Exponential backoff for API calls
- **Impact**: System now fully operational with all Phase 1-4 features active

#### Guardian Rust Critical Bugs (7 fixes)
1. **Stdio Deadlock** (`process.rs:158-159`)
   - Issue: `Stdio::piped()` causes pipe buffer overflow → process hangs
   - Fix: Changed to `Stdio::null()` (logs captured via file_watcher)

2. **libc Dependency** (`process.rs:220-265`)
   - Issue: `unsafe { libc::kill() }` Unix-only, unsafe code
   - Fix: Replaced with `child.start_kill()` cross-platform API

3. **Stop Command No-op** (`main.rs:137`)
   - Issue: Creates fresh ProcessManager → no running processes discovered
   - Fix: Uses sysinfo to discover actual running processes by name

4. **Status Command No-op** (`main.rs:165`)
   - Issue: Same fresh ProcessManager issue
   - Fix: Real-time process discovery via sysinfo

5. **UTF-8 Byte Slicing Panic** (`health.rs:446`)
   - Issue: `&content[offset..]` panics on non-char-boundary
   - Fix: Added `is_char_boundary()` validation with forward search

6. **Log Compression Identity Function** (`log_rotation.rs:222`)
   - Issue: `simple_compress()` just copies bytes, .gz extension misleading
   - Fix: Implemented real gzip using miniz_oxide (deflate + CRC32 + header)

7. **Unused Dependencies**
   - Issue: `notify`, `thiserror` in Cargo.toml but never imported
   - Fix: Removed unused deps, added `miniz_oxide = "0.7"`

**Test Status**: All 64 tests passing (lib + bin)

#### LLM Integration Tests (+9 tests)
- **Observer**: 5 new tests with mocked `_call_llm()`
  - OpenAI/Google success paths
  - Empty response, exception handling, malformed JSON
- **Reflector**: 4 new tests with mocked `_call_llm()`
  - Level 1/3 compression success
  - Exception handling, stats accumulation

**Test Status**: 173 passing (was 164)

#### Documentation Corrections (26 stale references)
- **Issue**: Initial design used `LogWatcher`/`chat.log`/`tail -f` but actual implementation uses `FileWatcher`/`session.jsonl`/`watchdog`
- **Files Updated**: BRD.md (2), PRD.md (7), Tech_Spec.md (12), Tasks.md (5)
- **References Fixed**:
  - `LogWatcher` → `FileWatcher` (11 occurrences)
  - `~/.openclaw/logs/chat.log` → `~/.openclaw/agents/main/sessions/*.jsonl` (7 occurrences)
  - `tail -f` → `watchdog` (3 occurrences)
  - `AGENTS.md` → `openclaw.json` (3 occurrences)
  - Status checkboxes updated (`[ ]` → `[x]`)

---

## What's Next

- WebSocket 실시간 메모리 주입
- 웹 대시보드
- 메트릭 수집 (Prometheus)
- Plugin system 확장

---

## Full Specification

- [BRD.md](../specs/BRD.md) — Business Requirements
- [PRD.md](../specs/PRD.md) — Product Requirements
- [Tech_Spec.md](../specs/Tech_Spec.md) — Technical Specification
- [Tasks.md](../specs/Tasks.md) — Implementation Tasks
- [Guardian README](../guardian/README.md) — Guardian detailed docs
