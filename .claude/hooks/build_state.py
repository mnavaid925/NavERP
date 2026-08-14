#!/usr/bin/env python
"""Durable build state for the NavERP Module Creation Sequence.

Why this exists: a Claude Code session dies when the 5-hour usage window is exhausted. Nothing
inside that session survives - not the plan, not which phase was running, not the BASE sha the
review wave needs. If the only record of progress is the transcript, the next session restarts
from Phase 1 and pays for the whole build twice.

This module keeps that record on disk instead, in `.claude/tasks/build-state.json`:

  window  the current 5-hour usage window (started_at / ends_at). NOT reset per session - a
          second session opened inside a live window inherits the SAME deadline, because the
          window is anchored to the first message of the window, not to each session start.
  build   the sub-module being built, its BASE sha and claimed migration number, and the
          status of each of the 8 phases.

CLI (the session and its agents call these; nobody hand-edits the JSON):

  python .claude/hooks/build_state.py window
  python .claude/hooks/build_state.py start --slug scm --submodule 4.17 --title "Returns" \
                                            --base 3de294ca --migration 0029
  python .claude/hooks/build_state.py phase 3_build in_progress --note "integrate step"
  python .claude/hooks/build_state.py phase 3_build done
  python .claude/hooks/build_state.py show
  python .claude/hooks/build_state.py finish

`show` prints the resume block that the SessionStart hook injects into a new session.
"""
import argparse
import json
import os
from datetime import datetime, timedelta

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HOOK_DIR))
STATE_PATH = os.path.join(ROOT, ".claude", "tasks", "build-state.json")

WINDOW_HOURS = 5.0
#: Leave the last of the window unbooked: a phase started here will not finish, and being cut
#: off mid-phase is what leaves the state file stale and the tree half-wired.
RESERVE_MINUTES = 20
#: The budget the sequence is designed around - one sub-module inside 4 hours.
BUDGET_HOURS = 4.0

PHASES = [
    ("0_claim",    "Claim the tree (BASE sha, dirty-tree check, migration number)"),
    ("1_research", "research agent -> .claude/tasks/research-<slug>-<N.M>.md"),
    ("2_todo",     "todo agent -> .claude/tasks/todo.md"),
    ("3_build",    "Build wave (module-build.js)"),
    ("4_review",   "Review wave (module-review.js) -> review-<slug>-<N.M>.md"),
    ("5_fix",      "code-fixer agent burns down the findings file"),
    ("6_tests",    "Test wave (module-tests.js)"),
    ("7_docs",     "Skill + README"),
]
PHASE_KEYS = [k for k, _ in PHASES]
PHASE_LABEL = dict(PHASES)
STATUSES = ("pending", "in_progress", "done", "skipped")
MARK = {"pending": "[ ]", "in_progress": "[>]", "done": "[x]", "skipped": "[-]"}


# --------------------------------------------------------------------------- time helpers

def now():
    """Local time, timezone-aware, so a stored deadline reads correctly to the user."""
    return datetime.now().astimezone()


def parse(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def fmt_delta(delta):
    total = int(delta.total_seconds())
    if total <= 0:
        return "0m"
    hours, minutes = divmod(total // 60, 60)
    return ("%dh %02dm" % (hours, minutes)) if hours else ("%dm" % minutes)


# --------------------------------------------------------------------------- persistence

def load():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
    os.replace(tmp, STATE_PATH)  # atomic: a half-written state file is worse than none


def blank_phases():
    return {key: {"status": "pending", "note": "", "at": ""} for key in PHASE_KEYS}


# --------------------------------------------------------------------------- window

def ensure_window(state):
    """Return (window, is_new).

    A window that has not expired is KEPT. The 5-hour limit is anchored to the first message of
    the window, so a second or third session opened inside it shares the original deadline -
    resetting the clock on every SessionStart would report a deadline hours later than the real
    one, which is worse than not tracking it at all.
    """
    current = now()
    window = state.get("window") or {}
    ends = parse(window.get("ends_at"))
    if ends and ends > current:
        window["sessions"] = int(window.get("sessions", 1)) + 1
        state["window"] = window
        return window, False

    window = {
        "started_at": current.isoformat(timespec="seconds"),
        "ends_at": (current + timedelta(hours=WINDOW_HOURS)).isoformat(timespec="seconds"),
        "budget_ends_at": (current + timedelta(hours=BUDGET_HOURS)).isoformat(timespec="seconds"),
        "sessions": 1,
    }
    state["window"] = window
    return window, True


def window_report(window):
    ends = parse(window.get("ends_at"))
    started = parse(window.get("started_at"))
    budget = parse(window.get("budget_ends_at"))
    current = now()
    left = (ends - current) if ends else timedelta(0)
    usable = left - timedelta(minutes=RESERVE_MINUTES)
    return {
        "started_at": started.strftime("%H:%M") if started else "?",
        "ends_at": ends.strftime("%H:%M") if ends else "?",
        "ends_at_full": ends.isoformat(timespec="seconds") if ends else "",
        "budget_ends_at": budget.strftime("%H:%M") if budget else "",
        "minutes_left": max(0, int(left.total_seconds() // 60)),
        "left_human": fmt_delta(left),
        "usable_human": fmt_delta(usable),
        "sessions": int(window.get("sessions", 1)),
    }


# --------------------------------------------------------------------------- resume

def next_phase(build):
    """The first phase that is neither done nor skipped - where a new session resumes."""
    phases = (build or {}).get("phases") or {}
    for key in PHASE_KEYS:
        if phases.get(key, {}).get("status") not in ("done", "skipped"):
            return key
    return None


def phase_strip(build):
    phases = (build or {}).get("phases") or {}
    parts = []
    for key in PHASE_KEYS:
        status = phases.get(key, {}).get("status", "pending")
        parts.append("%s %s" % (MARK.get(status, "[ ]"), key.split("_", 1)[1]))
    return "  ".join(parts)


def resume_block(state):
    """The text the SessionStart hook injects. Empty string when there is nothing to resume."""
    build = state.get("build")
    if not build:
        return ""
    key = next_phase(build)
    if key is None:
        return ""

    phases = build.get("phases") or {}
    entry = phases.get(key, {})
    lines = [
        "=== UNFINISHED BUILD - RESUME THIS, DO NOT START A NEW ONE ===",
        "%s %s %s" % (build.get("slug", "?"), build.get("submodule", "?"), build.get("title", "")),
        "  BASE sha:  %s   (the review wave needs this - do not recompute it)" % (build.get("base") or "NOT RECORDED"),
        "  migration: %s" % (build.get("migration") or "not claimed"),
        "  started:   %s" % (build.get("started_at") or "?"),
        "",
        "  " + phase_strip(build),
        "",
        "RESUME AT PHASE %s - %s" % (key, PHASE_LABEL.get(key, "")),
    ]
    if entry.get("note"):
        lines.append('  last note: "%s"' % entry["note"])
    if entry.get("status") == "in_progress":
        lines.append("  This phase was INTERRUPTED mid-run. Verify what already landed on disk before")
        lines.append("  re-running it - re-running a completed phase duplicates commits and migrations.")
    lines += [
        "",
        "Read .claude/tasks/build-state.json and .claude/tasks/todo.md, confirm against `git log`",
        "what actually got committed, then continue the CLAUDE.md Module Creation Sequence from this",
        "phase. Do NOT restart at Phase 1 and do NOT re-run phases already marked [x].",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- commands

def cmd_window(_args):
    state = load()
    window, is_new = ensure_window(state)
    save(state)
    report = window_report(window)
    report["new_window"] = is_new
    print(json.dumps(report, indent=2))
    return 0


def cmd_start(args):
    state = load()
    ensure_window(state)
    state["build"] = {
        "slug": args.slug,
        "submodule": args.submodule,
        "title": args.title or "",
        "base": args.base or "",
        "migration": args.migration or "",
        "started_at": now().isoformat(timespec="seconds"),
        "phases": blank_phases(),
    }
    save(state)
    print("build started: %s %s" % (args.slug, args.submodule))
    return 0


def cmd_phase(args):
    state = load()
    build = state.get("build")
    if not build:
        print("no build in progress - run `build_state.py start` first")
        return 1
    if args.key not in PHASE_KEYS:
        print("unknown phase %r; expected one of: %s" % (args.key, ", ".join(PHASE_KEYS)))
        return 1
    if args.status not in STATUSES:
        print("unknown status %r; expected one of: %s" % (args.status, ", ".join(STATUSES)))
        return 1

    entry = build.setdefault("phases", blank_phases()).setdefault(args.key, {})
    entry["status"] = args.status
    entry["at"] = now().isoformat(timespec="seconds")
    if args.note is not None:
        entry["note"] = args.note
    for field in ("base", "migration"):
        value = getattr(args, field, None)
        if value:
            build[field] = value
    save(state)
    print("%s -> %s" % (args.key, args.status))
    return 0


def cmd_finish(_args):
    state = load()
    build = state.pop("build", None)
    if build:
        build["finished_at"] = now().isoformat(timespec="seconds")
        history = state.setdefault("history", [])
        history.append(build)
        del history[:-20]  # keep the tail bounded; this file is read on every session start
    save(state)
    print("build closed out" if build else "no build in progress")
    return 0


def cmd_show(_args):
    state = load()
    window = state.get("window")
    if window:
        report = window_report(window)
        print("5-hour window: %s -> %s  (%s left, %s usable)"
              % (report["started_at"], report["ends_at"], report["left_human"], report["usable_human"]))
    else:
        print("no window recorded")
    block = resume_block(state)
    print("\n" + block if block else "\nno unfinished build")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subs = parser.add_subparsers(dest="cmd")

    subs.add_parser("window").set_defaults(func=cmd_window)
    subs.add_parser("show").set_defaults(func=cmd_show)
    subs.add_parser("finish").set_defaults(func=cmd_finish)

    start = subs.add_parser("start")
    start.add_argument("--slug", required=True)
    start.add_argument("--submodule", required=True)
    start.add_argument("--title", default="")
    start.add_argument("--base", default="")
    start.add_argument("--migration", default="")
    start.set_defaults(func=cmd_start)

    phase = subs.add_parser("phase")
    phase.add_argument("key")
    phase.add_argument("status")
    phase.add_argument("--note", default=None)
    phase.add_argument("--base", default=None)
    phase.add_argument("--migration", default=None)
    phase.set_defaults(func=cmd_phase)

    args = parser.parse_args()
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
