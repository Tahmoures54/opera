# Handover ↔ Readiness Engine Integration

**Status:** Helpers are live in `services/commissioning_handover_gates.py`.  
**Next action:** Drop the three calls below into `blueprints/commissioning/workflow.py::transition_handover`.

## Why this approach

The original `transition_handover` contains long ad-hoc queries for punch clearance and sheet sign-off. Those checks are now centralized in the Readiness Engine so that:

- MC / RFC / RFSU rules stay consistent with progress reporting.
- Error messages list every blocker instead of a single generic sentence.
- Future project-specific rule overrides can live in one place.

## Exact patch to apply

Inside `transition_handover`, replace the existing sheet/punch checks for each gate with the following.

### 1. Import (top of workflow.py)

```python
from services.commissioning_handover_gates import (
    require_ready_for_mc,
    require_ready_for_rfcc,
    require_ready_for_rfsu,
)
```

### 2. MC_CERTIFIED branch

Replace the block that queries all sheets and open_critical punches with:

```python
if target == HandoverStatus.MC_CERTIFIED:
    if not has_permission(package.project_id, "handover.manage") or old != HandoverStatus.DRAFT:
        abort(403)
    # Centralized OPERA readiness gate (Pre-Comm sheets + Punch A/B + Holds)
    require_ready_for_mc(package.company_name, subsystem_id)
    package.status, package.mc_issued_by_id = target, current_user.id
    # ... keep existing certificate_number / date / CommissioningCertificate creation ...
```

### 3. RFC_CERTIFIED branch

```python
elif target == HandoverStatus.RFC_CERTIFIED:
    if not has_permission(package.project_id, "handover.manage") or old != HandoverStatus.MC_CERTIFIED:
        abort(403)
    require_ready_for_rf(package.company_name, subsystem_id)
    package.status, package.rfc_issued_by_id = target, current_user.id
    # ... keep existing RFC certificate issuance ...
```

### 4. RFSU branch

```python
elif target == HandoverStatus.RFSU:
    if not has_permission(package.project_id, "handover.manage") or old != HandoverStatus.RF_CERTIFIED:
        abort(403)
    require_ready_for_rfsu(package.company_name, subsystem_id)
    package.status = target
```

## Behaviour after the patch

- Attempting MC while any Punch A/B is open, any Hold is unreleased, or any Pre-Comm A/B sheet is not SIGNED_OFF → HTTP 409 with a list of concrete blockers.
- RFC additionally requires all Comm-C and Functional-Test sheets to be signed-off.
- RFSU additionally requires every task in the subsystem to be COMPLETED or CANCELLED.

## Verification

1. Create a subsystem with one open Punch A → MC transition must fail with a clear message.
2. Clear the punch and sign all Pre-Comm sheets → MC succeeds.
3. Leave a Comm-C sheet unsigned → RFC fails.
4. Complete remaining tasks → RFSU succeeds.

## Notes

- The Readiness Engine currently treats *all* Pre-Comm and Comm sheets as required. If a project later needs a configurable “required sheet set”, extend `evaluate_subsystem_readiness` rather than re-introducing ad-hoc queries in the blueprint.
- Certificate snapshot and immutable `CommissioningCertificate` records remain unchanged.
