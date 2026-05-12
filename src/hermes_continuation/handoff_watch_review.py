#!/usr/bin/env python3
"""Review accumulated handoff watch logs and print a summary for threshold tuning.

Target: ≥50 log entries, <30% false positive rate, zero noise complaints.

Usage:
  python handoff_watch_review.py [--log-dir DIR] [--days N]

Output:
  - Entry count, date range
  - Level distribution (observe / advise / prepare / block)
  - Trigger source breakdown (gateway / cron / cli)
  - Cooldown-active ratio
  - Recommendation-level distribution
  - Threshold tuning suggestions based on actual data
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from hermes_continuation.watch_logger import read_watch_log


def _parse_ts(entry: dict) -> datetime | None:
    raw = entry.get("ts", "")
    if not isinstance(raw, str) or not raw:
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            # Python < 3.11 doesn't support 'Z' suffix
            cleaned = raw.replace("Z", "+00:00")
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def _count_by_key(entries: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        val = str(entry.get(key, "")).strip().lower()
        if val:
            counts[val] = counts.get(val, 0) + 1
    return counts


def _percent(n: int, total: int) -> str:
    if total == 0:
        return "0%"
    return f"{n / total * 100:.0f}%"


def _threshold_suggestion(
    entries: list[dict],
    key: str,
    current: int,
) -> str:
    """Suggest a threshold that would keep false positives under the target rate."""
    values = []
    for e in entries:
        v = e.get(key)
        if isinstance(v, (int, float)):
            values.append(int(v))

    if not values:
        return f"   (no data for {key})"

    values.sort()
    total = len(values)

    # Target: <30% of entries would trigger at this threshold
    # i.e., find the value where ≤30% of entries are below it
    # Actually we want: most entries that are "advise" or below should NOT trigger
    # Simpler: show the p50, p70, p90 values
    p50_idx = int(total * 0.50)
    p70_idx = int(total * 0.70)
    p90_idx = int(total * 0.90)

    parts = [f"   current={current}, p50={values[p50_idx]}, p70={values[p70_idx]}, p90={values[p90_idx]}"]
    if values[p70_idx] > current:
        parts.append(f"   ⚠️ p70 ({values[p70_idx]}) > current ({current}) — consider raising threshold")
    elif values[p50_idx] < current:
        parts.append(f"   ℹ️ p50 ({values[p50_idx]}) < current ({current}) — threshold looks reasonable")
    return "\n".join(parts)


def review(days: int | None = None) -> str:
    """Read watch logs and return a formatted review string."""
    entries = read_watch_log()
    if not entries:
        return "📭 尚無 watch log 資料。需要至少 50 筆記錄才能進行有意義的分析。"

    # Filter by days
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        entries = [e for e in entries if (_parse_ts(e) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff]

    if not entries:
        return f"📭 近 {days} 天內尚無 watch log 資料。"

    total = len(entries)

    # Date range
    timestamps = []
    for e in entries:
        ts = _parse_ts(e)
        if ts:
            timestamps.append(ts)
    earliest = min(timestamps).strftime("%Y-%m-%d") if timestamps else "unknown"
    latest = max(timestamps).strftime("%Y-%m-%d") if timestamps else "unknown"

    # Level distribution
    level_counts = _count_by_key(entries, "level")

    # Trigger source
    trigger_counts = _count_by_key(entries, "trigger")

    # Recommendation level
    rec_counts = _count_by_key(entries, "recommendation_level")

    # Cooldown ratio
    cooldown_count = sum(1 for e in entries if e.get("cooldown_active") is True)

    # Avg tool_calls / elapsed / changed_files
    tool_vals = [e["tool_calls"] for e in entries if isinstance(e.get("tool_calls"), (int, float))]
    elapsed_vals = [e["elapsed"] for e in entries if isinstance(e.get("elapsed"), (int, float))]
    changed_vals = [e["changed_files"] for e in entries if isinstance(e.get("changed_files"), (int, float))]

    avg_tool = sum(tool_vals) / len(tool_vals) if tool_vals else 0
    avg_elapsed = sum(elapsed_vals) / len(elapsed_vals) if elapsed_vals else 0
    avg_changed = sum(changed_vals) / len(changed_vals) if changed_vals else 0

    # Build output
    lines = [
        "=" * 60,
        "📊 Handoff Watch Log 分析報告",
        "=" * 60,
        "",
        f"⏱️  時間範圍：{earliest} → {latest}",
        f"📋 記錄總數：{total}",
        "",
    ]

    if total < 50:
        lines.append(f"⚠️ 記錄數 ({total}) 少於建議的 50 筆，分析結果僅供參考。")
        lines.append("   建議繼續收集資料後再進行閾值調整。")
        lines.append("")

    lines.append("---")
    lines.append("📈 觸發等級分佈")
    lines.append("---")
    for level in ["observe", "advise", "prepare", "block"]:
        count = level_counts.get(level, 0)
        bar = "█" * max(1, count * 30 // max(total, 1))
        lines.append(f"  {level:8s}: {count:4d} ({_percent(count, total):>3s}) {bar}")
    lines.append("")

    lines.append("---")
    lines.append("🔌 觸發來源")
    lines.append("---")
    for source, count in sorted(trigger_counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {source:8s}: {count:4d} ({_percent(count, total)})")
    lines.append("")

    if rec_counts:
        lines.append("---")
        lines.append("🎯 推薦等級分佈")
        lines.append("---")
        for level in ["observe", "advise", "prepare", "block"]:
            count = rec_counts.get(level, 0)
            if count:
                lines.append(f"  {level:8s}: {count:4d} ({_percent(count, total)})")
        lines.append("")

    lines.append("---")
    lines.append("🛡️ Cooldown 狀態")
    lines.append("---")
    lines.append(f"  cooldown active: {cooldown_count:4d} ({_percent(cooldown_count, total)})")
    lines.append(f"  cooldown clear : {total - cooldown_count:4d} ({_percent(total - cooldown_count, total)})")
    lines.append("")

    lines.append("---")
    lines.append("📊 平均指標")
    lines.append("---")
    lines.append(f"  avg tool_calls   : {avg_tool:.1f}")
    lines.append(f"  avg elapsed (min): {avg_elapsed:.1f}")
    lines.append(f"  avg changed_files: {avg_changed:.1f}")
    lines.append("")

    lines.append("---")
    lines.append("🔧 閾值調整建議")
    lines.append("---")
    lines.append("  tool_calls threshold:")
    lines.append(_threshold_suggestion(entries, "tool_calls", 5))
    lines.append("  elapsed_minutes threshold:")
    lines.append(_threshold_suggestion(entries, "elapsed", 30))
    lines.append("")
    lines.append("  ℹ️ 建議作法：")
    lines.append("    1. 先看 p50/p70 是否接近當前閾值")
    lines.append("    2. 若 p70 顯著高於當前閾值 → 調高以減少 false positive")
    lines.append("    3. 目標：false positive < 30%，零噪音投訴")
    lines.append("")

    # Progress toward tuning goal
    pct_complete = min(100, total * 100 // 50)
    bar_len = pct_complete // 5
    bar = "█" * bar_len + "░" * (20 - bar_len)
    lines.append("---")
    lines.append("📊 調優準備進度")
    lines.append("---")
    lines.append(f"  [{bar}] {total}/50 ({pct_complete}%)")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review handoff watch logs for threshold tuning",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Only consider logs from the last N days (default: 90)",
    )
    args = parser.parse_args()

    print(review(days=args.days))


if __name__ == "__main__":
    main()
