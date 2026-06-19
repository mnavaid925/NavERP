#!/usr/bin/env python
"""PostToolUse hook — auto-verify a single edited file (fast).

Triggered after Edit/Write/MultiEdit. It inspects the changed file path and:
  - apps/**.py or config/**.py  -> runs Django's `manage.py check`
  - templates/**.html           -> compiles the template + flags a multi-line {# #}
                                    comment (which renders as VISIBLE TEXT)

Exit 0  = clean, or the file isn't a Django source/template (no-op).
Exit 2  = a real problem; the message on stderr is fed back to Claude to fix.

The script is cwd-independent: it derives the project root from its own location
(.claude/hooks/on_edit.py -> project root), so it works no matter how it's invoked.
"""
import io
import json
import os
import sys

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HOOK_DIR))  # .claude/hooks -> .claude -> project root


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    fp = (payload.get("tool_input") or {}).get("file_path") or ""
    if not fp:
        return 0
    norm = fp.replace("\\", "/")
    is_py = norm.endswith(".py") and ("/apps/" in norm or "/config/" in norm)
    is_html = norm.endswith(".html") and "/templates/" in norm
    if not (is_py or is_html):
        return 0  # not a Django source/template — nothing to verify

    os.chdir(ROOT)
    sys.path.insert(0, ROOT)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        import django
        django.setup()
    except Exception as exc:  # never block on environment problems
        print(f"[auto-verify] skipped ({exc.__class__.__name__}: {exc})")
        return 0

    problems = []

    if is_py:
        from django.core.management import call_command
        from django.core.management.base import SystemCheckError
        buf = io.StringIO()
        try:
            call_command("check", stdout=buf, stderr=buf)
        except SystemCheckError:
            problems.append("manage.py check failed:\n" + buf.getvalue().strip())
        except Exception as exc:
            problems.append(f"manage.py check error: {exc}")

    if is_html:
        rel = norm.rsplit("/templates/", 1)[1]
        from django.template import TemplateSyntaxError
        from django.template.loader import get_template
        try:
            get_template(rel)
        except TemplateSyntaxError as exc:
            problems.append(f"Template {rel}: syntax error: {exc}")
        except Exception:
            pass  # missing includes / unrelated load errors — don't block
        try:
            with open(fp, encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    idx = line.find("{#")
                    if idx != -1 and "#}" not in line[idx:]:
                        problems.append(
                            f"Template {rel}:{i} opens a '{{#' comment with no closing '#}}' on the "
                            "same line. A multi-line {# #} comment renders as VISIBLE TEXT in the page "
                            "- use {% comment %}...{% endcomment %} instead."
                        )
                        break
        except Exception:
            pass

    if problems:
        sys.stderr.write(
            "AUTO-VERIFY failed after editing " + os.path.basename(fp) + ":\n- "
            + "\n- ".join(problems) + "\nPlease fix this before continuing.\n"
        )
        return 2

    print(f"[auto-verify] {os.path.basename(fp)}: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
