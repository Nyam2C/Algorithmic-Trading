"""리스크 매니저 모듈.

Phase 5: 리스크 관리 강화
- 일일 손실 한도 (-5% 시 전체 봇 정지)
- 연속 손실 카운터 (3연패 시 휴식)
- 드로다운 모니터링
"""
from datetime import datetime, timedelta, timezone

from loguru import logger

# 드로다운 임계값
_DD_TIER1_THRESHOLD = 0.05
_DD_MAX_THRESHOLD = 0.10


class RiskManager:
    """리스크 매니저.

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
        """리스크 매니저 초기화.

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
        self._daily_reset_time: datetime | None = None

        # 연속 손실 추적
        self._consecutive_losses: int = 0
        self._cooldown_until: datetime | None = None

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

    async def reset_daily_stats(
        self, current_balance: float, unrealized_pnl: float = 0.0
    ) -> None:
        """일일 통계 리셋 (매일 UTC 00:00 또는 봇 시작 시 호출).

        Phase 8: 미실현 손실이 있으면 다음 날로 이월합니다.

        Args:
            current_balance: 현재 잔고
            unrealized_pnl: 미실현 손익 (음수=미실현 손실, 이월됨)
        """
        # Phase 8: 미실현 손실 이월
        if unrealized_pnl < 0:
            self._daily_pnl = unrealized_pnl
        else:
            self._daily_pnl = 0.0
        self._daily_start_balance = current_balance
        self._daily_reset_time = datetime.now(timezone.utc)

        # Peak balance 업데이트
        self._peak_balance = max(self._peak_balance, current_balance)

        logger.info(
            f"일일 통계 리셋: 시작 잔고=${current_balance:,.2f}, "
            f"이월 PnL=${self._daily_pnl:+,.2f}, "
            f"리셋 시간={self._daily_reset_time.isoformat()}"
        )


    async def check_and_reset_if_new_day(
        self, current_balance: float, unrealized_pnl: float = 0.0
    ) -> bool:
        """UTC 자정 경과 시 일일 통계 자동 리셋.

        매 루프 반복마다 호출하여, 마지막 리셋 이후 UTC 자정을 넘었으면
        자동으로 일일 통계를 리셋합니다.

        Phase 8: 미실현 손실 이월 지원.

        Args:
            current_balance: 현재 잔고
            unrealized_pnl: 미실현 손익 (음수=미실현 손실, 이월됨)

        Returns:
            리셋 수행 여부 (True = 리셋함)
        """
        now = datetime.now(timezone.utc)

        if self._daily_reset_time is None:
            # 최초 호출: 리셋 수행
            await self.reset_daily_stats(current_balance, unrealized_pnl)
            return True

        # 마지막 리셋 날짜와 현재 날짜 비교
        if now.date() > self._daily_reset_time.date():
            logger.info(
                f"새로운 거래일 감지 (UTC {now.date()}), 일일 통계 리셋"
            )
            await self.reset_daily_stats(current_balance, unrealized_pnl)
            return True

        return False

    async def track_trade_pnl(self, pnl: float) -> None:
        """거래 PnL 추적.

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
        """거래 결과 추적 (연속 손실 카운터용).

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

    async def validate_position_risk(
        self,
        stop_loss_pct: float,
        leverage: int,
        max_loss_per_trade_pct: float = 0.02,
    ) -> tuple[bool, str]:
        """단일 거래 리스크 검증.

        진입 전 단일 거래의 예상 최대 손실이 허용 범위 내인지 확인합니다.

        Args:
            stop_loss_pct: 손절 비율 (0.004 = 0.4%)
            leverage: 레버리지
            max_loss_per_trade_pct: 최대 허용 단일 거래 손실률

        Returns:
            (허용 여부, 사유)
        """
        potential_loss = stop_loss_pct * leverage
        if potential_loss > max_loss_per_trade_pct:
            reason = (
                f"단일 거래 리스크 초과: SL({stop_loss_pct:.2%}) x "
                f"레버리지({leverage}x) = {potential_loss:.2%} > "
                f"한도({max_loss_per_trade_pct:.2%})"
            )
            logger.warning(reason)
            return False, reason
        return True, ""

    async def should_halt_trading(
        self, unrealized_pnl: float = 0.0
    ) -> tuple[bool, str]:
        """거래 중단 여부 확인.

        Args:
            unrealized_pnl: 미실현 손익 (음수=미실현 손실)

        Returns:
            (중단 여부, 중단 사유)
        """
        # 일일 손실 한도 체크 (시작 잔고가 설정된 경우만)
        if self._daily_start_balance > 0:
            # Phase 8: 순 PnL 기반 일일 손실 판단
            net_pnl = self._daily_pnl + min(unrealized_pnl, 0.0)
            if net_pnl < 0:
                daily_loss_pct = abs(net_pnl) / self._daily_start_balance
                if daily_loss_pct >= self.max_daily_loss_pct:
                    reason = (
                        f"일일 손실 한도 도달: {daily_loss_pct:.2%} "
                        f">= {self.max_daily_loss_pct:.2%}"
                    )
                    logger.warning(reason)
                    return True, reason

        # Phase 9: 드로다운 체크 (PnL 양수여도 전체 드로다운은 초과 가능)
        dd_exceeded, dd_reason = await self.check_max_drawdown()
        if dd_exceeded:
            return True, dd_reason

        return False, ""

    async def is_in_cooldown(self) -> bool:
        """쿨다운 상태 확인 (Phase 5.3).

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
        """잔고 업데이트 및 드로다운 계산.

        Args:
            current_balance: 현재 잔고
        """
        # Peak balance 업데이트
        self._peak_balance = max(self._peak_balance, current_balance)

        # 드로다운 계산
        if self._peak_balance > 0:
            self._current_drawdown = (
                self._peak_balance - current_balance
            ) / self._peak_balance

    async def check_max_drawdown(self) -> tuple[bool, str]:
        """최대 드로다운 체크.

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


    def get_drawdown_size_multiplier(self) -> float:
        """연속 드로다운 기반 포지션 크기 감소 배수.

        0% DD -> 1.0, 5% DD -> 0.7, 10% DD -> 0.3.
        선형 보간 적용.

        Returns:
            포지션 크기 배수 (0.3 ~ 1.0)
        """
        dd = self._current_drawdown

        if dd <= 0:
            return 1.0
        if dd >= _DD_MAX_THRESHOLD:
            return 0.3

        # 선형 보간: 0%->1.0, 5%->0.7, 10%->0.3
        if dd <= _DD_TIER1_THRESHOLD:
            # 0% ~ 5%: 1.0 -> 0.7
            return 1.0 - (dd / _DD_TIER1_THRESHOLD) * 0.3
        # 5% ~ 10%: 0.7 -> 0.3
        return 0.7 - ((dd - _DD_TIER1_THRESHOLD) / _DD_TIER1_THRESHOLD) * 0.4

    # =========================================================================
    # 상태 직렬화 (Phase 9: 재시작 시 복구용)
    # =========================================================================

    def to_dict(self) -> dict:
        """리스크 매니저 상태를 딕셔너리로 직렬화.

        Returns:
            상태 딕셔너리 (Redis 저장용)
        """
        return {
            "daily_pnl": self._daily_pnl,
            "daily_start_balance": self._daily_start_balance,
            "daily_reset_time": (
                self._daily_reset_time.isoformat()
                if self._daily_reset_time
                else None
            ),
            "consecutive_losses": self._consecutive_losses,
            "cooldown_until": (
                self._cooldown_until.isoformat()
                if self._cooldown_until
                else None
            ),
            "peak_balance": self._peak_balance,
            "current_drawdown": self._current_drawdown,
            "total_trades": self._total_trades,
            "winning_trades": self._winning_trades,
            "losing_trades": self._losing_trades,
        }

    def from_dict(self, state: dict) -> None:
        """딕셔너리에서 리스크 매니저 상태 복원.

        Args:
            state: to_dict()로 저장된 상태 딕셔너리
        """
        self._daily_pnl = state.get("daily_pnl", self._daily_pnl)
        self._daily_start_balance = state.get(
            "daily_start_balance", self._daily_start_balance
        )

        reset_time = state.get("daily_reset_time")
        if reset_time and isinstance(reset_time, str):
            self._daily_reset_time = datetime.fromisoformat(reset_time)
        elif reset_time is None:
            self._daily_reset_time = None

        self._consecutive_losses = state.get(
            "consecutive_losses", self._consecutive_losses
        )

        cooldown = state.get("cooldown_until")
        if cooldown and isinstance(cooldown, str):
            self._cooldown_until = datetime.fromisoformat(cooldown)
        elif cooldown is None:
            self._cooldown_until = None

        self._peak_balance = state.get("peak_balance", self._peak_balance)
        self._current_drawdown = state.get(
            "current_drawdown", self._current_drawdown
        )
        self._total_trades = state.get("total_trades", self._total_trades)
        self._winning_trades = state.get("winning_trades", self._winning_trades)
        self._losing_trades = state.get("losing_trades", self._losing_trades)

        logger.info(
            f"RiskManager 상태 복원: daily_pnl={self._daily_pnl:+,.2f}, "
            f"trades={self._total_trades}, drawdown={self._current_drawdown:.2%}"
        )

    # =========================================================================
    # 상태 조회
    # =========================================================================

    def get_daily_pnl(self) -> float:
        """일일 PnL 조회."""
        return self._daily_pnl

    def get_daily_pnl_pct(self) -> float:
        """일일 PnL 비율 조회."""
        if self._daily_start_balance <= 0:
            return 0.0
        return self._daily_pnl / self._daily_start_balance

    def get_consecutive_losses(self) -> int:
        """연속 손실 횟수 조회."""
        return self._consecutive_losses

    def get_current_drawdown(self) -> float:
        """현재 드로다운 조회."""
        return self._current_drawdown

    def get_stats(self) -> dict:
        """전체 통계 조회.

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
            "cooldown_until": (
                self._cooldown_until.isoformat()
                if self._cooldown_until
                else None
            ),
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
        """연속 손실 카운터 수동 리셋."""
        self._consecutive_losses = 0
        self._cooldown_until = None
        logger.info("연속 손실 카운터 수동 리셋")

    async def should_skip_trade(
        self, unrealized_pnl: float = 0.0
    ) -> tuple[bool, str]:
        """거래 스킵 여부 확인 (통합 체크).

        쿨다운 및 일일 손실 한도를 한번에 체크합니다.

        Args:
            unrealized_pnl: 미실현 손익 (음수=미실현 손실)

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

        # 일일 손실 한도 체크 (미실현 손익 포함)
        halt, reason = await self.should_halt_trading(unrealized_pnl)
        if halt:
            return True, reason

        # 드로다운 체크
        dd_halt, dd_reason = await self.check_max_drawdown()
        if dd_halt:
            return True, dd_reason

        return False, ""
