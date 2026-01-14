# Gemini 프롬프트 엔지니어링 가이드

**Project:** High-Win Survival System
**작성일:** 2025.12.15

---

## 1. 프롬프트 설계 철학

### 1.1 핵심 원칙

```
승률 > 손익비

→ "확실할 때만 진입"
→ "애매하면 WAIT"
→ "한 방보다 꾸준한 적중"
```

### 1.2 AI의 역할

| 역할 | 설명 |
|------|------|
| 방향 예측 | 다음 2시간 내 가격 방향 |
| 확신도 판단 | 진입할 만큼 확실한가? |
| 노이즈 필터 | 횡보/불확실 구간 회피 |

**AI가 하지 않는 것:**
- 정확한 가격 예측 (X)
- 익절/손절가 계산 (X) → 고정값 사용
- 레버리지 조정 (X) → 고정값 사용

---

## 2. 시스템 프롬프트

### 2.1 기본 시스템 프롬프트

```
You are a Bitcoin futures trading analyst specialized in short-term price direction prediction.

Your ONLY job is to predict the price direction for the next 1-2 hours.

## Core Principles

1. **High Win Rate Priority**
   - Only signal when you have HIGH CONFIDENCE (>65%)
   - When uncertain, ALWAYS output WAIT
   - It's better to miss opportunities than to enter bad trades

2. **Output Format**
   You must respond with EXACTLY ONE of these three words:
   - LONG: Price will go UP in the next 1-2 hours
   - SHORT: Price will go DOWN in the next 1-2 hours
   - WAIT: Uncertain or sideways market - DO NOT TRADE

3. **WAIT Conditions** (Output WAIT if ANY of these apply)
   - RSI between 40-60 (neutral zone)
   - Price consolidating near moving averages
   - Low volume or decreasing volume
   - Conflicting signals between indicators
   - Major support/resistance nearby causing uncertainty
   - Recent high volatility spike (potential reversal)

4. **LONG Conditions** (ALL must apply)
   - Clear bullish momentum
   - RSI recovering from oversold OR strong uptrend (55-70)
   - Price above short-term MA or breaking above
   - Increasing buy volume
   - No major resistance immediately above

5. **SHORT Conditions** (ALL must apply)
   - Clear bearish momentum
   - RSI falling from overbought OR strong downtrend (30-45)
   - Price below short-term MA or breaking below
   - Increasing sell volume
   - No major support immediately below

## Important Rules

- NEVER explain your reasoning
- NEVER add any text besides LONG, SHORT, or WAIT
- When in doubt, output WAIT
- Prioritize WIN RATE over profit potential
```

---

## 3. 데이터 입력 포맷

### 3.1 Market Data Prompt

```
## Current Market Data (BTCUSDT Perpetual)

### Price Action (Last 2 Hours, 5-min candles)
{candle_summary}

### Current State
- Current Price: ${current_price}
- 24h High: ${high_24h}
- 24h Low: ${low_24h}
- 24h Change: {change_24h}%

### Technical Indicators
- RSI (14): {rsi}
- RSI Trend: {rsi_trend} (rising/falling/flat)
- MA7: ${ma_7}
- MA25: ${ma_25}
- MA99: ${ma_99}
- Price vs MA7: {price_vs_ma7}% (above/below)
- Price vs MA25: {price_vs_ma25}% (above/below)

### Volume Analysis
- Current Volume: {current_volume}
- Avg Volume (24h): {avg_volume}
- Volume Ratio: {volume_ratio}x
- Volume Trend: {volume_trend} (increasing/decreasing)

### Volatility
- ATR (14): ${atr}
- ATR %: {atr_pct}%
- Volatility State: {volatility_state} (low/normal/high)

### Key Levels
- Nearest Resistance: ${resistance}
- Nearest Support: ${support}
- Distance to Resistance: {dist_resistance}%
- Distance to Support: {dist_support}%

Based on this data, output your signal (LONG, SHORT, or WAIT):
```

---

## 4. 캔들 데이터 요약 방식

### 4.1 간결한 요약 (토큰 절약)

```python
def summarize_candles(df: pd.DataFrame) -> str:
    """최근 24개 캔들 (2시간) 요약"""

    # 추세 판단
    first_close = df.iloc[0]['close']
    last_close = df.iloc[-1]['close']
    trend_pct = ((last_close - first_close) / first_close) * 100

    # 최근 모멘텀 (마지막 6개 캔들 = 30분)
    recent_df = df.tail(6)
    recent_trend = ((recent_df.iloc[-1]['close'] - recent_df.iloc[0]['close'])
                    / recent_df.iloc[0]['close']) * 100

    # 캔들 패턴 카운트
    bullish = sum(1 for _, row in df.iterrows() if row['close'] > row['open'])
    bearish = len(df) - bullish

    summary = f"""
2-Hour Trend: {'+' if trend_pct > 0 else ''}{trend_pct:.2f}%
Recent 30min: {'+' if recent_trend > 0 else ''}{recent_trend:.2f}%
Candle Count: {bullish} bullish / {bearish} bearish
Highest: ${df['high'].max():,.0f}
Lowest: ${df['low'].min():,.0f}
"""
    return summary
```

### 4.2 상세 요약 (정확도 우선)

```python
def detailed_candle_summary(df: pd.DataFrame) -> str:
    """6개 구간으로 나눠서 요약 (각 20분)"""

    summaries = []
    chunk_size = 4  # 4개 캔들 = 20분

    for i in range(0, len(df), chunk_size):
        chunk = df.iloc[i:i+chunk_size]
        if len(chunk) == 0:
            continue

        open_price = chunk.iloc[0]['open']
        close_price = chunk.iloc[-1]['close']
        high = chunk['high'].max()
        low = chunk['low'].min()
        volume = chunk['volume'].sum()

        direction = "↑" if close_price > open_price else "↓"
        change = ((close_price - open_price) / open_price) * 100

        summaries.append(
            f"{direction} {change:+.2f}% (H:${high:,.0f} L:${low:,.0f})"
        )

    return "\n".join(summaries)
```

---

## 5. RSI 해석 가이드

### 5.1 RSI 구간별 해석

```
RSI 구간과 시그널 매핑:

[0-20]   극단적 과매도 → LONG 고려 (반등 기대)
[20-30]  과매도 → LONG 우세
[30-40]  약한 하락 → 상황 봐서 판단
[40-60]  중립 → WAIT (진입 금지)
[60-70]  약한 상승 → 상황 봐서 판단
[70-80]  과매수 → SHORT 우세
[80-100] 극단적 과매수 → SHORT 고려 (하락 기대)
```

### 5.2 RSI + 추세 조합

| RSI | 가격 추세 | 신호 |
|-----|----------|------|
| <30 | 하락 둔화 | LONG |
| <30 | 계속 하락 | WAIT (낙하산 금지) |
| >70 | 상승 둔화 | SHORT |
| >70 | 계속 상승 | WAIT (FOMO 금지) |
| 40-60 | 어떤 추세든 | WAIT |

---

## 6. 볼륨 해석 가이드

### 6.1 볼륨 비율 기준

```
Volume Ratio = Current Volume / 24h Average Volume

[0.0-0.5]  매우 낮음 → WAIT (유동성 부족)
[0.5-0.8]  낮음 → WAIT 권장
[0.8-1.2]  정상 → 신호 유효
[1.2-2.0]  높음 → 신호 강화
[2.0+]     급등 → 주의 (변동성 경고)
```

### 6.2 볼륨 + 가격 조합

| 가격 | 볼륨 | 해석 |
|------|------|------|
| ↑ | ↑ | 강한 상승 (LONG 유리) |
| ↑ | ↓ | 약한 상승 (지속 의문) |
| ↓ | ↑ | 강한 하락 (SHORT 유리) |
| ↓ | ↓ | 약한 하락 (반등 가능) |

---

## 7. WAIT 판단 기준 (핵심)

### 7.1 WAIT 우선 조건들

```python
def should_wait(indicators: dict) -> tuple[bool, str]:
    """WAIT 조건 체크 - 하나라도 해당되면 WAIT"""

    reasons = []

    # 1. RSI 중립 구간
    if 40 <= indicators['rsi'] <= 60:
        reasons.append("RSI in neutral zone (40-60)")

    # 2. 낮은 볼륨
    if indicators['volume_ratio'] < 0.7:
        reasons.append("Low volume")

    # 3. MA 수렴 (횡보)
    ma_spread = abs(indicators['ma7'] - indicators['ma25']) / indicators['ma25'] * 100
    if ma_spread < 0.3:
        reasons.append("MAs converging (sideways)")

    # 4. 가격이 MA 사이에 끼임
    price = indicators['current_price']
    ma7, ma25 = indicators['ma7'], indicators['ma25']
    if min(ma7, ma25) < price < max(ma7, ma25):
        reasons.append("Price between MAs")

    # 5. 높은 변동성 (노이즈)
    if indicators['atr_pct'] > 1.5:
        reasons.append("High volatility (ATR > 1.5%)")

    # 6. 주요 지지/저항 근접
    if indicators['dist_resistance'] < 0.3 and indicators['dist_support'] < 0.3:
        reasons.append("Near both support and resistance")

    # 7. 지표 충돌
    rsi_signal = "bullish" if indicators['rsi'] < 40 else "bearish" if indicators['rsi'] > 60 else "neutral"
    ma_signal = "bullish" if indicators['current_price'] > indicators['ma25'] else "bearish"
    if rsi_signal != "neutral" and rsi_signal != ma_signal:
        reasons.append("Conflicting RSI and MA signals")

    return len(reasons) > 0, reasons
```

### 7.2 WAIT 비중 목표

```
목표 신호 분포:

WAIT:  40-50%  ← 불확실할 땐 진입 안 함
LONG:  25-30%
SHORT: 25-30%

WAIT가 30% 미만이면 → 프롬프트 조정 필요 (너무 공격적)
WAIT가 60% 초과이면 → 프롬프트 조정 필요 (너무 보수적)
```

---

## 8. 프롬프트 버전 관리

### 8.1 버전별 프롬프트

```python
PROMPT_VERSIONS = {
    "v1.0": {
        "name": "기본 버전",
        "description": "초기 테스트용",
        "system_prompt": "...",
        "expected_wait_ratio": 0.4,
    },
    "v1.1": {
        "name": "WAIT 강화",
        "description": "더 보수적인 진입",
        "system_prompt": "...",
        "expected_wait_ratio": 0.5,
    },
}

CURRENT_VERSION = "v1.0"
```

### 8.2 프롬프트 A/B 테스트

```python
async def ab_test_prompts(market_data: dict) -> dict:
    """두 버전의 프롬프트 동시 테스트"""

    results = {}
    for version, config in PROMPT_VERSIONS.items():
        signal = await get_gemini_signal(
            system_prompt=config['system_prompt'],
            market_data=market_data
        )
        results[version] = signal

    # 로그 기록
    log_ab_test(market_data, results)

    # 현재 버전 신호 반환
    return results[CURRENT_VERSION]
```

---

## 9. Gemini API 호출

### 9.1 기본 호출 코드

```python
import google.generativeai as genai
from loguru import logger

class GeminiSignalGenerator:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",  # 빠른 응답
            generation_config={
                "temperature": 0.1,  # 낮은 온도 = 일관된 응답
                "top_p": 0.8,
                "max_output_tokens": 10,  # LONG/SHORT/WAIT만 필요
            }
        )
        self.system_prompt = SYSTEM_PROMPT

    async def get_signal(self, market_data: dict) -> str:
        """매매 신호 생성"""

        try:
            # 프롬프트 구성
            user_prompt = self._build_market_prompt(market_data)
            full_prompt = f"{self.system_prompt}\n\n{user_prompt}"

            # API 호출
            response = await self.model.generate_content_async(full_prompt)

            # 응답 파싱
            signal = response.text.strip().upper()

            # 유효성 검사
            if signal not in ["LONG", "SHORT", "WAIT"]:
                logger.warning(f"Invalid signal: {signal}, defaulting to WAIT")
                return "WAIT"

            logger.info(f"Signal generated: {signal}")
            return signal

        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return "WAIT"  # 에러 시 안전하게 WAIT

    def _build_market_prompt(self, data: dict) -> str:
        """마켓 데이터 프롬프트 생성"""
        # ... (섹션 3의 포맷 사용)
```

### 9.2 모델 선택

| 모델 | 속도 | 비용 | 용도 |
|------|------|------|------|
| gemini-1.5-flash | 빠름 | 저렴 | **실시간 트레이딩 (권장)** |
| gemini-1.5-pro | 보통 | 중간 | 복잡한 분석 필요 시 |
| gemini-1.0-pro | 빠름 | 저렴 | 백테스트 대량 처리 |

---

## 10. 프롬프트 튜닝 가이드

### 10.1 승률이 낮을 때

```
문제: 승률 < 55%

해결책:
1. WAIT 조건 추가
   - RSI 중립 구간 확대 (35-65)
   - 볼륨 기준 상향 (0.8 → 1.0)

2. 진입 조건 강화
   - "HIGH CONFIDENCE" → "VERY HIGH CONFIDENCE"
   - 복수 지표 일치 요구

3. Temperature 낮추기
   - 0.1 → 0.05 (더 일관된 응답)
```

### 10.2 WAIT가 너무 많을 때

```
문제: WAIT > 60%

해결책:
1. WAIT 조건 완화
   - RSI 중립 구간 축소 (45-55)
   - 볼륨 기준 하향 (0.8 → 0.6)

2. 진입 조건 완화
   - "ALL must apply" → "MOST must apply"

3. Temperature 높이기
   - 0.1 → 0.2 (더 다양한 판단)
```

### 10.3 특정 방향 편향

```
문제: LONG 비율 >> SHORT 비율 (또는 반대)

해결책:
1. 프롬프트에 균형 명시
   "Maintain roughly equal LONG and SHORT signals over time"

2. 조건 대칭성 확인
   - LONG 조건과 SHORT 조건이 동일한 엄격함인지 체크
```

---

## 11. 백테스트 검증

### 11.1 신호 품질 메트릭

```python
def evaluate_signals(signals: list, prices: list) -> dict:
    """신호 품질 평가"""

    results = {
        'total': len(signals),
        'long': 0, 'short': 0, 'wait': 0,
        'long_win': 0, 'short_win': 0,
        'long_loss': 0, 'short_loss': 0,
    }

    for i, signal in enumerate(signals):
        if signal == 'WAIT':
            results['wait'] += 1
            continue

        # 2시간 후 가격 변화
        entry_price = prices[i]
        exit_price = prices[i + 24]  # 24개 5분봉 = 2시간
        change = (exit_price - entry_price) / entry_price

        if signal == 'LONG':
            results['long'] += 1
            if change > 0.0035:  # TP 도달
                results['long_win'] += 1
            elif change < -0.0055:  # SL 도달
                results['long_loss'] += 1

        elif signal == 'SHORT':
            results['short'] += 1
            if change < -0.0035:  # TP 도달
                results['short_win'] += 1
            elif change > 0.0055:  # SL 도달
                results['short_loss'] += 1

    # 승률 계산
    total_trades = results['long'] + results['short']
    total_wins = results['long_win'] + results['short_win']
    results['win_rate'] = total_wins / total_trades if total_trades > 0 else 0
    results['wait_ratio'] = results['wait'] / results['total']

    return results
```

### 11.2 목표 메트릭

```
승률: > 60%
WAIT 비율: 40-50%
LONG/SHORT 비율: 0.8 ~ 1.2 (균형)
연속 손실: < 5회
```

---

## 12. 프롬프트 체크리스트

### 배포 전 확인사항

- [ ] 출력이 정확히 LONG/SHORT/WAIT 중 하나인가?
- [ ] WAIT 조건이 충분히 명시되어 있는가?
- [ ] Temperature가 낮게 설정되어 있는가? (< 0.2)
- [ ] 백테스트 승률이 55% 이상인가?
- [ ] WAIT 비율이 40-50% 범위인가?
- [ ] 에러 시 기본값이 WAIT인가?
- [ ] 토큰 사용량이 합리적인가?

---

## 13. 다음 단계

1. **Phase 3에서 구현**
   - Gemini API 연동
   - 프롬프트 템플릿 적용
   - 백테스트로 승률 검증

2. **튜닝 반복**
   - 백테스트 결과 기반 프롬프트 조정
   - A/B 테스트로 최적 버전 선택
