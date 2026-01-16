# Scripts

실행 및 관리 스크립트 모음 (Bash 전용)

---

## ⭐ 올인원 CLI (권장)

### `bot.sh`
**모든 기능을 하나의 명령어로**

```bash
# 도움말
./scripts/bot.sh help

# 🚀 원-커맨드 (새로 추가!)
./scripts/bot.sh setup           # 전체 환경 설정 (최초 1회)
./scripts/bot.sh dev             # Bot + DB만 (빠름)
./scripts/bot.sh dev:monitor     # Bot + DB + Monitoring
./scripts/bot.sh dev:backend     # Bot + DB + Go API
./scripts/bot.sh dev:all         # 전체 스택
./scripts/bot.sh dev:down        # 전체 중지
./scripts/bot.sh dev:logs        # 전체 로그
./scripts/bot.sh prod            # 프로덕션 실행

# 📦 기본 실행
./scripts/bot.sh docker          # Docker로 실행 (레거시)
./scripts/bot.sh run             # 로컬 실행

# 🧪 테스트
./scripts/bot.sh test            # 전체 테스트

# 🗄️ 데이터베이스
./scripts/bot.sh db              # DB 초기화

# 🔧 관리
./scripts/bot.sh logs            # 로그 확인
./scripts/bot.sh status          # 상태 확인
./scripts/bot.sh restart         # 재시작
./scripts/bot.sh stop            # 중지
./scripts/bot.sh clean           # 정리
```

**왜 이걸 사용하나요?**
- 모든 기능을 하나의 명령어로
- 기억하기 쉬움
- 일관된 사용법
- 자동 에러 처리

---

## 📁 개별 스크립트

필요시 개별 스크립트도 직접 사용 가능:

### 🚀 `setup.sh`
**전체 환경 자동 설정**

```bash
./scripts/setup.sh --all         # 전체 설정
./scripts/setup.sh --dev         # 개발 환경만
./scripts/setup.sh --docker      # Docker만
./scripts/setup.sh --skip-tests  # 테스트 건너뛰기
```

---

### 🏃 `run.sh`
**로컬 환경에서 봇 실행**

```bash
./scripts/run.sh
```

**기능:**
- Python 버전 확인
- 의존성 자동 설치
- API 키 검증
- 봇 실행

---

### 🐳 `start-docker.sh`
**Docker 환경에서 봇 실행**

```bash
./scripts/start-docker.sh
```

**기능:**
- Docker 설치 확인
- .env 파일 검증
- Docker 이미지 빌드
- 컨테이너 시작
- 로그 스트리밍

---

### 🧪 `run-tests.sh`
**전체 테스트 스위트 실행**

```bash
./scripts/run-tests.sh
./scripts/run-tests.sh --no-cov      # 커버리지 없이
./scripts/run-tests.sh --verbose     # Verbose 모드
```

---

### 🤖 `ai_review.py`
**AI 코드 리뷰 (GitHub Actions용)**

```bash
python scripts/ai_review.py
```

CI/CD 파이프라인에서 자동으로 실행됨

---

## 🔄 워크플로우

### 최초 설정
```bash
./scripts/bot.sh setup
```

### 일상 사용
```bash
# 실행
./scripts/bot.sh docker

# 로그 확인
./scripts/bot.sh logs

# 재시작
./scripts/bot.sh restart
```

### 개발 중
```bash
# 테스트
./scripts/bot.sh test

# 로컬 실행
./scripts/bot.sh run
```

---

## 📊 명령어 비교

| bot.sh | 개별 스크립트 | 설명 |
|--------|-------------|------|
| `bot.sh setup` | `setup.sh --all` | 환경 설정 |
| `bot.sh run` | `run.sh` | 로컬 실행 |
| `bot.sh docker` | `start-docker.sh` | Docker 실행 |
| `bot.sh test` | `run-tests.sh` | 테스트 |
| `bot.sh db` | `../db/setup.sh` | DB 초기화 |
| `bot.sh logs` | `docker compose logs -f` | 로그 |
| `bot.sh status` | `docker ps` | 상태 확인 |
| `bot.sh stop` | `docker compose down` | 중지 |
| `bot.sh restart` | `docker compose restart` | 재시작 |
| `bot.sh clean` | 수동 삭제 | 정리 |

---

## 🎯 사용 예시

### 시나리오 1: 처음 시작
```bash
# 1. 환경 설정
./scripts/bot.sh setup

# 2. 실행
./scripts/bot.sh docker

# 3. 로그 확인
./scripts/bot.sh logs
```

### 시나리오 2: 코드 수정 후
```bash
# 1. 테스트
./scripts/bot.sh test

# 2. Docker 재빌드 및 실행
./scripts/bot.sh docker

# 3. 상태 확인
./scripts/bot.sh status
```

### 시나리오 3: 트러블슈팅
```bash
# 1. 로그 확인
./scripts/bot.sh logs

# 2. 재시작
./scripts/bot.sh restart

# 3. 상태 확인
./scripts/bot.sh status
```

### 시나리오 4: 정리
```bash
# 임시 파일 정리
./scripts/bot.sh clean

# 봇 중지
./scripts/bot.sh stop
```

---

## 🐛 트러블슈팅

### 실행 권한 에러
```bash
chmod +x scripts/*.sh
```

### Python 버전 에러
```bash
# Python 3.11+ 필요
python3 --version
```

### Docker 에러
```bash
# Docker 상태 확인
./scripts/bot.sh status

# Docker 재시작
sudo systemctl restart docker  # Linux
```

### 명령어를 찾을 수 없음
```bash
# 프로젝트 루트에서 실행
cd /path/to/Algorithmic-Trading
./scripts/bot.sh help
```

---

## 💡 팁

### 별칭(Alias) 설정
```bash
# ~/.bashrc 또는 ~/.zshrc에 추가
alias bot='/path/to/Algorithmic-Trading/scripts/bot.sh'

# 사용
bot setup
bot docker
bot logs
```

### 빠른 접근
```bash
# 프로젝트 루트에 심볼릭 링크
ln -s scripts/bot.sh bot

# 사용
./bot setup
./bot docker
```

---

## 📚 관련 문서

- **[../docs/SETUP_GUIDE.md](../docs/SETUP_GUIDE.md)** - 상세 설정 가이드
- **[../docs/QUICK_START.md](../docs/QUICK_START.md)** - 명령어 치트시트
- **[../docs/TEST_GUIDE.md](../docs/TEST_GUIDE.md)** - 테스트 가이드

---

## 🔮 향후 추가 예정

- `bot.sh backup` - 데이터베이스 백업
- `bot.sh restore` - 백업 복구
- `bot.sh update` - 봇 업데이트
- `bot.sh deploy` - 프로덕션 배포

---

## ⚠️ 주의사항

### Linux/Mac/WSL 전용
이 프로젝트는 Bash 스크립트를 사용합니다.

- ✅ Linux
- ✅ macOS
- ✅ WSL (Windows Subsystem for Linux)
- ❌ Windows PowerShell (WSL 설치 필요)

### Windows 사용자
WSL 설치 방법:
```powershell
# PowerShell (관리자)
wsl --install

# 또는 Ubuntu 설치
wsl --install -d Ubuntu
```

---

**스크립트 버전:** 2.0 (Bash 전용)
**마지막 업데이트:** 2026-01-16
