# Testing Guide

테스트 가이드입니다.

---

## 🧪 테스트 실행

### 빠른 실행

```bash
# Bash 스크립트 (권장)
./scripts/run-tests.sh

# 또는 직접 pytest 실행
pytest

# 또는 Python 모듈로 실행
python -m pytest
```

### 옵션

```bash
# 커버리지 없이 실행 (빠름)
./scripts/run-tests.sh --no-cov

# Verbose 모드
./scripts/run-tests.sh --verbose

# 특정 파일만 실행
pytest tests/test_config.py

# 특정 테스트만 실행
pytest tests/test_config.py::TestTradingConfig::test_config_creation_with_valid_data

# 마커로 필터링
pytest -m unit            # Unit 테스트만
pytest -m "not slow"      # 느린 테스트 제외
```

---

## 📊 코드 커버리지

테스트 실행 후 커버리지 리포트가 생성됩니다.

### 터미널에서 확인

```bash
pytest
# 자동으로 커버리지 표시됨
```

### HTML 리포트 확인

```bash
# 테스트 실행 후
open htmlcov/index.html   # Mac
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

---

## 📁 테스트 구조

```
tests/                           # 60개 테스트 파일, 1860+ 테스트 케이스
├── conftest.py                  # pytest 설정 및 공통 fixtures
├── test_config.py               # 설정 관리
├── test_bot_config.py           # 멀티봇 설정 모델
├── test_bot_instance*.py        # 봇 인스턴스 (통합, 루프 등)
├── test_executor*.py            # 주문 실행 + 안전장치
├── test_risk_manager.py         # 리스크 관리
├── test_trade_approval.py       # 수동 승인 시스템
├── test_indicators.py           # 기술적 지표
├── test_regime_detector.py      # 마켓 레짐 감지
├── test_multi_timeframe.py      # 다중 타임프레임
├── test_gemini*.py              # Gemini AI 클라이언트
├── test_ensemble*.py            # 앙상블 시그널
├── test_signals.py              # 신호 파싱
├── test_binance*.py             # Binance API
├── test_trade_history.py        # PostgreSQL 거래 기록
├── test_redis_state.py          # Redis 상태
├── test_audit_log.py            # 감사 로그
├── test_observability.py        # Prometheus + 로깅
├── test_discord_*.py            # Discord 봇 + 권한
├── test_api_*.py                # REST API + 미들웨어
├── test_backtest*.py            # 백테스트 엔진
└── ...                          # Phase 7-9 전용 테스트
```

**총 1860+ 테스트 케이스 (60개 파일)**

---

## 🎯 테스트 커버리지 목표

| 모듈 | 목표 커버리지 | 설명 |
|------|--------------|------|
| `src/trading/` | 95%+ | 주문 실행, 리스크 관리 |
| `src/exchange/` | 95%+ | Binance API 연동 |
| `src/ai/` | 90%+ | AI 신호 생성 |
| `src/data/` | 90%+ | 기술적 지표, 레짐 감지 |

---

## 📝 테스트 모듈별 요약

| 모듈 | 테스트 파일 | 주요 커버리지 |
|------|------------|--------------|
| 설정 | test_config, test_bot_config | 환경변수, Pydantic 모델, risk_level 기본값 |
| 봇 인스턴스 | test_bot_instance* | 트레이딩 루프, MTF 통합, 앙상블, 메트릭 |
| 주문 실행 | test_executor* | 진입/청산, TP/SL, PnL 계산, 안전장치 |
| 리스크 관리 | test_risk_manager | 일일 한도, 쿨다운, 드로다운, 수수료, 직렬화 |
| 수동 승인 | test_trade_approval | 승인 워크플로우, 타임아웃 |
| 기술적 지표 | test_indicators | RSI, MA, ATR, 볼륨, 캔들 패턴 |
| 레짐 감지 | test_regime_detector | 추세/횡보 분류, ATR 기반 강도 |
| 다중 TF | test_multi_timeframe | 상위 TF 필터링, 추세 일치/충돌 |
| AI 신호 | test_gemini*, test_ensemble*, test_signals | Gemini API, 앙상블, 신호 파싱 |
| Binance | test_binance* | API 클라이언트, Circuit Breaker, 재시도 |
| DB/Redis | test_trade_history, test_redis_state | PostgreSQL 거래 기록, Redis 상태 |
| 감사 로그 | test_audit_log | 이벤트 기록, 인메모리 폴백 |
| 모니터링 | test_observability | Prometheus 메트릭, 로깅 파이프라인 |
| Discord | test_discord_* | 명령어, 권한, 뷰, 임베드 |
| API | test_api_* | REST 엔드포인트, 인증, Rate Limiting |
| 백테스트 | test_backtest* | 시뮬레이션, 슬리피지 |

---

## 🚀 CI/CD 통합

GitHub Actions에서 자동 테스트:

```yaml
# .github/workflows/ci.yml
- name: Run tests
  run: |
    pip install -r requirements.txt
    pytest
```

---

## 💡 테스트 작성 가이드

### 1. Unit Test 작성

```python
def test_function_name():
    """테스트 설명"""
    # Arrange (준비)
    input_data = "test"

    # Act (실행)
    result = function(input_data)

    # Assert (검증)
    assert result == expected
```

### 2. Async Test 작성

```python
@pytest.mark.asyncio
async def test_async_function():
    """비동기 함수 테스트"""
    result = await async_function()
    assert result is not None
```

### 3. Mock 사용

```python
from unittest.mock import Mock, AsyncMock

def test_with_mock():
    """Mock을 사용한 테스트"""
    mock_client = Mock()
    mock_client.method = AsyncMock(return_value="mocked")

    result = await function_using_client(mock_client)

    mock_client.method.assert_called_once()
```

### 4. Fixture 사용

```python
@pytest.fixture
def sample_data():
    """재사용 가능한 테스트 데이터"""
    return {"key": "value"}

def test_with_fixture(sample_data):
    assert sample_data["key"] == "value"
```

---

## 🐛 디버깅

### 실패한 테스트만 재실행

```bash
pytest --lf  # last-failed
```

### 특정 테스트에 breakpoint

```python
def test_debug():
    import pdb; pdb.set_trace()  # 여기서 중단
    result = function()
```

### Verbose 출력

```bash
pytest -vv -s  # 모든 print 출력 표시
```

---

---

**테스트 커버리지 현황:**
- 총 1860+ 테스트 작성 완료 (60개 파일)
- 전체 커버리지: 90%+
- 모든 테스트 통과 ✅
