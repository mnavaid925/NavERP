#!/usr/bin/env python
"""SessionStart hook - stamp the 5-hour window and resume an interrupted build.

Two jobs, both of which have to happen before the first turn:

  1. Record the 5-hour usage window. A window already in flight is KEPT, not restarted - the
     limit is anchored to the first message of the window, so a second session opened two hours
     in shares the original deadline. Restamping it on every SessionStart would report a
     deadline hours later than the real one.

  2. If the previous session was cut off mid-build, inject the resume block: which sub-module,
     which phase, the BASE sha, and an explicit instruction not to restart from Phase 1. This is
     what makes a new session continue instead of rebuild.

Never blocks a session: any failure exits 0 with no context. A session-start hook that errors is
worse than one that does nothing.
"""
import json
import os
import sys

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HOOK_DIR)


def build_context():
    import build_state as bs

    state = bs.load()
    window, is_new = bs.ensure_window(state)
    bs.save(state)
    report = bs.window_report(window)

    lines = ["=== NavERP session window ==="]
    if is_new:
        lines.append("New 5-hour window started %s. It ENDS AT %s."
                     % (report["started_at"], report["ends_at"]))
    else:
        lines.append("Continuing the window that started %s (session #%d). It ENDS AT %s."
                     % (report["started_at"], report["sessions"], report["ends_at"]))
    lines.append("Time left: %s (usable: %s, keeping the last %d min to check out cleanly)."
                 % (report["left_human"], report["usable_human"], bs.RESERVE_MINUTES))

    minutes = report["minutes_left"]
    if minutes <= bs.RESERVE_MINUTES:
        lines.append("")
        lines.append("!! Under %d minutes remain. Do NOT start a new phase - it will not finish and being"
                     % bs.RESERVE_MINUTES)
        lines.append("   cut off mid-phase leaves the tree half-wired. Checkpoint instead: commit what is")
        lines.append("   done, run `build_state.py phase <key> in_progress --note \"...\"`, and stop.")
    elif minutes < 150:
        lines.append("")
        lines.append("Note: a full sub-module needs ~4h. With %s left, scope this session to finishing the"
                     % report["left_human"])
        lines.append("current build's remaining phases rather than starting a new sub-module.")

    lines.append("")
    lines.append("Checkpoint rule: after EVERY phase boundary run")
    lines.append("  venv\\Scripts\\python.exe .claude/hooks/build_state.py phase <key> done")
    lines.append("so that if this session is cut off, the next one resumes here instead of from Phase 1.")

    resume = bs.resume_block(state)
    if resume:
        lines.append("")
        lines.append(resume)

    return "\n".join(lines)


def main():
    try:
        json.load(sys.stdin)
    except Exception:
        pass

    try:
        context = build_context()
    except Exception as exc:  # never block a session on this hook
        sys.stderr.write("[session-start] skipped: %s: %s\n" % (exc.__class__.__name__, exc))
        return 0

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
