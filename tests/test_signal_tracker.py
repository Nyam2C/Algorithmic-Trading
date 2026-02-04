"""
신호 추적 시스템 테스트

Phase 6.1: SignalTracker 테스트
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.analytics.signal_tracker import (
    SignalRecord,
    SignalStats,
    SignalTracker,
)


class TestSignalRecord:
    """SignalRecord 테스트"""

    def test_create_signal_record(self):
        """신호 기록 생성 테스트"""
        record = SignalRecord.create(
            bot_id="test-bot",
            signal="LONG",
            source="gemini",
            market_conditions={"rsi": 35.5},
            reason="RSI 과매도",
        )

        assert record.bot_id == "test-bot"
        assert record.signal == "LONG"
        assert record.source == "gemini"
        assert record.market_conditions == {"rsi": 35.5}
        assert record.reason == "RSI 과매도"
        assert record.trade_result is None
        assert record.pnl is None
        assert record.signal_id is not None
        assert isinstance(record.timestamp, datetime)

    def test_to_dict(self):
        """딕셔너리 변환 테스트"""
        record = SignalRecord.create(
            bot_id="test-bot",
            signal="SHORT",
            source="rule_based",
        )

        data = record.to_dict()

        assert data["bot_id"] == "test-bot"
        assert data["signal"] == "SHORT"
        assert data["source"] == "rule_based"
        assert "timestamp" in data
        assert "signal_id" in data

    def test_update_result(self):
        """결과 업데이트 테스트"""
        record = SignalRecord.create(
            bot_id="test-bot",
            signal="LONG",
            source="gemini",
        )

        record.update_result("win", 125.50)

        assert record.trade_result == "win"
        assert record.pnl == 125.50


class TestSignalStats:
    """SignalStats 테스트"""

    def test_calculate_win_rate(self):
        """승률 계산 테스트"""
        stats = SignalStats(
            total_signals=10,
            traded_signals=8,
            wins=6,
            losses=2,
            total_pnl=500.0,
        )

        stats.calculate()

        assert stats.win_rate == 75.0  # 6/8 * 100
        assert stats.avg_pnl == 62.5  # 500 / 8

    def test_calculate_empty_stats(self):
        """빈 통계 계산 테스트"""
        stats = SignalStats()

        stats.calculate()

        assert stats.win_rate == 0.0
        assert stats.avg_pnl == 0.0

    def test_to_dict(self):
        """딕셔너리 변환 테스트"""
        stats = SignalStats(
            total_signals=10,
            traded_signals=8,
            wins=6,
            losses=2,
            total_pnl=500.0,
            best_pnl=150.0,
            worst_pnl=-50.0,
        )
        stats.calculate()

        data = stats.to_dict()

        assert data["total_signals"] == 10
        assert data["traded_signals"] == 8
        assert data["wins"] == 6
        assert data["losses"] == 2
        assert data["win_rate"] == 75.0
        assert data["total_pnl"] == 500.0
        assert data["avg_pnl"] == 62.5
        assert data["best_pnl"] == 150.0
        assert data["worst_pnl"] == -50.0


class TestSignalTracker:
    """SignalTracker 테스트"""

    @pytest.fixture
    def tracker(self):
        """테스트용 트래커 생성"""
        return SignalTracker()

    @pytest.mark.asyncio
    async def test_record_signal_in_memory(self, tracker):
        """인메모리 신호 기록 테스트"""
        signal_id = await tracker.record_signal(
            bot_id="test-bot",
            signal="LONG",
            source="gemini",
            market_conditions={"rsi": 35.5},
            reason="RSI 과매도",
        )

        assert signal_id is not None
        assert signal_id in tracker._in_memory_signals

        record = tracker._in_memory_signals[signal_id]
        assert record.signal == "LONG"
        assert record.source == "gemini"

    @pytest.mark.asyncio
    async def test_update_signal_result(self, tracker):
        """신호 결과 업데이트 테스트"""
        signal_id = await tracker.record_signal(
            bot_id="test-bot",
            signal="LONG",
            source="gemini",
        )

        success = await tracker.update_signal_result(
            signal_id=signal_id,
            result="win",
            pnl=125.50,
        )

        assert success is True

        record = tracker._in_memory_signals[signal_id]
        assert record.trade_result == "win"
        assert record.pnl == 125.50

    @pytest.mark.asyncio
    async def test_update_nonexistent_signal(self, tracker):
        """존재하지 않는 신호 업데이트 테스트"""
        success = await tracker.update_signal_result(
            signal_id="nonexistent-id",
            result="win",
            pnl=100.0,
        )

        assert success is False

    @pytest.mark.asyncio
    async def test_get_signal_stats_in_memory(self, tracker):
        """인메모리 통계 조회 테스트"""
        # 여러 신호 기록
        signals = [
            ("LONG", "gemini", "win", 100.0),
            ("SHORT", "gemini", "loss", -50.0),
            ("LONG", "rule_based", "win", 75.0),
            ("LONG", "gemini", "win", 125.0),
        ]

        for signal, source, result, pnl in signals:
            signal_id = await tracker.record_signal(
                bot_id="test-bot",
                signal=signal,
                source=source,
            )
            await tracker.update_signal_result(signal_id, result, pnl)

        stats = await tracker.get_signal_stats(bot_id="test-bot", days=7)

        assert stats.total_signals == 4
        assert stats.traded_signals == 4
        assert stats.wins == 3
        assert stats.losses == 1
        assert stats.win_rate == 75.0
        assert stats.total_pnl == 250.0  # 100 - 50 + 75 + 125
        assert stats.best_pnl == 125.0
        assert stats.worst_pnl == -50.0

    @pytest.mark.asyncio
    async def test_get_signal_stats_by_source(self, tracker):
        """소스별 통계 조회 테스트"""
        # gemini 신호 2개
        for _ in range(2):
            signal_id = await tracker.record_signal(
                bot_id="test-bot",
                signal="LONG",
                source="gemini",
            )
            await tracker.update_signal_result(signal_id, "win", 100.0)

        # rule_based 신호 1개
        signal_id = await tracker.record_signal(
            bot_id="test-bot",
            signal="LONG",
            source="rule_based",
        )
        await tracker.update_signal_result(signal_id, "loss", -50.0)

        # gemini 통계
        gemini_stats = await tracker.get_signal_stats(
            bot_id="test-bot",
            source="gemini",
            days=7,
        )
        assert gemini_stats.total_signals == 2
        assert gemini_stats.wins == 2
        assert gemini_stats.win_rate == 100.0

        # rule_based 통계
        rule_stats = await tracker.get_signal_stats(
            bot_id="test-bot",
            source="rule_based",
            days=7,
        )
        assert rule_stats.total_signals == 1
        assert rule_stats.losses == 1
        assert rule_stats.win_rate == 0.0

    @pytest.mark.asyncio
    async def test_get_win_rate_by_source(self, tracker):
        """소스별 승률 조회 테스트"""
        # gemini: 2승 1패 (66.67%)
        for result, pnl in [("win", 100), ("win", 50), ("loss", -30)]:
            signal_id = await tracker.record_signal(
                bot_id="test-bot",
                signal="LONG",
                source="gemini",
            )
            await tracker.update_signal_result(signal_id, result, pnl)

        # rule_based: 1승 (100%)
        signal_id = await tracker.record_signal(
            bot_id="test-bot",
            signal="LONG",
            source="rule_based",
        )
        await tracker.update_signal_result(signal_id, "win", 80.0)

        win_rates = await tracker.get_win_rate_by_source(days=7)

        assert "gemini" in win_rates
        assert "rule_based" in win_rates
        assert win_rates["gemini"] == pytest.approx(66.67, rel=0.01)
        assert win_rates["rule_based"] == 100.0

    @pytest.mark.asyncio
    async def test_get_recent_signals(self, tracker):
        """최근 신호 조회 테스트"""
        # 3개 신호 기록
        for i in range(3):
            await tracker.record_signal(
                bot_id="test-bot",
                signal="LONG" if i % 2 == 0 else "SHORT",
                source="gemini",
            )

        signals = await tracker.get_recent_signals(bot_id="test-bot", limit=2)

        assert len(signals) == 2
        # 최신순 정렬 확인
        assert signals[0]["timestamp"] >= signals[1]["timestamp"]

    @pytest.mark.asyncio
    async def test_cleanup_old_signals(self, tracker):
        """오래된 신호 정리 테스트"""
        # 현재 신호
        await tracker.record_signal(
            bot_id="test-bot",
            signal="LONG",
            source="gemini",
        )

        # 오래된 신호 (수동으로 timestamp 변경)
        old_signal_id = await tracker.record_signal(
            bot_id="test-bot",
            signal="SHORT",
            source="rule_based",
        )
        tracker._in_memory_signals[old_signal_id].timestamp = (
            datetime.now() - timedelta(days=31)
        )

        assert len(tracker._in_memory_signals) == 2

        deleted = await tracker.cleanup_old_signals(days=30)

        assert deleted == 1
        assert len(tracker._in_memory_signals) == 1

    @pytest.mark.asyncio
    async def test_stats_filter_by_days(self, tracker):
        """기간별 필터링 테스트"""
        # 최근 신호
        signal_id = await tracker.record_signal(
            bot_id="test-bot",
            signal="LONG",
            source="gemini",
        )
        await tracker.update_signal_result(signal_id, "win", 100.0)

        # 오래된 신호
        old_signal_id = await tracker.record_signal(
            bot_id="test-bot",
            signal="LONG",
            source="gemini",
        )
        tracker._in_memory_signals[old_signal_id].timestamp = (
            datetime.now() - timedelta(days=10)
        )
        await tracker.update_signal_result(old_signal_id, "win", 200.0)

        # 7일 통계 (최근 신호만)
        stats_7d = await tracker.get_signal_stats(days=7)
        assert stats_7d.total_signals == 1
        assert stats_7d.total_pnl == 100.0

        # 30일 통계 (둘 다)
        stats_30d = await tracker.get_signal_stats(days=30)
        assert stats_30d.total_signals == 2
        assert stats_30d.total_pnl == 300.0


class TestSignalTrackerWithDB:
    """DB 연동 SignalTracker 테스트"""

    @pytest.fixture
    def mock_pool(self):
        """Mock DB 풀 생성"""
        pool = MagicMock()
        pool.acquire = MagicMock()
        return pool

    @pytest.fixture
    def tracker_with_db(self, mock_pool):
        """DB 연결된 트래커 생성"""
        tracker = SignalTracker(db_pool=mock_pool)
        return tracker

    @pytest.mark.asyncio
    async def test_record_signal_to_db(self, tracker_with_db, mock_pool):
        """DB 신호 기록 테스트"""
        # Mock 설정
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        signal_id = await tracker_with_db.record_signal(
            bot_id="550e8400-e29b-41d4-a716-446655440000",
            signal="LONG",
            source="gemini",
            market_conditions={"rsi": 35.5},
            reason="RSI 과매도",
        )

        assert signal_id is not None
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_memory_on_db_error(self, tracker_with_db, mock_pool):
        """DB 오류 시 인메모리 폴백 테스트"""
        # Mock 설정 - DB 오류 발생
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("DB Error")
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        signal_id = await tracker_with_db.record_signal(
            bot_id="550e8400-e29b-41d4-a716-446655440000",
            signal="LONG",
            source="gemini",
        )

        # 인메모리에 저장되어야 함
        assert signal_id in tracker_with_db._in_memory_signals

    @pytest.mark.asyncio
    async def test_update_signal_result_in_db(self, tracker_with_db, mock_pool):
        """DB 신호 결과 업데이트 테스트"""
        mock_conn = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        success = await tracker_with_db.update_signal_result(
            signal_id="test-signal-id",
            result="win",
            pnl=125.50,
        )

        assert success is True
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_stats_from_db(self, tracker_with_db, mock_pool):
        """DB 통계 조회 테스트"""
        # Mock fetchrow 결과
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            "total_signals": 10,
            "traded_signals": 8,
            "wins": 6,
            "losses": 2,
            "total_pnl": 500.0,
            "best_pnl": 150.0,
            "worst_pnl": -50.0,
        }
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        stats = await tracker_with_db.get_signal_stats(days=7)

        assert stats.total_signals == 10
        assert stats.wins == 6
        assert stats.win_rate == 75.0

    @pytest.mark.asyncio
    async def test_get_win_rate_by_source_from_db(self, tracker_with_db, mock_pool):
        """DB 소스별 승률 조회 테스트"""
        mock_conn = AsyncMock()
        mock_conn.fetch.return_value = [
            {"source": "gemini", "traded": 10, "wins": 7},
            {"source": "rule_based", "traded": 5, "wins": 3},
        ]
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        win_rates = await tracker_with_db.get_win_rate_by_source(days=7)

        assert win_rates["gemini"] == 70.0
        assert win_rates["rule_based"] == 60.0
