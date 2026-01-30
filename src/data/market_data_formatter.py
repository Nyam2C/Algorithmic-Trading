"""
Gemini API용 시장 데이터 포맷터

토큰 효율성을 위해 시장 데이터를 압축 포맷으로 변환
목표: ~100 토큰 이하로 모든 필수 정보 전달
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class CompactMarketData:
    """압축된 시장 데이터 구조"""

    # 가격 정보
    price: int                    # 현재가 (정수)
    change_24h: float             # 24시간 변동률
    high_24h: int                 # 24시간 고가
    low_24h: int                  # 24시간 저가

    # 기술적 지표
    rsi: int                      # RSI (정수)
    rsi_trend: str                # RSI 추세 (↑/↓/→)
    ma_position: str              # MA 대비 위치 (상/중/하)
    trend_2h: float               # 2시간 추세 (%)

    # 거래량
    volume_ratio: float           # 거래량 비율

    # 변동성
    volatility: str               # 변동성 상태 (낮음/보통/높음)

    # 시장 심리 (선택)
    funding_rate: Optional[float] = None   # 펀딩비 (%)
    long_short_ratio: Optional[float] = None  # 롱숏 비율

    # 포지션 정보
    position: str = "없음"        # 현재 포지션 (LONG/SHORT/없음)
    entry_price: Optional[int] = None  # 진입가
    unrealized_pnl_pct: Optional[float] = None  # 미실현 손익률

    def to_compact_string(self) -> str:
        """
        압축 문자열 포맷으로 변환

        예시:
        BTC $106,500 | 24h: +2.3% (고:108k 저:104k)
        RSI:45↑ | MA:상 | 추세:+1.2% | 거래량:1.5x | 변동성:보통
        펀딩:+0.01% | 롱숏:52:48
        포지션:없음
        """
        lines = []

        # 1줄: 가격 정보
        high_k = f"{self.high_24h // 1000}k"
        low_k = f"{self.low_24h // 1000}k"
        lines.append(
            f"BTC ${self.price:,} | 24h: {self.change_24h:+.1f}% (고:{high_k} 저:{low_k})"
        )

        # 2줄: 기술적 지표
        lines.append(
            f"RSI:{self.rsi}{self.rsi_trend} | MA:{self.ma_position} | "
            f"추세:{self.trend_2h:+.1f}% | 거래량:{self.volume_ratio:.1f}x | 변동성:{self.volatility}"
        )

        # 3줄: 시장 심리 (있는 경우만)
        sentiment_parts = []
        if self.funding_rate is not None:
            sentiment_parts.append(f"펀딩:{self.funding_rate:+.3f}%")
        if self.long_short_ratio is not None:
            long_pct = int(self.long_short_ratio * 100 / (self.long_short_ratio + 1))
            short_pct = 100 - long_pct
            sentiment_parts.append(f"롱숏:{long_pct}:{short_pct}")

        if sentiment_parts:
            lines.append(" | ".join(sentiment_parts))

        # 4줄: 포지션 정보
        if self.position != "없음" and self.entry_price:
            lines.append(
                f"포지션:{self.position} @ ${self.entry_price:,} "
                f"({self.unrealized_pnl_pct:+.2f}%)"
            )
        else:
            lines.append("포지션:없음")

        return "\n".join(lines)

    def to_minimal_string(self) -> str:
        """
        최소 토큰 포맷 (~50 토큰)

        예시:
        BTC|106500|+2.3%|RSI:45↑|MA:상|Vol:1.5x|펀딩:+0.01%|포지션:없음
        """
        parts = [
            "BTC",
            str(self.price),
            f"{self.change_24h:+.1f}%",
            f"RSI:{self.rsi}{self.rsi_trend}",
            f"MA:{self.ma_position}",
            f"Vol:{self.volume_ratio:.1f}x",
        ]

        if self.funding_rate is not None:
            parts.append(f"펀딩:{self.funding_rate:+.3f}%")

        if self.position != "없음":
            parts.append(f"포지션:{self.position}({self.unrealized_pnl_pct:+.1f}%)")
        else:
            parts.append("포지션:없음")

        return "|".join(parts)


class MarketDataFormatter:
    """시장 데이터를 Gemini API용으로 포맷팅"""

    def __init__(self):
        self.last_data: Optional[CompactMarketData] = None

    def format_for_gemini(
        self,
        market_data: Dict[str, Any],
        position: Optional[Dict[str, Any]] = None,
        funding_rate: Optional[float] = None,
        long_short_ratio: Optional[float] = None,
        minimal: bool = False
    ) -> str:
        """
        시장 데이터를 Gemini API용 문자열로 변환

        Args:
            market_data: indicators.py의 analyze_market() 결과
            position: 현재 포지션 정보
            funding_rate: 펀딩비 (%)
            long_short_ratio: 롱숏 비율
            minimal: True면 최소 토큰 포맷 사용

        Returns:
            압축된 시장 데이터 문자열
        """
        # RSI 추세 기호 변환
        rsi_trend_map = {
            "rising": "↑",
            "falling": "↓",
            "neutral": "→",
        }
        rsi_trend = rsi_trend_map.get(
            market_data.get("rsi_trend", "neutral"), "→"
        )

        # MA 위치 변환
        ma_pos = market_data.get("price_vs_ma7_pos", "middle")
        ma_position_map = {
            "above": "상",
            "below": "하",
            "middle": "중",
        }
        ma_position = ma_position_map.get(ma_pos, "중")

        # 변동성 상태 변환
        volatility_map = {
            "low": "낮음",
            "normal": "보통",
            "high": "높음",
            "extreme": "극심",
        }
        volatility = volatility_map.get(
            market_data.get("volatility_state", "normal"), "보통"
        )

        # 포지션 정보 처리
        pos_side = "없음"
        entry_price = None
        unrealized_pnl_pct = None

        if position:
            pos_side = position.get("side", "없음")
            entry_price = int(position.get("entry_price", 0))

            # 미실현 손익률 계산
            if entry_price > 0:
                current_price = market_data.get("current_price", entry_price)
                if pos_side == "LONG":
                    unrealized_pnl_pct = (current_price - entry_price) / entry_price * 100
                else:
                    unrealized_pnl_pct = (entry_price - current_price) / entry_price * 100

        # CompactMarketData 생성
        compact_data = CompactMarketData(
            price=int(market_data.get("current_price", 0)),
            change_24h=market_data.get("change_24h_pct", 0),
            high_24h=int(market_data.get("high_24h", 0)),
            low_24h=int(market_data.get("low_24h", 0)),
            rsi=int(market_data.get("rsi", 50)),
            rsi_trend=rsi_trend,
            ma_position=ma_position,
            trend_2h=market_data.get("trend_2h_pct", 0),
            volume_ratio=market_data.get("volume_ratio", 1.0),
            volatility=volatility,
            funding_rate=funding_rate,
            long_short_ratio=long_short_ratio,
            position=pos_side,
            entry_price=entry_price,
            unrealized_pnl_pct=unrealized_pnl_pct,
        )

        self.last_data = compact_data

        if minimal:
            result = compact_data.to_minimal_string()
        else:
            result = compact_data.to_compact_string()

        logger.debug(f"포맷된 시장 데이터: {result}")
        return result

    def build_gemini_prompt(
        self,
        market_data: Dict[str, Any],
        position: Optional[Dict[str, Any]] = None,
        funding_rate: Optional[float] = None,
        long_short_ratio: Optional[float] = None,
    ) -> str:
        """
        Gemini API용 완전한 프롬프트 생성

        Returns:
            시스템 지시 + 데이터 + 질문 포함 프롬프트
        """
        data_str = self.format_for_gemini(
            market_data, position, funding_rate, long_short_ratio
        )

        prompt = f"""당신은 비트코인 선물 트레이딩 전문가입니다.
아래 시장 데이터를 분석하고 1-2시간 내 포지션을 추천하세요.

[시장 데이터]
{data_str}

[규칙]
- LONG: 상승 예상 (확신도 65% 이상)
- SHORT: 하락 예상 (확신도 65% 이상)
- WAIT: 불확실하거나 횡보 예상

[응답 형식]
신호: LONG/SHORT/WAIT
이유: (한 문장)"""

        return prompt

    def estimate_tokens(self, text: str) -> int:
        """
        대략적인 토큰 수 추정 (영어 기준 4문자 = 1토큰)
        한글은 약 2문자 = 1토큰
        """
        # 간단한 추정: 공백으로 분리된 단어 수 + 특수문자
        words = text.split()
        return len(words) + len(text) // 4


# 싱글톤 인스턴스
formatter = MarketDataFormatter()


def format_market_data(
    market_data: Dict[str, Any],
    position: Optional[Dict[str, Any]] = None,
    funding_rate: Optional[float] = None,
    long_short_ratio: Optional[float] = None,
    minimal: bool = False
) -> str:
    """
    시장 데이터를 Gemini용 문자열로 포맷팅 (편의 함수)
    """
    return formatter.format_for_gemini(
        market_data, position, funding_rate, long_short_ratio, minimal
    )


def build_gemini_prompt(
    market_data: Dict[str, Any],
    position: Optional[Dict[str, Any]] = None,
    funding_rate: Optional[float] = None,
    long_short_ratio: Optional[float] = None,
) -> str:
    """
    Gemini API용 프롬프트 생성 (편의 함수)
    """
    return formatter.build_gemini_prompt(
        market_data, position, funding_rate, long_short_ratio
    )
