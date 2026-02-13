# Release v1.0.2 — Feature Update

**Release Date**: 2026-02-14
**OC-Memory**: v0.4.1 | **OC-Guardian**: v1.0.2

---

## Overview

이번 릴리즈는 macOS 환경에서 맥북 덮개를 닫아도 서비스가 중단되지 않도록 하는 **슬립 방지 기능(Sleep Prevention)**을 활성화하고, `oc-guardian`을 통해 서비스를 통합 관리하도록 개선한 업데이트입니다.

---

## Changes

### 🛡️ OC-Guardian — v1.0.2

#### Features
- **macOS 슬립 방지 기능 활성화** (`guardian.toml`)
  - **Issue**: 맥북 덮개를 닫거나 절전 모드로 진입할 때 터미널 프로세스가 중단되던 현상.
  - **Improvement**: `guardian.toml`의 `macos.prevent_sleep` 설정을 `true`로 기본 활성화했습니다. 이제 `oc-guardian` 실행 시 `caffeinate` 명령어를 통해 시스템 슬립을 자동으로 방지합니다.

#### Configuration
- **기본 설정 업데이트**
  - `guardian.toml` 파일이 프로젝트 루트에 포함되어 바로 사용 가능하도록 준비되었습니다.

---

## How to Apply

```bash
# 최신 코드 반영
git pull origin main

# 서비스 시작 (이미 설정 완료됨)
./oc-guardian start
```

---

## What's Next
- WebSocket 실시간 메모리 주입 기능 고도화
- 가상 환경(venv) 관리 자동화 스크립트 보완
