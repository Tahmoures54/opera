# Handover ↔ Readiness Engine Integration

**Status:** MC, RFC and RFSU readiness gates are wired into the handover transition workflow.  
**Certificate lifecycle:** MC and RFC certificates are issued as immutable issue-time records. RFSU is a gated readiness transition followed by Operations Acceptance.

## Implemented handover sequence

`DRAFT → MC_CERTIFIED → RFC_CERTIFIED → RFSU → ACCEPTED`

- **MC:** `require_ready_for_mc` checks the pre-commissioning readiness criteria.
- **RFC:** `require_ready_for_rfc` checks MC prerequisites plus Commissioning C / Functional Test completion.
- **RFSU:** `require_ready_for_rfsu` checks RFC prerequisites, remaining Punch A/B blockers and task completion.
- **Operations Acceptance:** only a user with `handover.accept` can accept or reject after RFSU.

## RFC certificate issuance

When a package transitions from `MC_CERTIFIED` to `RFC_CERTIFIED`, OPERA:

1. Enforces the project-scoped `handover.manage` permission.
2. Evaluates the RFC readiness gate before changing the package state.
3. Requires a certificate number and issue date in the operations form.
4. Enforces a company-wide unique certificate number.
5. Stores the authenticated issuer and issue timestamp.
6. Captures an immutable issue-time snapshot of the project, subsystem, package, readiness metrics, check sheets, documents, Punch items, witness/hold points, equipment and tasks.
7. Writes a `COMPLETION_CERTIFICATE_ISSUED` audit event and a handover status audit event in the same transaction.
8. Exposes the issued record through the printable RFC certificate view.

The certificate route accepts `RFC`. The former `RF` route remains a compatibility alias. Existing `RF` certificate types and `RF_CERTIFIED` / `RF_PENDING` handover values are migrated to `RFC`, `RFC_CERTIFIED` and `RFC_PENDING`. The old package-column names remain mapped internally to avoid dropping or rewriting legacy references; application code uses RFC names.

## Project-configurable policy

The project Readiness policy is stored in `CommissioningProject.readiness_policy_json` and managed by users with `project.manage`. It independently configures blocking Punch categories, required Check Sheet types for MC/RFC/RFSU, Hold-point blocking gates, Check Sheet presence requirements and whether all tasks must be complete before RFSU. Defaults preserve the previous OPERA A/B Punch and Check Sheet assumptions. Invalid stored policy data fails all readiness gates closed. Issued MC/RFC certificate snapshots include the effective policy and gate-specific issues. See [READINESS_POLICY.md](READINESS_POLICY.md).

## Verification scenarios

1. An open Punch A/B, unreleased Hold point or unsigned required Pre-Comm sheet blocks MC with HTTP 409.
2. A missing Comm-C / Functional Test sign-off blocks RFC.
3. RFC issuance with a duplicate company certificate number is rejected.
4. RFC issuance captures the authenticated issuer, issue date and evidence snapshot.
5. Attempting to mutate an issued certificate snapshot is rejected by the append-only model guard.
6. The `/certificates/RFC` and legacy `/certificates/RF` URLs resolve to the same RFC certificate.
7. Incomplete commissioning tasks or remaining blockers prevent RFSU.

## Important limitations

- Electronic sign-off is an authenticated acknowledgement, not a qualified cryptographic signature.
- The readiness rules are OPERA's configured baseline. Project contracts, approved completion procedures, ITPs and authority matrices remain authoritative.
- The Readiness Engine currently treats all registered Pre-Comm and Commissioning / Functional Test sheets in scope as required. Project-specific required-sheet configuration remains future work.
