"""Guards on the shape of the SCM test suite itself.

These assert nothing about the product. They exist because the suite's own files are now large enough
(``test_views.py`` is over 14 000 lines and grows with every sub-module) that a mistake in *them* is
hard to see and expensive to diagnose.

The case that prompted this: a sub-module's tests appended a second module-level ``_messages`` helper
to ``test_views.py``. Python binds the LAST definition, so every earlier caller silently got the new
one — and the two returned different types (a list of strings vs. one joined lowercase string). Nine
unrelated quality tests began failing on ``any("..." in m for m in _messages(resp))``, which iterated
a string character by character and matched nothing. Nothing pointed at the cause: the failures were
in a sub-module nobody had touched, the diff that broke them was pure addition, and the shadowed name
appeared correct at both definition sites.

The bisect to find it cost more than this file will ever cost to run.
"""
import ast
import pathlib

import pytest

TESTS_DIR = pathlib.Path(__file__).resolve().parent

#: Every test module in this package, plus conftest — the files where an appended helper can shadow
#: an existing one. Sorted so a failure names the same file across runs.
TEST_FILES = sorted(
    path for path in TESTS_DIR.glob("*.py")
    if path.name != "__init__.py"
)


def _module_level_definitions(path):
    """``{name: [line, ...]}`` for every top-level ``def``/``class``/simple assignment in ``path``.

    Only module scope. A method redefined inside a class is a different (and much more visible)
    problem, and nested helpers are scoped to their function, so neither can shadow across the file.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    seen = {}
    for node in tree.body:
        names = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        for name in names:
            seen.setdefault(name, []).append(node.lineno)
    return seen


@pytest.mark.parametrize("path", TEST_FILES, ids=lambda p: p.name)
def test_no_module_level_name_is_defined_twice(path):
    """A second definition of a module-level name silently rebinds it for the WHOLE file.

    Including for every call site written above it, which is what makes this invisible: the earlier
    tests still read as correct and still call the name they always called.
    """
    duplicates = {
        name: lines for name, lines in _module_level_definitions(path).items()
        if len(lines) > 1
    }
    assert not duplicates, (
        f"{path.name} defines these module-level names more than once: "
        + "; ".join(f"{name} at lines {lines}" for name, lines in sorted(duplicates.items()))
        + ". Python binds the last one, so every earlier caller silently gets it. Rename the new "
          "definition rather than shadowing the existing one."
    )
