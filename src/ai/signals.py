"""
Trading signal parsing and validation
"""
from loguru import logger


def parse_signal(raw_signal: str) -> str:
    """
    Parse and clean signal from AI response

    Args:
        raw_signal: Raw signal from AI

    Returns:
        Cleaned signal: "LONG", "SHORT", or "WAIT"
    """
    # Clean and uppercase
    signal = raw_signal.strip().upper()

    # Remove common prefixes/suffixes
    for prefix in ["SIGNAL:", "OUTPUT:", "RESULT:"]:
        if signal.startswith(prefix):
            signal = signal[len(prefix):].strip()

    # Extract first word if multiple words
    if " " in signal:
        signal = signal.split()[0]

    return signal


def validate_signal(signal: str) -> bool:
    """
    Validate if signal is one of the allowed values

    Args:
        signal: Signal to validate

    Returns:
        True if valid, False otherwise
    """
    valid_signals = ["LONG", "SHORT", "WAIT"]
    is_valid = signal in valid_signals

    if not is_valid:
        logger.warning(f"Invalid signal: '{signal}'")

    return is_valid


def get_signal_emoji(signal: str) -> str:
    """
    Get emoji for signal (for Discord notifications)

    Args:
        signal: Trading signal

    Returns:
        Emoji string
    """
    emoji_map = {
        "LONG": "🟢",
        "SHORT": "🔴",
        "WAIT": "⏸️",
    }
    return emoji_map.get(signal, "❓")


def get_signal_color(signal: str) -> int:
    """
    Get color code for signal (for Discord embeds)

    Args:
        signal: Trading signal

    Returns:
        Discord color code (integer)
    """
    color_map = {
        "LONG": 0x00FF00,  # Green
        "SHORT": 0xFF0000,  # Red
        "WAIT": 0xFFFF00,  # Yellow
    }
    return color_map.get(signal, 0x808080)  # Gray for unknown


def should_enter_trade(signal: str, has_position: bool) -> bool:
    """
    Determine if we should enter a trade based on signal and current position

    Args:
        signal: Trading signal
        has_position: Whether we currently have an open position

    Returns:
        True if should enter trade, False otherwise
    """
    # Don't enter if we already have a position
    if has_position:
        logger.debug("Already have position, skipping entry")
        return False

    # Don't enter on WAIT signal
    if signal == "WAIT":
        logger.debug("Signal is WAIT, skipping entry")
        return False

    # Enter on LONG or SHORT
    if signal in ["LONG", "SHORT"]:
        logger.info(f"Signal {signal} with no position, will enter trade")
        return True

    return False
