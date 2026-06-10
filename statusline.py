#!/usr/bin/env python3
"""Single-line cache-TTL status for Claude Code's `statusLine` setting.

Claude Code passes the session JSON on stdin. We find the matching
cache-timer file written by the Stop / UserPromptSubmit hooks and print one
line that the extension renders inside the panel (sidebar or editor window).

Reuses cache_countdown.py's logic so the output matches the terminal ticker.
Designed to be run every second via `statusLine.refreshInterval`.
"""
import sys
import os
import json
from datetime import datetime, timezone

# cache_countdown.py lives in this same directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cache_countdown as cc

TTL = 295  # seconds; matches the ticker's default (just under Anthropic's 5min)


def main():
    # The extension captures stdout as a pipe -> force UTF-8 so emoji survive.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        data = {}

    sid = data.get("session_id", "")
    if not sid:
        return  # nothing to render

    timer = cc.STATE_DIR / f"cache-timer-{sid}.json"
    if not timer.is_file():
        return  # no hook has fired for this session yet

    try:
        t = json.loads(timer.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    ts_str = t.get("timestamp")
    if not ts_str:
        return
    try:
        ts = datetime.fromisoformat(ts_str)  # handles .NET's 7-digit fraction on 3.11+
    except ValueError:
        return
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    remaining = TTL - (datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds()
    stopped = t.get("stopped")

    if stopped is False:
        line = "\U0001f525 cache hot"          # 🔥 agent active, cache being refreshed
    elif stopped is True:
        if remaining > 0:
            icon = cc.get_icon(remaining, TTL)  # green/yellow/red by ratio
            line = f"{icon} cache {cc.format_countdown(remaining)}"
            cwd = t.get("cwd", "") or data.get("cwd", "")
            try:
                ctx, exceeds = cc.read_session_context(sid, cwd)
                cost = cc.estimate_cost(ctx, exceeds)
            except Exception:
                cost = ""
            if cost:
                line += f" · {cost} at risk"
        else:
            line = "❄ cache cold"           # ❄ expired
    else:
        return  # unknown state (no hook yet)

    try:
        print(cc._safe_encode(line))
    except Exception:
        print(line.encode("ascii", "replace").decode("ascii"))


if __name__ == "__main__":
    main()
