# Release v1.0.4 — MacBook 덮개 닫기 슬립 방지 개선

**Release Date**: 2026-02-14
**OC-Memory**: v0.4.1 | **OC-Guardian**: v1.0.4

---

## Overview

MacBook 덮개를 닫았을 때 터미널 세션이 종료되는 문제를 해결한 패치입니다. `caffeinate` 플래그에 `-s`(system sleep 방지)를 추가하고, sudo 없이 작동하는 슬립 방지를 기본 활성화했습니다.

---

## Changes

### 🛡️ OC-Guardian — v1.0.4

#### Bug Fixes
- **덮개 닫기 시 터미널 다운 문제 수정**
  - `caffeinate -di` → `caffeinate -dis`로 변경
  - `-s` 플래그 추가로 system sleep(덮개 닫기)까지 방지
  - 기존에는 display + idle sleep만 방지하여 덮개 닫기 시 세션이 죽는 문제가 있었음

#### Configuration
- **슬립 방지 기본 활성화**
  - `guardian.toml`의 `prevent_sleep`을 `true`로 변경
  - `caffeinate` 방식 사용 (sudo 불필요)
  - 수동 `sudo pmset -c disablesleep 1` 실행이 더 이상 필요 없음

---

## Migration Guide

```bash
# 1. 최신 코드 반영
git pull origin main

# 2. 수동 pmset 설정 해제 (이전에 설정한 경우)
sudo pmset -c disablesleep 0

# 3. Guardian 재시작
./oc-guardian stop
./oc-guardian start
```

---

## What's Next
- 슬립 방지 상태 모니터링 (caffeinate 프로세스 health check)
- 배터리 모드 시 슬립 방지 정책 최적화
