"""
리스크 매니저 모듈

Phase 5: 리스크 관리 강화
- 일일 손실 한도 (-5% 시 전체 봇 정지)
- 연속 손실 카운터 (3연패 시 휴식)
- 드로다운 모니터링
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from loguru import logger


class RiskManager:
    """리스크 매니저

    봇의 리스크를 관리하는 클래스입니다.
    일일 손실 한도, 연속 손실 카운터, 최대 드로다운 등을 추적합니다.

    Phase 5.2: 일일 손실 한도 (-5% 시 전체 봇 정지)
    Phase 5.3: 연속 손실 카운터 (3연패 시 휴식)

    Attributes:
        max_daily_loss_pct: 일일 최대 손실률 (기본 5%)
        max_drawdown_pct: 최대 드로다운 (기본 10%)
        max_consecutive_losses: 최대 연속 손실 횟수 (기본 3회)
        cooldown_minutes: 연속 손실 후 휴식 시간 (기본 30분)

    Example:
        >>> risk_manager = RiskManager(max_daily_loss_pct=0.05)
        >>> await risk_manager.reset_daily_stats(10000.0)
        >>> await risk_manager.track_trade_pnl(-100.0)
        >>> halt, reason = await risk_manager.should_halt_trading()
    """

    def __init__(
        self,
        max_daily_loss_pct: float = 0.05,
        max_drawdown_pct: float = 0.10,
        max_consecutive_losses: int = 3,
        cooldown_minutes: int = 30,
    ) -> None:
        """리스크 매니저 초기화

        Args:
            max_daily_loss_pct: 일일 최대 손실률 (0.05 = 5%)
            max_drawdown_pct: 최대 드로다운 (0.10 = 10%)
            max_consecutive_losses: 최대 연속 손실 횟수
            cooldown_minutes: 연속 손실 후 휴식 시간 (분)
        """
        # 설정
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_minutes = cooldown_minutes

        # 일일 통계
        self._daily_pnl: float = 0.0
        self._daily_start_balance: float = 0.0
        self._daily_reset_time: Optional[datetime] = None

        # 연속 손실 추적
        self._consecutive_losses: int = 0
        self._cooldown_until: Optional[datetime] = None

        # 드로다운 추적
        self._peak_balance: float = 0.0
        self._current_drawdown: float = 0.0

        # 거래 통계
        self._total_trades: int = 0
        self._winning_trades: int = 0
        self._losing_trades: int = 0

        logger.info(
            f"RiskManager 초기화: max_daily_loss={max_daily_loss_pct*100}%, "
            f"max_consecutive_losses={max_consecutive_losses}"
        )

    # =========================================================================
    # 일일 손실 관리 (Phase 5.2)
    # =========================================================================

    async def reset_daily_stats(self, current_balance: float) -> None:
        """일일 통계 리셋 (매일 UTC 00:00 또는 봇 시작 시 호출)

        Args:
            current_balance: 현재 잔고
        """
        self._daily_pnl = 0.0
        self._daily_start_balance = current_balance
        self._daily_reset_time = datetime.now(timezone.utc)

        # Peak balance 업데이트
        if current_balance > self._peak_balance:
            self._peak_balance = current_balance

        logger.info(
            f"일일 통계 리셋: 시작 잔고=${current_balance:,.2f}, "
            f"리셋 시간={self._daily_reset_time.isoformat()}"
        )

    async def track_trade_pnl(self, pnl: float) -> None:
        """거래 PnL 추적

        Args:
            pnl: 실현 손익 (양수=이익, 음수=손실)
        """
        self._daily_pnl += pnl
        self._total_trades += 1

        if pnl >= 0:
            self._winning_trades += 1
        else:
            self._losing_trades += 1

        logger.info(
            f"PnL 기록: {pnl:+,.2f} USDT, 일일 누적={self._daily_pnl:+,.2f} USDT"
        )

    async def track_trade_result(self, is_win: bool) -> None:
        """거래 결과 추적 (연속 손실 카운터용)

        Args:
            is_win: 승리 여부
        """
        if is_win:
            self._consecutive_losses = 0
            logger.debug("승리 - 연속 손실 카운터 리셋")
        else:
            self._consecutive_losses += 1
            logger.warning(f"손실 - 연속 손실 카운터: {self._consecutive_losses}")

            # 연속 손실 한도 도달 시 쿨다운 설정
            if self._consecutive_losses >= self.max_consecutive_losses:
                self._cooldown_until = datetime.now(timezone.utc) + timedelta(
                    minutes=self.cooldown_minutes
                )
                logger.warning(
                    f"연속 손실 한도 도달 ({self._consecutive_losses}회), "
                    f"쿨다운 시작: {self._cooldown_until.isoformat()} 까지"
                )

    async def should_halt_trading(self) -> Tuple[bool, str]:
        """거래 중단 여부 확인

        Returns:
            (중단 여부, 중단 사유)
        """
        # 시작 잔고가 설정되지 않은 경우
        if self._daily_start_balance <= 0:
            return False, ""

        # 일일 손실률 계산
        daily_loss_pct = abs(self._daily_pnl) / self._daily_start_balance

        # 일일 손실 한도 체크
        if self._daily_pnl < 0 and daily_loss_pct >= self.max_daily_loss_pct:
            reason = f"일일 손실 한도 도달: {daily_loss_pct:.2%} >= {self.max_daily_loss_pct:.2%}"
            logger.warning(reason)
            return True, reason

        return False, ""

    async def is_in_cooldown(self) -> bool:
        """쿨다운 상태 확인 (Phase 5.3)

        Returns:
            쿨다운 중이면 True
        """
        if self._cooldown_until is None:
            return False

        now = datetime.now(timezone.utc)
        if now < self._cooldown_until:
            remaining = (self._cooldown_until - now).total_seconds() / 60
            logger.info(f"쿨다운 중: 잔여 시간 {remaining:.1f}분")
            return True

        # 쿨다운 종료
        self._cooldown_until = None
        self._consecutive_losses = 0  # 쿨다운 후 리셋
        logger.info("쿨다운 종료 - 거래 재개 가능")
        return False

    # =========================================================================
    # 드로다운 관리
    # =========================================================================

    async def update_balance(self, current_balance: float) -> None:
        """잔고 업데이트 및 드로다운 계산

        Args:
            current_balance: 현재 잔고
        """
        # Peak balance 업데이트
        if current_balance > self._peak_balance:
            self._peak_balance = current_balance

        # 드로다운 계산
        if self._peak_balance > 0:
            self._current_drawdown = (
                self._peak_balance - current_balance
            ) / self._peak_balance

    async def check_max_drawdown(self) -> Tuple[bool, str]:
        """최대 드로다운 체크

        Returns:
            (한도 도달 여부, 사유)
        """
        if self._current_drawdown >= self.max_drawdown_pct:
            reason = (
                f"최대 드로다운 도달: {self._current_drawdown:.2%} >= "
                f"{self.max_drawdown_pct:.2%}"
            )
            logger.warning(reason)
            return True, reason

        return False, ""

    # =========================================================================
    # 상태 조회
    # =========================================================================

    def get_daily_pnl(self) -> float:
        """일일 PnL 조회"""
        return self._daily_pnl

    def get_daily_pnl_pct(self) -> float:
        """일일 PnL 비율 조회"""
        if self._daily_start_balance <= 0:
            return 0.0
        return self._daily_pnl / self._daily_start_balance

    def get_consecutive_losses(self) -> int:
        """연속 손실 횟수 조회"""
        return self._consecutive_losses

    def get_current_drawdown(self) -> float:
        """현재 드로다운 조회"""
        return self._current_drawdown

    def get_stats(self) -> dict:
        """전체 통계 조회

        Returns:
            리스크 통계 딕셔너리
        """
        win_rate = 0.0
        if self._total_trades > 0:
            win_rate = self._winning_trades / self._total_trades

        return {
            "daily_pnl": self._daily_pnl,
            "daily_pnl_pct": self.get_daily_pnl_pct(),
            "daily_start_balance": self._daily_start_balance,
            "consecutive_losses": self._consecutive_losses,
            "cooldown_until": self._cooldown_until.isoformat() if self._cooldown_until else None,
            "current_drawdown": self._current_drawdown,
            "peak_balance": self._peak_balance,
            "total_trades": self._total_trades,
            "winning_trades": self._winning_trades,
            "losing_trades": self._losing_trades,
            "win_rate": win_rate,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_consecutive_losses": self.max_consecutive_losses,
            "max_drawdown_pct": self.max_drawdown_pct,
        }

    def reset_consecutive_losses(self) -> None:
        """연속 손실 카운터 수동 리셋"""
        self._consecutive_losses = 0
        self._cooldown_until = None
        logger.info("연속 손실 카운터 수동 리셋")

    async def should_skip_trade(self) -> Tuple[bool, str]:
        """거래 스킵 여부 확인 (통합 체크)

        쿨다운 및 일일 손실 한도를 한번에 체크합니다.

        Returns:
            (스킵 여부, 사유)
        """
        # 쿨다운 체크
        if await self.is_in_cooldown():
            remaining: float = 0.0
            if self._cooldown_until:
                remaining = (
                    self._cooldown_until - datetime.now(timezone.utc)
                ).total_seconds() / 60
            return True, f"쿨다운 중 (잔여 {remaining:.1f}분)"

        # 일일 손실 한도 체크
        halt, reason = await self.should_halt_trading()
        if halt:
            return True, reason

        # 드로다운 체크
        dd_halt, dd_reason = await self.check_max_drawdown()
        if dd_halt:
            return True, dd_reason

        return False, ""
