# Punch Category Configuration: Design

Status: **design only**. No code or migration is changed by this document.
Owner: OPERA commissioning domain. Tracks Phase 2 item "Punch categories are project-configurable".

## 1. Current state (verified in code)

- `PunchCategory` is a fixed enum with values `A`, `B`, `C`, `D` (`models_commissioning.py`).
  The database column `commissioning_punch_item.category` is a PostgreSQL enum
  (`commissioning_punch_category`) created by `20261116_0019_opera_commissioning_foundation`.
- **Gate blocking is already project-configurable.** `punch_blocking_categories` per gate
  (`MC`, `RFC`, `RFSU`) is stored in `project.readiness_policy_json`, validated in
  `services/commissioning_readiness_policy.py`, and enforced through `open_critical`
  (`blueprints/commissioning/workflow.py`) and `services/commissioning_readiness.py`.
  It is covered by `test_readiness_policy_changes_punch_blockers_per_gate`.
- **Not configurable:** the set of categories, their labels and meanings, and the
  per-category numbering prefix.

## 2. Dependency inventory

| Location | Dependency on fixed categories | Treatment in the design |
|---|---|---|
| `models_commissioning.py` (`PunchCategory`, `PunchItem.category`) | Enum column | Replace with a code that references a project category definition |
| `services/commissioning_number_service.py` | `PUNCH_KEYS` built from enum; `next_punch_number` | Key by category code, not enum |
| `services/commissioning_readiness_policy.py` | Valid values come from enum | Validate against project definitions |
| `services/commissioning_readiness.py` (line ~168, ~172, ~240) | Gate filter by `category.value`; `open_punch_ab_count` hard-codes `{"A","B"}` | Gate filter unchanged in logic. The `A/B` metric is a legacy label and must be renamed or computed from policy |
| `services/commissioning_dossier_export.py` (lines ~194, ~250) | `category.value` | Use category code and label |
| `blueprints/commissioning/workflow.py` line ~958 | Parses form value into enum | Validate against project categories |
| `blueprints/commissioning/workflow.py` line ~1291 | `legacy_open_ab` uses `PunchCategory.A/B` | Informational only. Keep as legacy metric, rename to make its fixed scope explicit |
| `blueprints/commissioning/workflow.py` lines ~1363, ~2353, ~2358 | Serialize and gate by category value | Use category code |
| `blueprints/commissioning/project.py` line ~147, `workflow.py` line ~329 | `punch_categories=list(PunchCategory)` for forms | Pass project definitions |
| `templates/commissioning/operations.html`, `readiness_policy.html`, `subsystem_dossier.html`, `completion_certificate.html` | Render `category.value` / "Category X" | Render code and label from definitions |
| `scripts/seed_commissioning_demo.py` | Cycles through enum values | Seed default definitions |
| `templates/help/user_guide*.html` | Describe A/B/C/D as fixed | Update to describe configurable categories |
| Tests (`test_commissioning_*`) | Use `PunchCategory.A/B/C` | Keep defaults working; add configurable-category tests |

## 3. Proposed model

New table `commissioning_punch_category` (tenant- and project-scoped):

- `id` (PK), `company_name` (required, indexed), `project_id` (FK, required)
- `code` (string, 1–8 characters, `[A-Z0-9_-]`), unique per `(project_id, code)`
- `label` (string, required, ≤ 120 characters): shown in UI and exports
- `description` (text, optional): meaning of the category, for procedures
- `sort_order` (int), `is_active` (bool). Inactive categories cannot be selected for new items but remain valid for existing items
- `created_at`, `updated_at`, `created_by_id`

`PunchItem` gets `category_code` (string, FK to the definition on `(project_id, code)`).
The old enum column is kept during the transition.

Default definitions: when a project has no definitions, the application uses
the historical A/B/C/D definitions (labels only, no implied meaning). Existing
behaviour and readiness defaults are unchanged.

## 4. Migration strategy (additive, reversible in steps)

Each step is a separate pull request, verified by CI before merge. The CI
`integration` job runs migrations on an empty PostgreSQL database and runs the
forward upgrade from `20260922_0015`.

1. **P1 — additive schema.** Create `commissioning_punch_category`. Add nullable
   `category_code` to `commissioning_punch_item`. No reads change. Test: migration
   applies on empty and upgraded databases; model constraints (unique code per project,
   tenant scope).
2. **P2 — backfill and dual write.** Backfill definitions A–D per existing project
   with historical labels. Backfill `category_code` from the enum. Write both
   columns on create. Test: backfill is idempotent; every existing item has a code.
3. **P3 — read path.** Readers (readiness, number service, dossier export,
   templates, forms) use `category_code` and definitions. Enum remains as a fallback
   for rows created before P2. Tests: custom category blocks a gate only when configured;
   numbering uses custom code; unknown code is rejected.
4. **P4 — management UI and API.** Project owners create, rename, deactivate
   categories. Changes are audited. Permission: `project.manage`. Tests: viewer and
   engineer cannot manage categories; tenant isolation; invalid codes rejected.
5. **P5 — retire the enum.** Only after production data has been verified. Drop the
   enum column in a separate migration with a verified backup. Not before.

Downgrade is not automatic (`docs/DEPLOYMENT_GUIDE.md` §8).

## 5. Rules that must not change

- A signed-off check sheet and a closed Punch item are never silently changed by
  a category edit. Category changes on an existing item are audited and limited to
  open items.
- Deactivating a category never removes it from existing items or history.
- Readiness results must be reproducible from the policy snapshot stored in each certificate.
- The numbering counter per category must remain tenant-scoped and atomic.

## 6. Acceptance criteria (for completion of this item)

- A project can define its own category set; readiness gates block only on
  categories configured for that gate.
- Historical projects keep working without any action (A–D backfilled).
- Every category change is in the audit log with before and after values.
- Documentation (`USER_MANUAL.md`, `help/user_guide*.html`) describes the configurable behaviour.
- All tests above exist and pass in CI.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Existing certificates reference A/B wording | Certificates store issue-time snapshots; no re-rendering with new labels |
| Dual-write divergence between enum and code | Backfill test and constraint check in P2; enum removed only in P5 |
| Performance of joins on definitions | Index on `(company_name, project_id, code)`; definitions are small |
| Persian or non-Latin labels | Code is restricted to ASCII; labels are free text, length-limited |

## 8. Not in scope

- Automatic classification of categories from severity.
- Cross-project shared category catalogues (may be considered later).
