"""
Discord Embed 생성 함수

봇 상태, 포지션, 통계, 내역 등의 임베드를 생성합니다.
"""
from datetime import datetime
from typing import Dict, Any, List

import discord

from src.discord_bot.constants import Colors, Emojis
from src.discord_bot.utils import (
    format_uptime,
    format_time_ago,
    format_duration,
    format_timecut_remaining,
    calculate_pnl,
    get_status_emoji,
    get_status_text,
    get_position_emoji,
    get_pnl_emoji,
    format_price,
    format_percentage,
)


def create_status_embed(bot_state: dict) -> discord.Embed:
    """봇 상태 임베드 생성

    Args:
        bot_state: 공유 봇 상태 딕셔너리

    Returns:
        상태 임베드
    """
    is_running = bot_state.get("is_running", False)
    current_price = bot_state.get("current_price", 0)
    last_signal = bot_state.get("last_signal", "WAIT")
    last_signal_time = bot_state.get("last_signal_time")
    is_paused = bot_state.get("is_paused", False)
    uptime_start = bot_state.get("uptime_start")
    position = bot_state.get("position")

    # 상태 색상 결정
    color = Colors.SUCCESS if (is_running and not is_paused) else Colors.ERROR

    embed = discord.Embed(title="🤖 봇 상태", color=color)

    # 상태 필드
    status_color = get_status_emoji(is_running, is_paused)
    status_value = get_status_text(is_running, is_paused)

    embed.add_field(name="⚡ 상태", value=f"{status_color} {status_value}", inline=True)
    embed.add_field(name="⏰ 가동시간", value=format_uptime(uptime_start), inline=True)
    embed.add_field(name="💰 심볼", value=bot_state.get("symbol", "BTCUSDT"), inline=True)
    embed.add_field(name="📊 현재가", value=format_price(current_price), inline=True)

    # 포지션 정보
    if position and position.get("side"):
        side = position.get("side")
        emoji = get_position_emoji(side)
        embed.add_field(name="📍 포지션", value=f"{emoji} {side}", inline=True)
    else:
        embed.add_field(name="📍 포지션", value="없음", inline=True)

    embed.add_field(
        name="🔄 마지막 신호",
        value=f"{last_signal} ({format_time_ago(last_signal_time)})",
        inline=False
    )
    embed.add_field(name="📈 전략", value="Rule-Based (RSI + MA)", inline=False)

    return embed


def create_position_embed(bot_state: dict) -> discord.Embed:
    """포지션 상세 임베드 생성

    Args:
        bot_state: 공유 봇 상태 딕셔너리

    Returns:
        포지션 임베드
    """
    position = bot_state.get("position")

    if not position or not position.get("side"):
        embed = discord.Embed(
            title="📍 포지션 없음",
            description="⏸️ 신호를 기다리는 중...",
            color=Colors.WARNING
        )
        embed.add_field(
            name="🔄 마지막 신호",
            value=bot_state.get("last_signal", "WAIT"),
            inline=False
        )
        return embed

    side = position.get("side")
    entry_price = position.get("entry_price", 0)
    size = position.get("quantity", position.get("size", 0))
    leverage = position.get("leverage", 15)
    entry_time = position.get("entry_time")
    tp_price = position.get("tp_price", 0)
    sl_price = position.get("sl_price", 0)
    timecut_at = position.get("timecut_at")
    current_price = bot_state.get("current_price", 0)

    # PnL 계산
    pnl_pct, pnl_usd = calculate_pnl(
        entry_price, current_price, side, leverage, size
    )

    emoji = get_position_emoji(side)
    color = Colors.LONG if side == "LONG" else Colors.SHORT

    embed = discord.Embed(title="📍 현재 포지션", color=color)

    embed.add_field(name=f"{emoji} 방향", value=side, inline=True)
    embed.add_field(name="💵 진입가", value=format_price(entry_price), inline=True)
    embed.add_field(
        name="📊 수량",
        value=f"{size:.4f} BTC ({leverage}x)",
        inline=True
    )
    embed.add_field(name="⏱️ 경과시간", value=format_duration(entry_time), inline=True)
    embed.add_field(
        name="🎯 익절가",
        value=f"{format_price(tp_price)} (+0.4%)",
        inline=True
    )
    embed.add_field(
        name="🛑 손절가",
        value=f"{format_price(sl_price)} (-0.4%)",
        inline=True
    )
    embed.add_field(
        name="⏰ 타임컷",
        value=format_timecut_remaining(timecut_at),
        inline=False
    )

    pnl_emoji = get_pnl_emoji(pnl_usd)
    embed.add_field(
        name=f"{pnl_emoji} 현재 손익",
        value=f"${pnl_usd:+.2f} ({format_percentage(pnl_pct)})",
        inline=False
    )

    return embed


def create_stats_embed(stats_data: Dict[str, Any], hours: int = 24) -> discord.Embed:
    """거래 통계 임베드 생성

    Args:
        stats_data: 통계 데이터
        hours: 조회 기간 (시간)

    Returns:
        통계 임베드
    """
    if stats_data["total_trades"] == 0:
        return discord.Embed(
            title=f"📊 거래 없음 (최근 {hours}시간)",
            description="이 기간에 완료된 거래가 없습니다",
            color=Colors.WARNING
        )

    color = Colors.SUCCESS if stats_data["total_pnl"] > 0 else Colors.ERROR

    embed = discord.Embed(
        title="📊 거래 통계",
        description=f"최근 {hours}시간",
        color=color
    )

    embed.add_field(
        name="🎯 총 거래",
        value=str(stats_data["total_trades"]),
        inline=True
    )
    embed.add_field(
        name="✅ 승",
        value=f"{stats_data['winners']}회 ({stats_data['win_rate']:.1f}%)",
        inline=True
    )
    embed.add_field(
        name="❌ 패",
        value=f"{stats_data['losers']}회",
        inline=True
    )

    pnl_emoji = get_pnl_emoji(stats_data["total_pnl"])
    embed.add_field(
        name=f"{pnl_emoji} 총 손익",
        value=f"${stats_data['total_pnl']:+.2f}",
        inline=False
    )
    embed.add_field(
        name="📈 최고 거래",
        value=f"+{stats_data['best_trade']:.2f}%",
        inline=True
    )
    embed.add_field(
        name="📉 최악 거래",
        value=f"{stats_data['worst_trade']:.2f}%",
        inline=True
    )
    embed.add_field(
        name=f"{Emojis.LONG} LONG",
        value=f"{stats_data['long_trades']}회",
        inline=True
    )
    embed.add_field(
        name=f"{Emojis.SHORT} SHORT",
        value=f"{stats_data['short_trades']}회",
        inline=True
    )

    return embed


def create_history_embed(trades: List[Dict[str, Any]]) -> discord.Embed:
    """거래 내역 임베드 생성

    Args:
        trades: 거래 목록

    Returns:
        내역 임베드
    """
    if not trades:
        return discord.Embed(
            title="📜 거래 내역 없음",
            description="완료된 거래를 찾을 수 없습니다",
            color=Colors.WARNING
        )

    embed = discord.Embed(
        title=f"📜 최근 거래 (최근 {len(trades)}개)",
        color=Colors.INFO
    )

    for i, trade in enumerate(trades, 1):
        side = trade["side"]
        emoji = get_position_emoji(side)
        entry = float(trade["entry_price"])
        exit_p = float(trade["exit_price"]) if trade["exit_price"] else 0
        exit_reason = trade["exit_reason"]
        pnl = float(trade.get("pnl", 0) or 0)
        pnl_pct = float(trade.get("pnl_pct", 0) or 0)

        # Time ago
        exit_time = trade["exit_time"]
        if exit_time:
            if hasattr(exit_time, 'replace'):
                time_diff = datetime.now() - exit_time.replace(tzinfo=None)
            else:
                time_diff = datetime.now() - exit_time
            hours_ago = int(time_diff.total_seconds() / 3600)
            mins_ago = int((time_diff.total_seconds() % 3600) / 60)

            if hours_ago > 0:
                time_ago = f"{hours_ago}시간 {mins_ago}분 전"
            else:
                time_ago = f"{mins_ago}분 전"
        else:
            time_ago = "N/A"

        pnl_emoji = get_pnl_emoji(pnl)

        value = (
            f"{emoji} **{side}** | 진입: {format_price(entry)} → "
            f"청산: {format_price(exit_p)} ({exit_reason})\n"
            f"{pnl_emoji} 손익: ${pnl:+.2f} ({format_percentage(pnl_pct)}) | {time_ago}"
        )

        embed.add_field(
            name=f"{i}️⃣ 거래 #{trade['id']}",
            value=value,
            inline=False
        )

    return embed


def create_account_embed(
    balance: Dict[str, Any],
    positions: List[Dict[str, Any]]
) -> discord.Embed:
    """계정 전체 포지션 임베드 생성

    Args:
        balance: 잔고 정보
        positions: 포지션 목록

    Returns:
        계정 임베드
    """
    total_unrealized_pnl = sum(p["unrealized_pnl"] for p in positions)

    embed = discord.Embed(title="💼 계정 현황", color=Colors.INFO)

    # 잔고 정보
    embed.add_field(
        name="💰 USDT 잔고",
        value=format_price(balance['balance']),
        inline=True
    )
    embed.add_field(
        name="💵 사용 가능",
        value=format_price(balance['available']),
        inline=True
    )
    embed.add_field(
        name="📊 열린 포지션",
        value=f"{len(positions)}개",
        inline=True
    )

    # 총 미실현 손익
    pnl_emoji = get_pnl_emoji(total_unrealized_pnl)
    embed.add_field(
        name=f"{pnl_emoji} 총 미실현 손익",
        value=f"${total_unrealized_pnl:+,.2f}",
        inline=False
    )

    # 각 포지션 표시
    if positions:
        embed.add_field(
            name="─" * 20,
            value="**📍 열린 포지션 목록**",
            inline=False
        )

        for i, pos in enumerate(positions, 1):
            side = pos["side"]
            emoji = get_position_emoji(side)
            pnl_emoji = get_pnl_emoji(pos["unrealized_pnl"])

            value = (
                f"{emoji} **{side}** {pos['leverage']}x\n"
                f"진입: {format_price(pos['entry_price'])} → "
                f"현재: {format_price(pos['current_price'])}\n"
                f"수량: {pos['quantity']:.4f}\n"
                f"{pnl_emoji} 손익: ${pos['unrealized_pnl']:+,.2f} "
                f"({format_percentage(pos['pnl_pct'])})\n"
                f"청산가: {format_price(pos['liquidation_price'])}"
            )

            embed.add_field(
                name=f"{i}. {pos['symbol']}",
                value=value,
                inline=True
            )
    else:
        embed.add_field(
            name="📍 포지션",
            value="열린 포지션이 없습니다",
            inline=False
        )

    return embed


def create_bot_list_embed(data: Dict[str, Any]) -> discord.Embed:
    """봇 목록 임베드 생성

    Args:
        data: 봇 목록 데이터

    Returns:
        봇 목록 임베드
    """
    total_bots = data.get("total_bots", 0)
    running_bots = data.get("running_bots", 0)
    paused_bots = data.get("paused_bots", 0)
    bots = data.get("bots", [])

    embed = discord.Embed(
        title="📋 봇 목록",
        description=f"총 {total_bots}개 봇 등록됨",
        color=Colors.INFO
    )

    embed.add_field(
        name="📊 요약",
        value=f"🟢 실행 중: {running_bots}개\n⏸️ 일시정지: {paused_bots}개",
        inline=False
    )

    if bots:
        for bot_info in bots:
            is_running = bot_info.get('is_running', False)
            is_paused = bot_info.get('is_paused', False)
            status_emoji = get_status_emoji(is_running, is_paused)

            embed.add_field(
                name=f"{status_emoji} {bot_info.get('name', 'unknown')}",
                value=(
                    f"심볼: {bot_info.get('symbol', 'N/A')}\n"
                    f"위험도: {bot_info.get('risk_level', 'N/A')}"
                ),
                inline=True
            )
    else:
        embed.add_field(
            name="ℹ️ 정보",
            value="등록된 봇이 없습니다.",
            inline=False
        )

    return embed


def create_bot_status_embed(bot_name: str, state: Dict[str, Any]) -> discord.Embed:
    """봇 상태 임베드 생성

    Args:
        bot_name: 봇 이름
        state: 봇 상태 데이터

    Returns:
        봇 상태 임베드
    """
    is_running = state.get('is_running', False)
    is_paused = state.get('is_paused', False)

    # 상태 색상 결정
    if is_running and not is_paused:
        color = Colors.SUCCESS
        status_str = "🟢 실행 중"
    elif is_paused:
        color = Colors.WARNING
        status_str = "⏸️ 일시정지"
    else:
        color = Colors.ERROR
        status_str = "🔴 중지됨"

    embed = discord.Embed(title=f"📊 {bot_name} 상태", color=color)

    embed.add_field(name="⚡ 상태", value=status_str, inline=True)
    embed.add_field(name="💰 심볼", value=state.get('symbol', 'N/A'), inline=True)
    embed.add_field(name="⚠️ 위험도", value=state.get('risk_level', 'N/A'), inline=True)
    embed.add_field(name="📈 레버리지", value=f"{state.get('leverage', 0)}x", inline=True)
    embed.add_field(
        name="💵 현재가",
        value=format_price(state.get('current_price', 0)),
        inline=True
    )
    embed.add_field(name="🔄 루프", value=str(state.get('loop_count', 0)), inline=True)

    # 포지션 정보
    position = state.get('position')
    if position and position.get('side'):
        side_emoji = get_position_emoji(position['side'])
        embed.add_field(
            name=f"{side_emoji} 포지션",
            value=f"{position['side']} @ {format_price(position.get('entry_price', 0))}",
            inline=False
        )

    # 마지막 시그널
    embed.add_field(
        name="🔄 마지막 시그널",
        value=state.get('last_signal', 'WAIT'),
        inline=True
    )

    return embed
