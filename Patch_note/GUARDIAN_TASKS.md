# OC-Guardian 구현 Task 분해

**프로젝트**: OC-Guardian (OpenClaw Process Guardian)
**작성일**: 2026-02-13
**총 예상 기간**: 7-9주
**우선순위**: P0 (Critical) → P1 (High) → P2 (Medium) → P3 (Low)

---

## 📊 프로젝트 개요

### 목표
OpenClaw와 OC-Memory를 안정적으로 관리하는 Rust 기반 프로세스 가디언 시스템 개발

### 주요 기능
- ✅ 자동 순차 시작 (OpenClaw → OC-Memory)
- ✅ 5단계 멀티 레벨 헬스체크
- ✅ 시나리오 기반 자동 복구
- ✅ 로그 자동 로테이션
- ✅ 메모리 압축 (이중 트리거)
- ✅ Email 알림
- ✅ MacBook 슬립 방지

### 개발 환경
- **언어**: Rust 2021 Edition
- **플랫폼**: Windows, macOS, Linux
- **의존성**: 최소화 (단일 바이너리 목표)

---

## 📋 Phase 1: 핵심 Guardian (2-3주)

### 목표
기본 프로세스 관리 + 순차 시작 기능 구현

### Sprint 1.1: 프로젝트 설정 (2일)

#### Task 1.1.1: Rust 프로젝트 초기화
- **우선순위**: P0
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] `cargo new oc-guardian --bin` 실행
  - [x] 프로젝트 구조 생성
    ```
    oc-guardian/
    ├── Cargo.toml
    ├── src/
    │   ├── main.rs
    │   ├── config.rs
    │   ├── process.rs
    │   ├── health.rs
    │   ├── recovery.rs
    │   ├── logger.rs
    │   └── lib.rs
    ├── guardian.toml.example
    └── README.md
    ```
  - [x] `.gitignore` 설정
  - [x] README.md 작성

#### Task 1.1.2: Cargo.toml 의존성 설정
- **우선순위**: P0
- **예상 시간**: 1시간
- **의존성**:
  ```toml
  [dependencies]
  tokio = { version = "1.35", features = ["full"] }
  clap = { version = "4.4", features = ["derive"] }
  serde = { version = "1.0", features = ["derive"] }
  toml = "0.8"
  tracing = "0.1"
  tracing-subscriber = { version = "0.3", features = ["json"] }
  sysinfo = "0.30"
  anyhow = "1.0"
  thiserror = "1.0"
  chrono = "0.4"
  ```
- **체크리스트**:
  - [x] 의존성 추가
  - [x] `cargo build` 테스트
  - [x] 릴리스 프로필 최적화 설정

#### Task 1.1.3: 개발 환경 설정
- **우선순위**: P1
- **예상 시간**: 1시간
- **체크리스트**:
  - [x] `rustfmt.toml` 설정
  - [x] `clippy.toml` 설정
  - [x] VSCode/IDE 설정
  - [x] CI/CD 초안 (GitHub Actions)

---

### Sprint 1.2: TOML 설정 파싱 (3일)

#### Task 1.2.1: 설정 구조체 정의
- **우선순위**: P0
- **예상 시간**: 4시간
- **파일**: `src/config.rs`
- **체크리스트**:
  - [x] `SupervisorConfig` 구조체
  - [x] `ProcessConfig` 구조체
  - [x] `HealthConfig` 구조체
  - [x] `RecoveryConfig` 구조체
  - [x] `LoggingConfig` 구조체
  - [x] Serde derive 매크로 적용
  - [x] 기본값 함수 작성

**코드 스켈레톤**:
```rust
#[derive(Debug, Deserialize, Serialize)]
pub struct SupervisorConfig {
    pub processes: HashMap<String, ProcessConfig>,
    pub recovery: RecoveryConfig,
    pub logging: LoggingConfig,
    #[serde(default)]
    pub memory: MemoryConfig,
}
```

#### Task 1.2.2: TOML 파일 로드 및 검증
- **우선순위**: P0
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] `load_config()` 함수 구현
  - [x] 경로 확장 (`~` → 절대 경로)
  - [x] 필수 섹션 검증
  - [x] 의존성 순환 검증
  - [x] 에러 메시지 개선

#### Task 1.2.3: 설정 파일 예시 작성
- **우선순위**: P1
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] `guardian.toml.example` 작성
  - [x] 주석으로 설명 추가
  - [x] 모든 옵션 포함
  - [x] 검증 통과 확인

#### Task 1.2.4: 유닛 테스트 작성
- **우선순위**: P1
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] 올바른 TOML 로드 테스트
  - [x] 잘못된 TOML 에러 테스트
  - [x] 순환 의존성 감지 테스트
  - [x] 기본값 테스트

---

### Sprint 1.3: 프로세스 관리 (4일)

#### Task 1.3.1: ProcessManager 구조체
- **우선순위**: P0
- **예상 시간**: 4시간
- **파일**: `src/process.rs`
- **체크리스트**:
  - [x] `ProcessManager` 구조체
  - [x] `ManagedProcess` 구조체
  - [x] `ProcessState` enum (Stopped, Starting, Running, Stopping, Failed)
  - [x] 프로세스 목록 관리 (HashMap)

#### Task 1.3.2: 프로세스 시작 (spawn)
- **우선순위**: P0
- **예상 시간**: 4시간
- **체크리스트**:
  - [x] `start_process()` 함수
  - [x] `tokio::process::Command` 사용
  - [x] 작업 디렉토리 설정
  - [x] 환경 변수 주입
  - [x] PID 저장
  - [x] 에러 처리

**코드 스켈레톤**:
```rust
async fn start_process(&mut self, name: &str) -> Result<()> {
    let config = self.get_process_config(name)?;

    let mut cmd = Command::new(&config.command);
    cmd.args(&config.args)
       .current_dir(&config.working_dir)
       .envs(&config.env);

    let child = cmd.spawn()?;
    let pid = child.id().ok_or(anyhow!("No PID"))?;

    // ManagedProcess 업데이트
    // ...

    Ok(())
}
```

#### Task 1.3.3: 프로세스 중지 (stop)
- **우선순위**: P0
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] `stop_process()` 함수
  - [x] Graceful shutdown (SIGTERM)
  - [x] 타임아웃 후 강제 종료 (SIGKILL)
  - [x] Windows 호환성 처리
  - [x] 상태 업데이트

#### Task 1.3.4: 프로세스 재시작
- **우선순위**: P0
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] `restart_process()` 함수
  - [x] stop → wait → start 순서
  - [x] 재시작 횟수 카운트
  - [x] 백오프 딜레이 적용

#### Task 1.3.5: 유닛 테스트
- **우선순위**: P1
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] 프로세스 시작 테스트
  - [x] 프로세스 중지 테스트
  - [x] 재시작 테스트
  - [x] 존재하지 않는 명령어 테스트

---

### Sprint 1.4: 의존성 및 순차 시작 (4일)

#### Task 1.4.1: 의존성 그래프 해석
- **우선순위**: P0
- **예상 시간**: 4시간
- **체크리스트**:
  - [x] Topological sort 구현
  - [x] 순환 의존성 감지
  - [x] 시작 순서 결정
  - [x] 에러 처리

#### Task 1.4.2: 준비 상태 감지 - 로그 패턴
- **우선순위**: P0
- **예상 시간**: 5시간
- **의존성**: `regex`, `notify` crate 추가
- **체크리스트**:
  - [x] 로그 파일 tail 구현
  - [x] Regex 패턴 매칭
  - [x] 타임아웃 처리
  - [x] 로그 버퍼링 고려

**코드 스켈레톤**:
```rust
async fn wait_for_log_pattern(
    log_file: &Path,
    pattern: &str,
    timeout: Duration
) -> Result<()> {
    let regex = Regex::new(pattern)?;
    let start = Instant::now();

    // tail -f 구현
    while start.elapsed() < timeout {
        if let Ok(line) = read_new_line(log_file).await {
            if regex.is_match(&line) {
                return Ok(());
            }
        }
        sleep(Duration::from_millis(100)).await;
    }

    Err(anyhow!("Timeout waiting for pattern: {}", pattern))
}
```

#### Task 1.4.3: 준비 상태 감지 - 포트
- **우선순위**: P1
- **예상 시간**: 3시간
- **의존성**: `tokio::net` 사용
- **체크리스트**:
  - [x] TCP 포트 연결 시도
  - [x] 타임아웃 처리
  - [x] 재시도 로직

#### Task 1.4.4: 준비 상태 감지 - 시간
- **우선순위**: P2
- **예상 시간**: 1시간
- **체크리스트**:
  - [x] 고정 시간 대기 (fallback)
  - [x] `tokio::time::sleep` 사용

#### Task 1.4.5: 순차 시작 통합
- **우선순위**: P0
- **예상 시간**: 4시간
- **체크리스트**:
  - [x] `start_all()` 함수 구현
  - [x] 의존성 순서대로 시작
  - [x] 각 프로세스 준비 대기
  - [x] 에러 발생 시 롤백

#### Task 1.4.6: 통합 테스트
- **우선순위**: P0
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] 순차 시작 테스트 (mock 프로세스)
  - [x] 의존성 준비 확인 테스트
  - [x] 타임아웃 테스트
  - [x] 에러 케이스 테스트

---

### Sprint 1.5: CLI 명령어 (3일)

#### Task 1.5.1: CLI 구조 설계
- **우선순위**: P0
- **예상 시간**: 3시간
- **파일**: `src/main.rs`
- **의존성**: `clap` crate
- **체크리스트**:
  - [x] 명령어 구조 정의
    - `start`: 모든 프로세스 시작
    - `stop`: 모든 프로세스 중지
    - `restart`: 재시작
    - `status`: 상태 확인
    - `logs`: 로그 확인
  - [x] Subcommand derive 적용
  - [x] 공통 옵션 (`--config`)

**코드 스켈레톤**:
```rust
#[derive(Parser)]
#[command(name = "oc-guardian")]
struct Cli {
    #[command(subcommand)]
    command: Commands,

    #[arg(short, long, default_value = "guardian.toml")]
    config: String,
}

#[derive(Subcommand)]
enum Commands {
    Start,
    Stop,
    Restart { process: Option<String> },
    Status,
    Logs {
        process: Option<String>,
        #[arg(short, long)]
        follow: bool,
    },
}
```

#### Task 1.5.2: start/stop/restart 구현
- **우선순위**: P0
- **예상 시간**: 4시간
- **체크리스트**:
  - [x] `handle_start()` 구현
  - [x] `handle_stop()` 구현
  - [x] `handle_restart()` 구현
  - [x] ProcessManager 연동
  - [x] 에러 메시지 개선

#### Task 1.5.3: status 명령어
- **우선순위**: P0
- **예상 시간**: 4시간
- **의존성**: `tabled` or `comfy-table` crate
- **체크리스트**:
  - [x] 프로세스 목록 조회
  - [x] 테이블 형식 출력
  - [x] 상태별 색상 (online=녹색, failed=빨강)
  - [x] 헬스체크 상태 포함

**출력 예시**:
```
┌───────────┬────────┬──────┬──────────┬─────────┬───────────┐
│ Name      │ Status │ PID  │ Uptime   │ Restarts│ Health    │
├───────────┼────────┼──────┼──────────┼─────────┼───────────┤
│ openclaw  │ online │ 1234 │ 10m 5s   │ 0       │ ✓ Healthy │
│ oc-memory │ online │ 5678 │ 9m 55s   │ 0       │ ✓ Healthy │
└───────────┴────────┴──────┴──────────┴─────────┴───────────┘
```

#### Task 1.5.4: logs 명령어
- **우선순위**: P1
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] 로그 파일 읽기
  - [x] `--follow` 옵션 (tail -f)
  - [x] `--tail N` 옵션
  - [x] 색상 출력

#### Task 1.5.5: CLI 테스트
- **우선순위**: P1
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] 각 명령어 수동 테스트
  - [x] 도움말 메시지 확인
  - [x] 에러 케이스 테스트

---

### Sprint 1.6: 기본 헬스체크 (2일)

#### Task 1.6.1: HealthChecker 구조체
- **우선순위**: P0
- **예상 시간**: 3시간
- **파일**: `src/health.rs`
- **체크리스트**:
  - [x] `HealthChecker` 구조체
  - [x] `HealthStatus` enum
  - [x] Level 1: 프로세스 존재 확인 (sysinfo)
  - [x] 헬스체크 결과 캐싱

#### Task 1.6.2: 메인 루프 통합
- **우선순위**: P0
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] Supervisor main loop 구현
  - [x] 주기적 헬스체크 (5초마다)
  - [x] 상태 업데이트
  - [x] 헬스체크 실패 시 로그

#### Task 1.6.3: 유닛 테스트
- **우선순위**: P1
- **예상 시간**: 2시간

---

### Phase 1 완료 기준

- [x] 프로세스 시작/중지/재시작 동작
- [x] 의존성 기반 순차 시작 동작
- [x] 로그 패턴으로 준비 상태 감지
- [x] CLI 명령어 모두 동작
- [x] 기본 헬스체크 동작
- [x] 유닛 테스트 통과율 80% 이상
- [x] OpenClaw + OC-Memory 실제 관리 테스트 성공

---

## 📋 Phase 2: 고급 헬스체크 & 복구 (2-3주)

### 목표
멀티 레벨 헬스체크 + 시나리오 기반 자동 복구

### Sprint 2.1: 로그 모니터링 (3일)

#### Task 2.1.1: 로그 파일 tail 구현
- **우선순위**: P0
- **예상 시간**: 4시간
- **의존성**: `notify` crate (파일 시스템 감시)
- **체크리스트**:
  - [x] 파일 변경 감지
  - [x] 새로운 라인만 읽기
  - [x] 로그 로테이션 처리
  - [x] 버퍼링 고려

#### Task 2.1.2: 로그 활성도 체크
- **우선순위**: P0
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] 마지막 로그 시간 추적
  - [x] 타임아웃 체크 (예: 5분)
  - [x] 정상 idle 상태 구분

#### Task 2.1.3: 로그 패턴 매칭 (고급)
- **우선순위**: P1
- **예상 시간**: 3시간
- **의존성**: `regex` crate
- **체크리스트**:
  - [x] 에러 패턴 감지
  - [x] 경고 패턴 감지
  - [x] 커스텀 패턴 설정

---

### Sprint 2.2: JSON 설정 검증 (2일)

#### Task 2.2.1: JSON 파서
- **우선순위**: P0
- **예상 시간**: 3시간
- **의존성**: `serde_json` crate
- **체크리스트**:
  - [x] JSON 파일 읽기
  - [x] 파싱 검증
  - [x] 에러 위치 표시

#### Task 2.2.2: 자동 백업
- **우선순위**: P0
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] 변경 전 백업 생성
  - [x] 세대별 백업 (최대 5개)
  - [x] 백업 파일 로테이션

#### Task 2.2.3: 자동 롤백
- **우선순위**: P0
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] 검증 실패 시 복원
  - [x] 복원 성공 확인
  - [x] 알림 전송

---

### Sprint 2.3: 메모리/CPU 모니터링 (2일)

#### Task 2.3.1: 리소스 사용량 측정
- **우선순위**: P0
- **예상 시간**: 3시간
- **의존성**: `sysinfo` crate
- **체크리스트**:
  - [x] CPU 사용률 측정
  - [x] 메모리 사용량 측정 (RSS)
  - [x] 주기적 측정 (30초마다)

#### Task 2.3.2: 임계값 체크
- **우선순위**: P0
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] 설정된 임계값과 비교
  - [x] 지속 시간 체크 (sustained)
  - [x] 경고/에러 분리

---

### Sprint 2.4: HTTP 헬스 엔드포인트 (2일)

#### Task 2.4.1: HTTP 클라이언트 구현
- **우선순위**: P1
- **예상 시간**: 3시간
- **의존성**: `reqwest` crate
- **체크리스트**:
  - [x] HTTP GET 요청
  - [x] 타임아웃 설정
  - [x] 응답 코드 확인
  - [x] 재시도 로직

#### Task 2.4.2: 헬스체크 통합
- **우선순위**: P1
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] 주기적 체크 (60초마다)
  - [x] 실패 시 카운트
  - [x] 연속 실패 임계값

---

### Sprint 2.5: 시나리오 기반 복구 (4일)

#### Task 2.5.1: RecoveryEngine 구조체
- **우선순위**: P0
- **예상 시간**: 4시간
- **파일**: `src/recovery.rs`
- **체크리스트**:
  - [x] `RecoveryEngine` 구조체
  - [x] `RecoveryScenario` 매칭
  - [x] 트리거 조건 평가

#### Task 2.5.2: 복구 액션 구현
- **우선순위**: P0
- **예상 시간**: 6시간
- **체크리스트**:
  - [x] `restore_backup`: 백업 복원
  - [x] `restart_with_dependencies`: 의존성 포함 재시작
  - [x] `graceful_restart`: Graceful shutdown + 재시작
  - [x] `exponential_backoff`: 지수 백오프
  - [x] `log_warning`: 로그만 기록

#### Task 2.5.3: 6가지 시나리오 구현
- **우선순위**: P0
- **예상 시간**: 6시간
- **체크리스트**:
  - [x] invalid_json (JSON 오류)
  - [x] process_crash (프로세스 크래시)
  - [x] unresponsive (무반응)
  - [x] memory_leak (메모리 누수)
  - [x] network_timeout (네트워크 타임아웃)
  - [x] llm_error (LLM 에러 - 로그만)

#### Task 2.5.4: 복구 통계 수집
- **우선순위**: P1
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] 복구 횟수 기록
  - [x] 복구 성공/실패 추적
  - [x] 통계 로그 출력

#### Task 2.5.5: 통합 테스트
- **우선순위**: P0
- **예상 시간**: 4시간
- **체크리스트**:
  - [x] 각 시나리오 테스트
  - [x] 복구 액션 동작 확인
  - [x] 엣지 케이스 테스트

---

### Sprint 2.6: Graceful Shutdown (2일)

#### Task 2.6.1: 시그널 처리
- **우선순위**: P0
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] SIGTERM 전송
  - [x] 타임아웃 대기 (grace_period)
  - [x] SIGKILL 전송 (타임아웃 시)
  - [x] Windows 호환성

#### Task 2.6.2: 종료 순서 관리
- **우선순위**: P0
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] 의존성 역순으로 종료
  - [x] 각 프로세스 종료 확인
  - [x] 타임아웃 처리

---

### Phase 2 완료 기준

- [x] 5단계 헬스체크 모두 동작
- [x] 6가지 복구 시나리오 동작
- [x] JSON 자동 백업/복원 동작
- [x] Graceful shutdown 동작
- [x] 통합 테스트 통과율 85% 이상

---

## 📋 Phase 3: OC-Memory 통합 (1-2주)

### 목표
OC-Memory 프로젝트에 Guardian 통합 + 추가 기능

### Sprint 3.1: 프로젝트 구조 재구성 (2일)

#### Task 3.1.1: 폴더 구조 생성
- **우선순위**: P0
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] `guardian/` 폴더 생성
  - [x] Rust 프로젝트 이동
  - [x] `scripts/` 폴더 생성
  - [x] `.gitignore` 업데이트

#### Task 3.1.2: 빌드 스크립트 작성
- **우선순위**: P0
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] `scripts/build.sh` 작성
  - [x] 크로스 컴파일 설정
  - [x] 빌드 결과 복사

---

### Sprint 3.2: 설치 스크립트 (3일)

#### Task 3.2.1: install.sh 작성
- **우선순위**: P0
- **예상 시간**: 4시간
- **파일**: `scripts/install.sh`
- **체크리스트**:
  - [x] Rust 설치 확인
  - [x] Python 의존성 설치
  - [x] Guardian 빌드
  - [x] 설정 파일 생성
  - [x] 경로 자동 설정
  - [x] 실행 권한 부여

#### Task 3.2.2: install.ps1 작성 (Windows)
- **우선순위**: P0
- **예상 시간**: 4시간
- **파일**: `scripts/install.ps1`
- **체크리스트**:
  - [x] Windows 환경 체크
  - [x] PowerShell 스크립트 작성
  - [x] 동일 기능 구현

#### Task 3.2.3: 테스트
- **우선순위**: P0
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] macOS 테스트
  - [x] Linux 테스트
  - [x] Windows 테스트

---

### Sprint 3.3: 로그 로테이션 (2일)

#### Task 3.3.1: lib/log_rotation.py 작성
- **우선순위**: P0
- **예상 시간**: 3시간
- **파일**: `lib/log_rotation.py`
- **체크리스트**:
  - [x] `LogRotator` 클래스
  - [x] 크기 기반 로테이션
  - [x] gzip 압축
  - [x] 세대별 백업 관리

#### Task 3.3.2: Guardian에서 호출
- **우선순위**: P0
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] 주기적 로그 로테이션 (1시간마다)
  - [x] Python 스크립트 호출
  - [x] 에러 처리

---

### Sprint 3.4: 메모리 압축 전략 (3일)

#### Task 3.4.1: 압축 매니저 구현
- **우선순위**: P0
- **예상 시간**: 5시간
- **파일**: `src/compression.rs` (신규)
- **체크리스트**:
  - [x] `CompressionManager` 구조체
  - [x] 토큰 카운트 함수
  - [x] 이중 트리거 로직
    - 트리거 1: 토큰 임계값 (30,000)
    - 트리거 2: 24시간 스케줄

#### Task 3.4.2: Observer/Reflector 호출
- **우선순위**: P0
- **예상 시간**: 4시간
- **체크리스트**:
  - [x] Python Observer 호출
  - [x] LLM API 파라미터 전달
  - [x] 압축 결과 검증
  - [x] 압축 비율 계산

#### Task 3.4.3: 압축 통계 로깅
- **우선순위**: P1
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] JSON 형식 로그
  - [x] 압축 전/후 토큰 수
  - [x] 압축 비율
  - [x] 소요 시간

#### Task 3.4.4: 테스트
- **우선순위**: P0
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] 토큰 임계값 트리거 테스트
  - [x] 24시간 스케줄 테스트
  - [x] 스마트 건너뜀 테스트

---

### Sprint 3.5: macOS 슬립 방지 (2일)

#### Task 3.5.1: caffeinate 구현
- **우선순위**: P0
- **예상 시간**: 3시간
- **파일**: `src/macos.rs` (신규)
- **체크리스트**:
  - [x] `#[cfg(target_os = "macos")]` 조건 컴파일
  - [x] `caffeinate -di` 실행
  - [x] 프로세스 관리

#### Task 3.5.2: pmset 구현 (대안)
- **우선순위**: P2
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] `sudo pmset -c disablesleep 1` 실행
  - [x] 종료 시 복원
  - [x] sudo 권한 체크

#### Task 3.5.3: 설정 통합
- **우선순위**: P0
- **예상 시간**: 1시간
- **체크리스트**:
  - [x] `guardian.toml`에 `[macos]` 섹션
  - [x] Guardian 시작 시 자동 실행
  - [x] Guardian 종료 시 복원

---

### Sprint 3.6: Email 알림 (2일)

#### Task 3.6.1: SMTP 클라이언트
- **우선순위**: P1
- **예상 시간**: 4시간
- **의존성**: `lettre` crate
- **체크리스트**:
  - [x] SMTP 연결
  - [x] TLS 지원
  - [x] 인증 처리
  - [x] 이메일 전송

#### Task 3.6.2: 알림 템플릿
- **우선순위**: P1
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] 제목 템플릿
  - [x] 본문 템플릿
  - [x] 변수 치환 ({event_type}, {process_name} 등)

#### Task 3.6.3: 이벤트 연동
- **우선순위**: P1
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] 복구 시나리오에서 호출
  - [x] 비동기 전송
  - [x] 에러 처리 (전송 실패 시 로그만)

---

### Phase 3 완료 기준

- [x] OC-Memory 프로젝트에 통합 완료
- [x] 설치 스크립트 3개 플랫폼 동작
- [x] 로그 로테이션 동작
- [x] 메모리 압축 이중 트리거 동작
- [x] macOS 슬립 방지 동작
- [x] Email 알림 동작

---

## 📋 Phase 4: 프로덕션 준비 (1주)

### Sprint 4.1: 성능 최적화 (2일)

#### Task 4.1.1: 프로파일링
- **우선순위**: P1
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] `cargo flamegraph` 실행
  - [x] 병목 지점 식별
  - [x] 메모리 사용량 측정

#### Task 4.1.2: 최적화
- **우선순위**: P1
- **예상 시간**: 4시간
- **체크리스트**:
  - [x] 불필요한 클론 제거
  - [x] Arc/Mutex 최적화
  - [x] 비동기 작업 개선

---

### Sprint 4.2: 크로스 플랫폼 테스트 (2일)

#### Task 4.2.1: Windows 테스트
- **우선순위**: P0
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] 빌드 테스트
  - [x] 실행 테스트
  - [x] 프로세스 관리 테스트
  - [x] 시그널 처리 테스트

#### Task 4.2.2: macOS 테스트
- **우선순위**: P0
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] 동일 테스트
  - [x] caffeinate 기능 테스트

#### Task 4.2.3: Linux 테스트
- **우선순위**: P0
- **예상 시간**: 2시간

---

### Sprint 4.3: 시스템 서비스 등록 (2일)

#### Task 4.3.1: systemd service (Linux)
- **우선순위**: P1
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] service 파일 템플릿 작성
  - [x] `install-service` 명령어 구현
  - [x] 자동 시작 설정

#### Task 4.3.2: LaunchAgent (macOS)
- **우선순위**: P1
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] plist 파일 템플릿
  - [x] `install-service` 명령어 구현

#### Task 4.3.3: Windows Service
- **우선순위**: P1
- **예상 시간**: 4시간
- **체크리스트**:
  - [x] Windows Service API 사용
  - [x] `install-service` 명령어 구현

---

### Sprint 4.4: 문서화 (1일)

#### Task 4.4.1: README 업데이트
- **우선순위**: P0
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] OC-Memory README에 Guardian 추가
  - [x] 빠른 시작 가이드
  - [x] AI 친화적 구조

#### Task 4.4.2: QUICKSTART.md
- **우선순위**: P0
- **예상 시간**: 1시간

#### Task 4.4.3: guardian/README.md
- **우선순위**: P1
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] Guardian 상세 문서
  - [x] 설정 가이드
  - [x] 트러블슈팅

---

### Sprint 4.5: 릴리스 빌드 (1일)

#### Task 4.5.1: 릴리스 설정
- **우선순위**: P0
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] `Cargo.toml` 최적화
  - [x] 바이너리 크기 최소화
  - [x] Strip symbols

#### Task 4.5.2: 크로스 컴파일
- **우선순위**: P0
- **예상 시간**: 3시간
- **체크리스트**:
  - [x] Windows (x86_64)
  - [x] macOS (x86_64, arm64)
  - [x] Linux (x86_64)

#### Task 4.5.3: GitHub Release
- **우선순위**: P1
- **예상 시간**: 2시간
- **체크리스트**:
  - [x] Release 노트 작성
  - [x] 바이너리 업로드
  - [x] 체크섬 제공

---

### Phase 4 완료 기준

- [x] 3개 플랫폼 모두 빌드 및 동작
- [x] 시스템 서비스 등록 동작
- [x] 문서화 완료
- [x] GitHub Release 완료
- [x] 성능 기준 만족 (메모리 < 5MB)

---

## 📊 전체 일정 요약

| Phase | 기간 | 주요 산출물 |
|-------|------|------------|
| **Phase 1** | 2-3주 | 기본 프로세스 관리 + CLI |
| **Phase 2** | 2-3주 | 고급 헬스체크 + 복구 |
| **Phase 3** | 1-2주 | OC-Memory 통합 + 추가 기능 |
| **Phase 4** | 1주 | 프로덕션 준비 + 릴리스 |
| **총계** | **7-9주** | **OC-Guardian v1.0** |

---

## 🎯 우선순위 정리

### P0 (Critical) - 필수 기능
- 프로세스 관리 (시작/중지/재시작)
- 순차 시작 (의존성 기반)
- 준비 상태 감지 (로그 패턴)
- CLI 명령어
- 기본 헬스체크
- 복구 시나리오 (6가지)
- 설치 스크립트
- 메모리 압축 (이중 트리거)

### P1 (High) - 중요 기능
- HTTP 헬스체크
- Email 알림
- macOS 슬립 방지
- 시스템 서비스 등록

### P2 (Medium) - 선택 기능
- pmset 구현 (caffeinate 대안)
- 고급 로그 패턴 매칭

### P3 (Low) - 추후 개선
- 웹 대시보드
- 메트릭 수집

---

## 🚨 리스크 관리

| 리스크 | 확률 | 영향 | 완화 방안 |
|--------|------|------|-----------|
| Rust 학습 곡선 | 중 | 중 | 템플릿 제공, 단계별 구현 |
| 크로스 플랫폼 이슈 | 중 | 높 | 조건부 컴파일, 각 플랫폼 테스트 |
| OpenClaw 로그 형식 변경 | 낮 | 중 | 설정 가능한 패턴 |
| LLM API 장애 | 중 | 중 | 재시도 로직, Fallback |
| 의존성 순환 | 낮 | 높 | 설정 검증 단계에서 차단 |

---

## ✅ 최종 체크리스트

### Phase 1 완료
- [x] Rust 프로젝트 설정
- [x] TOML 설정 파싱
- [x] 프로세스 관리
- [x] 순차 시작
- [x] CLI 명령어
- [x] 기본 헬스체크

### Phase 2 완료
- [x] 로그 모니터링
- [x] JSON 검증
- [x] 리소스 모니터링
- [x] HTTP 헬스체크
- [x] 복구 시나리오
- [x] Graceful shutdown

### Phase 3 완료
- [x] 프로젝트 통합
- [x] 설치 스크립트
- [x] 로그 로테이션
- [x] 메모리 압축
- [x] macOS 슬립 방지
- [x] Email 알림

### Phase 4 완료
- [x] 성능 최적화
- [x] 크로스 플랫폼 테스트
- [x] 시스템 서비스
- [x] 문서화
- [x] 릴리스 빌드

---

**Task 문서 작성 완료!**
**총 예상 기간: 7-9주**
**개발 시작 준비 완료**
