"""4.15 empty states — the branch no smoke sweep in this project had ever rendered.

WHY THIS FILE EXISTS, and why it is committed rather than living in ``temp/``:

Every smoke sweep in this repo logs in against a **seeded** tenant. A seeded tenant has rows in every
table by construction, so the ``{% empty %}`` / ``.empty-state`` branch of every list and report
template is never rendered, and any link inside it is never followed. Two 4.14 defects lived exactly
there and both shipped — *both returned 200*, so a status-only assertion could not have caught either.
They were found by a human reading the template.

The subtler half, and the reason "we already have an empty-tenant test" was not a defence: 4.14 HAD an
empty-tenant smoke test and HAD a dead-link sweep, and both were green. The link sweep only ever ran
against the seeded tenant, so the two bad anchors were never in the HTML it read. **Two checks each
covering half of a thing look exactly like full coverage** — worse than a missing check, which at
least shows up as an absence.

The harnesses that first caught this (``temp/verify_links.py`` and its 4.15 copy) are **gitignored**,
which means every rule about them is enforced only by memory — and both copies shipped with a
fixed throwaway-tenant slug and an unguarded teardown that leaked a tenant into the shared dev
database, because the second copy was made by adapting the first rather than by re-deriving it. This
file is that check moved into the committed suite, which is the only place a rule can grow teeth.

Note what makes the leak bug *structurally impossible* here rather than merely fixed: this module
creates **no tenant of its own**. ``client_a`` is a tenant admin whose workspace simply has no 4.15
rows, because no ``cc_*`` fixture is requested — and pytest rolls the transaction back regardless.
There is no slug to collide and no teardown to forget.

Every assertion below reports its **denominator**. A sweep that follows zero anchors and reports no
failures is this repo's most common false green — the first rewrite of the 4.14 harness did exactly
that by applying a template-source regex to rendered HTML.
"""
import re

import pytest
from django.urls import reverse

# Rendered HTML, so this matches a real href. NOT ``{% url %}`` — that no longer exists by the time
# the page reaches a browser, and matching against it is how the original harness scanned nothing at
# all while reporting a confident pass.
_CC_ANCHOR = re.compile(r'<a\s[^>]*href="(/[^"#]*)"')

# Every argument-free 4.15 page, so the sweep covers what the EMPTY branch renders. The report pages
# appear once per ``?view=`` because each view has its own empty state with its own call to action.
_CC_EMPTY_PAGES = [
    ("scm:coldchainmonitor_list", ""),
    ("scm:temperaturereading_list", ""),
    ("scm:temperatureexcursion_list", ""),
    ("scm:cold_storage_report", ""),
    ("scm:cold_storage_report", "?view=on_hand"),
    ("scm:cold_storage_report", "?view=mismatch"),
    ("scm:cold_storage_report", "?view=expiring"),
    ("scm:cold_storage_report", "?view=quarantined"),
    ("scm:cold_storage_report", "?view=unmonitored"),
    ("scm:cold_chain_compliance_report", ""),
    ("scm:reefer_board", ""),
]

# Create pages are swept for 200s, comment leaks and dead links, but are NOT required to render an
# empty state: a form is not a listing. `temperatureexcursion_create` happens to have one (it asks you
# to pick a monitor and there are none) and `coldchainmonitor_create` correctly does not — asserting
# an empty state on both would have forced a decorative one onto a page that does not need it.
_CC_EMPTY_FORM_PAGES = [
    ("scm:coldchainmonitor_create", ""),
    ("scm:temperatureexcursion_create", ""),
]

# Value slots only. The zero-rendering rule is about a FIGURE reading as 0 where it means "absent" —
# the prose on these pages legitimately says things like "an MKT of 0.00 °C would read as a
# perfectly-cold store", and a naive whole-page substring match flags the sub-module's own
# explanation of the invariant as a violation of it. It did, on the first run.
_CC_VALUE_SLOT = re.compile(r"<(?:td|dd)\b[^>]*>(.*?)</(?:td|dd)>", re.S)


def _cc_empty_paths(include_forms=True):
    """The 4.15 pages as request paths. Kept a function so a bad url name fails loudly at call time."""
    pages = list(_CC_EMPTY_PAGES) + (list(_CC_EMPTY_FORM_PAGES) if include_forms else [])
    return [reverse(name) + query for name, query in pages]


@pytest.mark.django_db
class TestColdChainEmptyStates:
    """``client_a`` is a tenant admin with ZERO 4.15 rows — no ``cc_*`` fixture is requested, so every
    page below renders its empty branch rather than a table."""

    def test_every_page_renders_200_with_no_cold_chain_rows(self, client_a):
        """A page that 500s on an empty workspace is invisible to every seeded check we run."""
        paths = _cc_empty_paths()
        assert paths, "no 4.15 pages configured — the sweep would pass over nothing"
        broken = [(p, client_a.get(p).status_code) for p in paths]
        broken = [(p, code) for p, code in broken if code != 200]
        assert not broken, "pages not returning 200 on an empty workspace: %s" % broken

    def test_the_empty_state_branch_actually_renders(self, client_a):
        """Fails loudly if a future seeder or default filter stops this branch being reached.

        This is the assertion the 4.14 harness was missing: it is not enough that the page is 200,
        because the defect this file exists for returned 200."""
        missing = []
        for path in _cc_empty_paths(include_forms=False):
            html = client_a.get(path).content.decode()
            if "empty-state" not in html:
                missing.append(path)
        assert not missing, (
            "these pages rendered no .empty-state block on a workspace with zero 4.15 rows, so "
            "nothing below is being checked on them: %s" % missing)

    def test_every_link_rendered_on_an_empty_workspace_accepts_GET(self, client_a):
        """The 4.14 defect exactly: an ``.empty-state`` call to action pointing at a POST-only route.

        It renders as an ordinary link and is a guaranteed 405 on click, and nothing about the page
        suggests it is broken until somebody presses it. Checked by actually issuing the GET, which is
        what a click does — a decorator-attribute probe reports a confident, wrong **zero**, because
        ``require_http_methods`` keeps its method list in a closure."""
        seen, bad = set(), []
        for path in _cc_empty_paths():
            html = client_a.get(path).content.decode()
            for match in _CC_ANCHOR.finditer(html):
                target = match.group(1).replace("&amp;", "&")
                if target in seen or not target.startswith("/scm/"):
                    continue
                seen.add(target)
                code = client_a.get(target).status_code
                if code == 405:
                    bad.append("%s links to %s -> 405 (POST-only route)" % (path, target))
                elif code >= 500:
                    bad.append("%s links to %s -> %s" % (path, target, code))
        # The denominator, asserted rather than assumed. Zero anchors followed and zero failures is
        # indistinguishable from a clean sweep, and is how the original harness passed while blind.
        assert len(seen) >= 10, (
            "only %d in-app links were followed across %d pages — too few to be a real sweep; the "
            "anchor pattern has probably stopped matching the rendered HTML"
            % (len(seen), len(_CC_EMPTY_PAGES)))
        assert not bad, "\n".join(bad)

    def test_no_cold_chain_page_leaks_a_template_comment_when_empty(self, client_a):
        """Django ``{# #}`` comments are single-line only; a multi-line one leaks onto the page.

        Checked on the EMPTY branch specifically, because that markup is the least-viewed in the
        sub-module and therefore the most likely to carry an unreviewed note."""
        leaked = []
        for path in _cc_empty_paths():
            html = client_a.get(path).content.decode()
            for marker in ("{#", "{% comment", "{% if", "{% for"):
                if marker in html:
                    leaked.append("%s leaks %r" % (path, marker))
        assert not leaked, leaked

    def test_a_missing_temperature_never_renders_as_zero_on_an_empty_workspace(self, client_a):
        """Blank-vs-zero is this sub-module's whole contract, and the empty branch is where every
        figure is absent at once — so it is the strongest place to assert it.

        ``0.00 %`` time-in-range means "never in range"; the opposite of "no readings". Likewise a
        bare ``0`` °C is a real chilled temperature, not a missing one.

        Checked in VALUE SLOTS only (``<td>`` / ``<dd>``), not across the whole page. The first
        version matched the whole document and flagged
        ``"an MKT of 0.00 °C would read as a perfectly-cold store"`` — the excursion form's own
        explanation of this exact rule. A check that cannot tell a figure from a sentence about
        figures fails on the code that documents it best."""
        offenders = []
        checked = 0
        for path in _cc_empty_paths():
            html = client_a.get(path).content.decode()
            for slot in _CC_VALUE_SLOT.findall(html):
                checked += 1
                for wrong in ("0.00 %", "0.00 °C", "0.00°C"):
                    if wrong in slot:
                        offenders.append("%s renders %r in a value slot with no data behind it"
                                         % (path, wrong))
        assert checked, "no <td>/<dd> value slots were examined — the pattern has stopped matching"
        assert not offenders, offenders
