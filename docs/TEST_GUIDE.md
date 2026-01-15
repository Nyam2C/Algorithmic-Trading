# Testing Guide

Sprint 1 프로젝트의 테스트 가이드입니다.

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
tests/
├── conftest.py              # pytest 설정 및 공통 fixtures
├── test_config.py           # 설정 관리 테스트 (14개)
├── test_indicators.py       # 기술적 지표 테스트 (20개)
├── test_signals.py          # 신호 파싱 테스트 (12개)
└── test_executor.py         # 주문 실행 테스트 (18개)
```

**총 64개 테스트 케이스**

---

## 🎯 테스트 커버리지 목표

| 모듈 | 목표 커버리지 | 설명 |
|------|--------------|------|
| src/config.py | 90%+ | 설정 관리 |
| src/data/indicators.py | 85%+ | 지표 계산 |
| src/ai/signals.py | 100% | 신호 파싱 (단순) |
| src/trading/executor.py | 80%+ | 주문 실행 |
| src/exchange/binance.py | 70%+ | API 연동 (Mock) |
| src/ai/gemini.py | 70%+ | AI 연동 (Mock) |

---

## 📝 작성된 테스트

### 1. test_config.py

**TestTradingConfig 클래스:**
- ✅ 유효한 데이터로 설정 생성
- ✅ 심볼 대문자 변환
- ✅ 심볼이 USDT로 끝나는지 검증
- ✅ 레버리지 범위 검증 (1-125)
- ✅ 포지션 크기 검증 (0 < size <= 1)
- ✅ 기본값 테스트

**TestLoadConfig 클래스:**
- ✅ 환경 변수에서 설정 로딩
- ✅ 필수 키 없을 때 에러

**TestGetConfig 클래스:**
- ✅ 싱글톤 패턴 확인

---

### 2. test_indicators.py

**TestCalculateRSI 클래스:**
- ✅ RSI 정상 계산
- ✅ RSI 범위 검증 (0-100)
- ✅ 상승 추세에서 RSI > 50
- ✅ 하락 추세에서 RSI < 50

**TestCalculateMA 클래스:**
- ✅ MA 정상 계산
- ✅ 상승 추세에서 단기 MA > 장기 MA

**TestCalculateATR 클래스:**
- ✅ ATR 정상 계산
- ✅ ATR 양수 검증

**TestCalculateVolumeRatio 클래스:**
- ✅ 볼륨 비율 계산
- ✅ 높은 볼륨일 때 비율 > 1

**TestAnalyzeRSITrend 클래스:**
- ✅ RSI 상승/하락/횡보 감지

**TestCalculatePriceVsMA 클래스:**
- ✅ 가격이 MA 위/아래 판단

**TestAnalyzeCandlePattern 클래스:**
- ✅ 상승/하락 캔들 카운트

**TestAnalyzeMarket 클래스:**
- ✅ 전체 시장 분석 통합
- ✅ 모든 필수 키 포함 확인
- ✅ 값 범위 검증

---

### 3. test_signals.py

**TestParseSignal 클래스:**
- ✅ 단순 신호 파싱 (LONG/SHORT/WAIT)
- ✅ 소문자 → 대문자 변환
- ✅ 공백 제거
- ✅ 프리픽스 제거 (SIGNAL:, OUTPUT: 등)
- ✅ 여러 단어 중 첫 단어 추출

**TestValidateSignal 클래스:**
- ✅ 유효한 신호 검증
- ✅ 유효하지 않은 신호 거부

**TestGetSignalEmoji 클래스:**
- ✅ 신호별 이모지 반환 (🟢🔴⏸️)

**TestGetSignalColor 클래스:**
- ✅ 신호별 Discord 색상 코드

**TestShouldEnterTrade 클래스:**
- ✅ 진입 조건 판단 (신호 + 포지션 상태)

---

### 4. test_executor.py

**TestTradingExecutor 클래스:**
- ✅ 레버리지 설정
- ✅ 포지션 크기 계산
- ✅ LONG 포지션 진입
- ✅ SHORT 포지션 진입
- ✅ 기존 포지션 있을 때 진입 거부
- ✅ 포지션 청산
- ✅ 포지션 없을 때 청산 불가
- ✅ 포지션 여부 확인
- ✅ PnL 계산 (LONG 수익/손실)
- ✅ PnL 계산 (SHORT 수익/손실)
- ✅ TP 조건 체크
- ✅ SL 조건 체크
- ✅ TP/SL 미도달 시 None 반환

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

## 📈 다음 단계

Sprint 2에서 추가할 테스트:
- [ ] test_binance.py - Binance API Mock 테스트
- [ ] test_gemini.py - Gemini AI Mock 테스트
- [ ] test_integration.py - E2E 통합 테스트
- [ ] test_main.py - 메인 루프 테스트

---

**테스트 커버리지 현황:**
- 총 64개 테스트 작성 완료
- 핵심 모듈 커버리지: 85%+
- 모든 테스트 통과 ✅
