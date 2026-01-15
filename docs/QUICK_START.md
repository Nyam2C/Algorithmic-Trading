# Quick Start Cheatsheet

빠른 참조용 명령어 모음

---

## 🚀 초기 설정 (최초 1회)

```bash
# 전체 환경 설정 (권장)
./scripts/bot.sh setup --all

# 또는 대화형 모드
./scripts/bot.sh setup
```

---

## 🏃 실행

### Docker (권장)
```bash
# 시작
./scripts/bot.sh docker

# 로그 확인
docker compose logs -f bot

# 중지
docker compose down
```

### 로컬
```bash
# 시작
./scripts/bot.sh run

# 또는
python -m src.main
```

---

## 🧪 테스트

```bash
# 전체 테스트
./scripts/run-tests.sh

# 특정 테스트
pytest tests/test_config.py

# 커버리지
pytest --cov=src --cov-report=html
```

---

## 🗄️ 데이터베이스

```bash
# 초기화
./d./scripts/setup.sh

# 접속 (Docker)
docker compose exec db psql -U postgres -d trading

# 접속 (로컬)
psql -h localhost -U postgres -d trading
```

---

## 📝 주요 명령어

### 환경 설정
```bash
./scripts/bot.sh setup --all        # 전체 설정
./scripts/bot.sh setup --dev        # 개발 환경만
./scripts/bot.sh setup --docker     # Docker만
./scripts/bot.sh setup --skip-tests # 테스트 건너뛰기
```

### 실행 스크립트
```bash
./scripts/bot.sh run                # 로컬 실행
./scripts/bot.sh docker       # Docker 실행
./scripts/run-tests.sh          # 테스트 실행
./d./scripts/setup.sh   # DB 초기화
```

### Docker 명령어
```bash
docker compose build         # 이미지 빌드
docker compose up -d         # 백그라운드 실행
docker compose up            # 포그라운드 실행
docker compose down          # 중지 및 삭제
docker compose ps            # 상태 확인
docker compose logs -f bot   # 실시간 로그
docker compose restart bot   # 재시작
```

### 테스트 명령어
```bash
pytest                       # 전체 테스트
pytest -v                    # Verbose 모드
pytest -k test_config        # 특정 테스트만
pytest -m unit               # 마커로 필터링
pytest --lf                  # 실패한 테스트만
pytest --cov=src             # 커버리지
```

---

## 📂 주요 파일

### 설정
- `.env` - 환경 변수 (API 키)
- `config.py` - 설정 관리

### 실행
- `src/main.py` - 메인 엔트리포인트
- `run.sh` / `run.py` - 로컬 실행 스크립트
- `start-docker.sh` - Docker 실행 스크립트

### 테스트
- `tests/` - 테스트 파일들
- `pytest.ini` - Pytest 설정
- `.coveragerc` - 커버리지 설정

### 문서
- `README.md` - 프로젝트 개요
- `SETUP_GUIDE.md` - 설정 가이드
- `TEST_GUIDE.md` - 테스트 가이드

---

## 🔑 API 키 발급

### Binance Testnet
🔗 https://testnet.binancefuture.com
- GitHub/Google 로그인
- API Management → Create API Key

### Gemini AI
🔗 https://aistudio.google.com/apikey
- Google 계정 로그인
- Create API Key

### Discord Webhook
- 서버 설정 → 연동 → 웹후크
- 새 웹후크 → URL 복사

---

## 🛠️ 트러블슈팅

### Python 버전
```bash
python3 --version  # 3.11+ 필요
```

### Docker 상태
```bash
docker ps          # 실행 중인 컨테이너
docker compose ps  # 프로젝트 컨테이너
```

### 의존성 재설치
```bash
pip install -r requirements.txt
```

### .env 재생성
```bash
rm .env
./scripts/bot.sh setup --dev
```

### 데이터베이스 재설정
```bash
docker compose down -v  # 볼륨 삭제
./d./scripts/setup.sh
```

---

## 📊 모니터링

### 로그 확인
```bash
# Docker
docker compose logs -f bot

# 로컬
tail -f logs/bot.log
```

### 데이터베이스 쿼리
```sql
-- 최근 거래
SELECT * FROM trades ORDER BY entry_time DESC LIMIT 10;

-- AI 신호
SELECT * FROM ai_signals ORDER BY timestamp DESC LIMIT 20;

-- 봇 상태
SELECT * FROM bot_status WHERE bot_name = 'high-win-bot';
```

---

## 🎯 워크플로우

### 1. 최초 설정
```bash
git clone <repo>
cd Algorithmic-Trading
./scripts/bot.sh setup --all
```

### 2. 개발
```bash
# 코드 수정
vim src/main.py

# 테스트 실행
./scripts/run-tests.sh

# 로컬 실행
./scripts/bot.sh run
```

### 3. 배포
```bash
# Docker 빌드 및 실행
./scripts/bot.sh docker

# 로그 모니터링
docker compose logs -f bot
```

### 4. 디버깅
```bash
# 컨테이너 접속
docker compose exec bot bash

# 로그 확인
docker compose logs bot

# DB 확인
docker compose exec db psql -U postgres -d trading
```

---

## 🔄 업데이트

### 코드 업데이트 후
```bash
# 의존성 재설치
pip install -r requirements.txt

# 테스트
./scripts/run-tests.sh

# Docker 재빌드
docker compose build
docker compose up -d
```

---

**자세한 내용은 [SETUP_GUIDE.md](SETUP_GUIDE.md) 참조**
