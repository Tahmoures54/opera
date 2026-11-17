# Check Sheet and Test Sheet Templates

OPERA provides a project-scoped template library for reusable Check Sheet and Test Sheet structures.

## Template lifecycle
1. A user with `checksheets.manage` creates a DRAFT template with a unique project template code, title, Check Sheet type, discipline, optional equipment type, overall acceptance criteria and 1–100 inspection items.
2. Each item records description, expected result, item-level acceptance criteria, unit, measurement type, optional numeric limits, mandatory flag and witness-required flag.
3. A manager approves the draft. Approved template content is immutable.
4. To change an approved template, create the next revision. The new revision starts as DRAFT; after approval, the previous revision becomes RETIRED.
5. Templates are retained; they are not hard-deleted.

## Instantiating a Check Sheet
When creating a Check Sheet, select an approved template. OPERA validates the Check Sheet type and, when the template declares an equipment type, requires a matching equipment tag. It copies the template items into the Check Sheet and stores a complete template/revision snapshot on the Check Sheet.

Later template revisions do not alter already-created Check Sheets. A revision of a signed-off Check Sheet copies the original template snapshot and item definitions.

## Execution and sign-off
- At least one item must be mandatory before a Check Sheet can be issued.
- All mandatory items must be completed before sign-off.
- Any NOK result blocks sign-off.
- Completed mandatory or optional items require independent QC verification.
- Witness-required items require their associated witness points to be released before sign-off.
- Optional items may remain PENDING; they do not block sign-off unless they are performed and fail.

## Governance
Template item content and acceptance criteria must be derived from approved project procedures, ITPs, OEM documents or contract requirements. OPERA validates structure and workflow; it does not invent technical acceptance criteria.

Template JSON must be an array of 1–100 objects. Each object supports: `description`, `expected_result`, `acceptance_criteria`, `unit`, `measurement_type` (`QUALITATIVE` by default or `NUMERIC`), `minimum_value`, `maximum_value`, `witness_required` and `mandatory`. Numeric measurements require a unit. Limits are optional and are validated to fit 16 integer digits and 8 decimal places.
```json
[
  {
    "description": "Verify equipment tag and nameplate",
    "expected_result": "Matches approved equipment register",
    "acceptance_criteria": "No mismatch",
    "unit": "mm/s",
    "measurement_type": "NUMERIC",
    "minimum_value": "2.5",
    "maximum_value": "5.0",
    "witness_required": false,
    "mandatory": true
  }
]
```

See the Commissioning Operations page for template creation, revision, approval and Check Sheet instantiation.


## Numeric measurement capture

Approved Check Sheet templates may define individual items as either `QUALITATIVE` (the default for existing templates) or `NUMERIC`. Numeric items require a unit and may define an approved minimum and/or maximum value. During execution, the operator records the numeric reading separately from the qualitative result status. An item may be marked `OK` only when its reading is within every configured limit; an out-of-range reading must be recorded as `NOK` or corrected. Numeric readings, units, item type and result status are included in the append-only audit event. Existing templates and manually added items remain qualitative unless explicitly configured as numeric.

Limits must come from the approved project/OEM procedure. OPERA does not invent measurement ranges or tolerance values.
