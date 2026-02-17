"""SessionClassifier 테스트."""
from datetime import datetime, timezone

from src.ai.confluence.session_classifier import SessionClassifier, TradingSession


class TestTradingSession:
    """TradingSession enum 테스트."""

    def test_session_values(self):
        assert TradingSession.ASIA.value == "asia"
        assert TradingSession.EU.value == "eu"
        assert TradingSession.US.value == "us"
        assert TradingSession.DEEP_NIGHT.value == "deep_night"

    def test_session_members(self):
        assert len(TradingSession) == 4


class TestSessionClassifier:
    """SessionClassifier 테스트."""

    def setup_method(self):
        self.classifier = SessionClassifier()

    def test_asia_session_start(self):
        t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        assert self.classifier.classify(t) == TradingSession.ASIA

    def test_asia_session_mid(self):
        t = datetime(2026, 1, 1, 4, 30, tzinfo=timezone.utc)
        assert self.classifier.classify(t) == TradingSession.ASIA

    def test_eu_session_start(self):
        t = datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc)
        assert self.classifier.classify(t) == TradingSession.EU

    def test_eu_session_mid(self):
        t = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
        assert self.classifier.classify(t) == TradingSession.EU

    def test_us_session_start(self):
        t = datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc)
        assert self.classifier.classify(t) == TradingSession.US

    def test_us_session_end(self):
        t = datetime(2026, 1, 1, 20, 59, tzinfo=timezone.utc)
        assert self.classifier.classify(t) == TradingSession.US

    def test_deep_night_session(self):
        t = datetime(2026, 1, 1, 22, 0, tzinfo=timezone.utc)
        assert self.classifier.classify(t) == TradingSession.DEEP_NIGHT

    def test_default_current_time(self):
        """current_time=None이면 현재 UTC 시간 사용."""
        result = self.classifier.classify()
        assert isinstance(result, TradingSession)
