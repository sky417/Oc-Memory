# Release v1.0.3 — Hotfix: Log Path Fix

**Release Date**: 2026-02-14
**OC-Memory**: v0.4.1 | **OC-Guardian**: v1.0.3

---

## Overview

이번 릴리즈는 `oc-guardian`이 OpenClaw의 상태를 올바르게 감시하지 못하던 경로 오류를 수정한 긴급 패치입니다.

---

## Changes

### 🛡️ OC-Guardian — v1.0.3

#### Bug Fixes
- **OpenClaw 로그 경로 수정**
  - 기존 `chat.log`로 설정되어 있던 감시 경로를 실제 생성되는 `gateway.log`로 변경하였습니다.
  - 이 수정으로 인해 가미언이 OpenClaw의 시작 여부를 정확히 판단하고 안정적으로 프로세스를 관리할 수 있게 되었습니다.

#### Configuration
- `guardian.toml` 내의 `log_file` 및 `managed_logs` 경로가 최신 사양에 맞게 업데이트되었습니다.

---

## How to Apply

```bash
# 최신 코드 반영
git pull origin main

# 서비스 재시작
./oc-guardian stop
./oc-guardian start
```

---

## What's Next
- 프로세스 안정성 모니터링 강화
- 로그 순환(Rotation) 정책 최적화
