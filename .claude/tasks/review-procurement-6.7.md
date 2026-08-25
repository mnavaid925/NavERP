# Review wave — procurement 6.7 E-Auction Management (2026-08-26)

Six parallel read-only lanes over the 6.7 changeset (`apps/procurement/{models,forms,views,urls}/EAuctionManagement/`,
`migrations/0010_eauction_management.py`, `_seed_eauction` seeder block, `templates/procurement/eauctionmanagement/**`,
e-auction admin registrations). QA lane: check / seed×2 / smoke_67 / smoke67_post + own tenant-isolation probe — all green.

| Lane | Findings |
|---|---|
| code-reviewer | 9 (3 Medium pace/tie/award-race/type-scope, 6 Low) |
| explorer | 4 (2 Medium context gaps, 2 Low seeder hygiene) |
| frontend-reviewer | 8 (2 Medium styling/poll-zone, 6 Low markup nits) |
| performance-reviewer | 6 (1 High floor N+1, 1 Medium endless polling, 4 Low) |
| qa-smoke-tester | 0 — all commands exit 0 |
| security-reviewer | 6 (1 Critical auth gap, 2 Important, 3 Minor) |

## Consolidated fix list (apply in this order)

| ID | Sev | Status | File | Problem | Fix |
|---|---|---|---|---|---|
| F-SE-01 | Critical | [ ] | views/EAuctionManagement/* | Views are login_required only; vendor-portal logins can create/edit/delete/publish/close/cancel auctions, manage invites, award | `_staff_required` decorator (tenant member or superuser; message+redirect otherwise) on ALL eauc views except `eauc_bid`; define once in Auctions.py, import into Bids.py |
| F-PF-01 | High | [ ] | views/Auctions.py eauc_floor | 2N+1 queries pre-pagination; row.best never rendered | Paginate auction ids first, then ONE grouped EaucBid aggregate for the page; drop dead best_bid call |
| F-SE-02 | Important | [ ] | views/Bids.py _bound_supplier | Inactive/NULL-supplier VPA falls through to STAFF branch ⇒ impersonation | If a binding row exists at all → return (None, True); staff branch only when no VPA row AND user.tenant matches |
| F-CR-01 | Medium | [ ] | models/Bids.py next_floor | earliest-50 slice weakens pace rule past 50 bids | own_best via aggregate Min("amount") |
| F-CR-02 | Medium | [ ] | models/Bids.py next_floor | Rival first bid may EQUAL current best | cap rival first bids at best.amount − 0.01 too |
| F-CR-03 / F-SE-04 | Medium | [ ] | models/Auctions.py award + views/Bids.py | award() unlocked; concurrent POSTs double-award | view: atomic + select_for_update re-fetch; model: once-guard on awarded_supplier_id |
| F-CR-04 | Medium | [ ] | models/Auctions.py AUCTION_TYPES | "forward" selectable but engine reverse-only | restrict choices to reverse (+comment); update migration choices |
| F-SE-03 | Important | [ ] | templates detail/results | reserve_price visible to non-staff | resolved BY F-SE-01 gating; verify bid/floor/board render no reserve afterwards |
| F-EX-01 / F-EX-02 | Medium | [ ] | views eauc_console/eauc_bid | board fragment first paint lacks ranked/recent_bids | shared `_board_ctx(obj)` used by console/bid/board |
| F-FE-01 | Medium | [ ] | forms/Auctions.py EaucInviteForm | bare widgets (no form-select/form-input), no label slots | widget attrs + template label/error rendering |
| F-FE-02 / F-PF-02 | Medium | [ ] | console.html + board endpoint | participation/countdown outside poll zone go stale; polling never stops after close | render hx attributes only while obj.accepts_bids; move extensions footer into board.html; drop dead #countdown id |
| F-CR-05 / F-CR-06 | Low | [ ] | models/Bids.py clean + views/Bids.py | floor=None conflates causes; silent no-op POST when floor None | distinguish exhausted-ladder message; explicit error branch when floor None on POST |
| F-CR-07 | Low | [ ] | models/Auctions.py extension fields | 0 allowed for extension_seconds/max_extensions → fake "extended" | MinValueValidator(1) both + migration |
| F-CR-08 | Low | [ ] | forms/Auctions.py save() | double-submitted invite POST raises IntegrityError 500 | get_or_create semantics |
| F-CR-09 / F-EX-03 / F-EX-04 | Low | [ ] | seed_procurement.py | live auction presets extensions_used=1 w/o pushed closes_at; --flush misses 6.7 rows; docstring/help stale vs 6.7 | extend closes_at by extension_seconds in seed; add flush deletes; update docstring/help |
| F-PF-03..05 | Low | [ ] | views Bids.py + Auctions.py | savings_vs_start re-queries best; total_bids extra COUNT; award-refusal re-query | derive from fetched best; sum ranked counts; reuse leader from award() refusal |
| F-PF-06 / F-FE-03 | Low | [ ] | views/Auctions.py eauc_detail + detail.html | O(invites×ranked) nested loop; empty td fallback | pass dict lookup / participants-style zip; add "—" fallback |
| F-FE-04..08 | Low | [ ] | results/board/bid/floor templates | type=submit outside form; missing novalidate; bare-dash empty states | apply standard markup |
| F-SE-05 | Minor | [ ] | admin.py + views | award_note editable post-award; note uncapped | readonly_fields += award_note; cap 500 chars in view |
| F-SE-06 | Minor | [ ] | detail.html | placed_by identity shown to portal viewers | moot after F-SE-01 (detail is staff-only) — verify and mark |

## Accepted / not-actionable
- QA probe leftovers in dev DB (throwaway parties/auctions) — untracked data only.

## Verification after fixes
`temp\smoke_67.py`, `temp\smoke67_post.py`, `manage.py check`, then the test wave
(`test_eauction_{models,forms,views,security}.py`) must all be green.
