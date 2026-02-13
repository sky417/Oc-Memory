# Release v1.0.2 — Configuration Update

**Release Date**: 2026-02-14
**OC-Memory**: v0.4.1 | **OC-Guardian**: v1.0.2

---

## Overview

이번 릴리즈는 `oc-guardian`의 기본 설정 파일을 프로젝트에 포함하여 초기 설정을 간소화한 업데이트입니다.

---

## Changes

### 🛡️ OC-Guardian — v1.0.2

#### Configuration
- **기본 설정 업데이트**
  - `guardian.toml` 파일이 프로젝트 루트에 포함되어 바로 사용 가능하도록 준비되었습니다.
  - 기본적으로 macOS 슬립 방지 기능은 비활성화(`prevent_sleep = false`) 상태로 제공됩니다.

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
