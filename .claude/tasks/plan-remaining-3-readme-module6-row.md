# Plan 3 — Repair the broken Module 6 row in the README roadmap table

**Created:** 2026-09-19 · **HEAD at authoring:** `0ba7f760` · **Status:** ✅ **COMPLETE — verified 2026-09-21**
**Scope:** `README.md` line 1199 (one line) · **Effort:** tiny — 1 edit, 1 commit

> **CLOSED 2026-09-21 — the fix was already in, landed by `3db5a589`.** Verified from scratch rather
> than assumed: line 1199 now begins `| 6 | Procurement Management System | \`procurement\` |` and the
> table runs 0–23 with no non-row line inside it.
>
> **The prose is provably intact.** The old line was **40,124** chars; the new line is **40,178** — a
> **54-char prepend** (the four cells at 53 chars plus the cell separator space). Confirmed byte-for-byte:
>
> ```
> new.startswith("| 6 | Procurement Management System | `procurement` | ")  -> True
> new[len(prefix):] == old                                                -> True
> ```
>
> So all 40,124 characters of Module 6's status prose survived unchanged — this was a pure prepend,
> exactly as specified. (My first arithmetic check said 53 and looked "off by one"; the discrepancy was
> the trailing separator space in my check string, not a lost character. Worth knowing: **an
> off-by-one in a verification is more often the verifier than the artefact.**)
>
> **One commit, README.md only:** `git show --stat 3db5a589` → `README.md | 4 ++--`, 1 file changed.
> That commit also carried the 7.15 module-7 row update, which is why it is a 2-insertion/2-deletion
> diff rather than 1/1.

---

## Goal

`README.md`'s module roadmap table renders **Module 6 (Procurement) as loose paragraph text and skips
from module 5 to module 7**. The row lost its leading cells.

## The defect, exactly

**Location:** `README.md:1199`
**Introduced by:** commit `1ec9d0d0` — *"docs: README covers 6.16 Supplier Performance & Evaluation"*
(2026-09-07). That commit replaced the row's text but dropped the four leading cells and did not restore
them.

**Current state of line 1199:**

| | |
|---|---|
| length | 40,124 chars |
| starts with | `**19 of 19 sub-modules — Module 6 complete.** **6.16 supplie…` |
| ends with | `…re-seed cannot write into another app's ledger. 143 tests. |` |
| pipe count | **1** (the trailing one) |

**Neighbouring rows for comparison:**

```
line 1198: | 5 | Inventory Management System (IMS) | `inventory` | 🟦 5.1–5.20 built — …
line 1199: **19 of 19 sub-modules — Module 6 complete.** **6.16 supplier performance …
line 1200: | 7 | Project Management | `projects` | 🟦 7.1–7.14 built — …
```

So the table jumps 5 → 7, and because the line is not a table row at all, the entire 40k-character
Module 6 status renders as an unformatted paragraph.

## The fix

**Prepend the four missing cells** — the trailing pipe is already present, so this is a pure prepend and
the existing prose is preserved byte-for-byte:

```
| 6 | Procurement Management System | `procurement` |
```

The result must read:

```
| 6 | Procurement Management System | `procurement` | **19 of 19 sub-modules — Module 6 complete.** **6.16 supplier performance & evaluation** is the layer … 143 tests. |
```

The app slug `procurement` and the title `Procurement Management System` match the header convention
(`| # | Module | App slug | Status |`) and `NavERP.md`'s module index.

### Do it with an Edit, not a rewrite

`README.md` is large and the line is 40k chars — **do not retype it.** Use an `Edit` whose `old_string` is
the line's unique opening and whose `new_string` prepends the cells:

- `old_string`: `**19 of 19 sub-modules — Module 6 complete.**`
- `new_string`: `| 6 | Procurement Management System | \`procurement\` | **19 of 19 sub-modules — Module 6 complete.**`

That anchor is unique in the file.

## Verification

1. **Re-run the table-integrity sweep** — every row between the header (`| # | Module | App slug | Status |`)
   and the end of the table must have the same pipe count as the header, and every line must start with `|`:

   ```bash
   venv\Scripts\python.exe -c "src=open('README.md',encoding='utf-8').read().splitlines(); s=[i for i,l in enumerate(src) if l.startswith('| # | Module | App slug | Status |')][0]; h=src[s].count('|'); print('header pipes',h); [print(i+1, src[i].count('|'), src[i][:60]) for i in range(s+2,len(src)) if src[i].strip() and not src[i].lstrip().startswith('|')]"
   ```

   > Note: a row's pipe count can legitimately exceed the header's when the status text itself contains a
   > `|` inside a code span — that is **not** a defect. The reliable signal is a line that does **not**
   > start with `|`, or a row whose cell count is short.

2. **Confirm all 24 module rows are present** — modules 0–23, none missing:

   ```bash
   grep -c '^| [0-9]* | ' README.md
   ```

3. **Eyeball the rendered table** in a Markdown preview: module 6's row must sit between 5 and 7 with a
   status cell, and no paragraph should appear mid-table.

## Commit

```bash
git add README.md
git commit -m "docs: restore the Module 6 row cells in the README roadmap table"
```

## Done when

- [x] Line 1199 starts with `| 6 | Procurement Management System | \`procurement\` |` — verified 2026-09-21.
- [x] The table has 24 module rows (0–23) and no non-row line inside it — verified: rows at lines
      1193–1216 are all module rows, each with 5 pipes matching the header's 5. (Line 1218 is the prose
      *after* the table, which is correct.)
- [x] Module 6's status text is otherwise unchanged — proven byte-identical by the prefix-strip
      comparison above.
- [x] One commit, `README.md` only — `3db5a589`.

## Note — do this together with Plan 4

Plan 4 updates the **status text** of the module 0 / 3 / 7 rows in this same table. Doing both in one
session avoids two passes over a 40k-character file, but keep them as **separate commits** — this one is a
structural repair, Plan 4's are content updates.
