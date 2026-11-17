# Configurable Subsystem Dossier Index

OPERA supports project-level rules for the mandatory engineering documents included in each subsystem dossier. Project administrators manage these rules from **Commissioning Operations → Configurable dossier index**.

## Rule fields

- **Document type:** document-register classification matched without case sensitivity.
- **Discipline:** a discipline code/name, or `ANY` to accept any discipline.
- **Minimum count:** number of current document revisions that must qualify (1–1000).
- **Must be approved:** when enabled, only current documents with status APPROVED qualify.
- **Evidence required:** when enabled, a current document must have at least one linked OPERA attachment record.

Rules are scoped to one company and project. Duplicate combinations of document type and discipline are rejected. A rule can be updated or deactivated; deactivation is audited and does not delete its history.

## Dossier evaluation

For each active rule, OPERA:
1. Selects the latest revision for each document number in the subsystem.
2. Matches the document type and discipline.
3. Applies the approval and evidence requirements.
4. Compares qualifying current documents with the configured minimum count.
5. Displays the qualifying count and PASS/MISSING result.

Superseded document revisions are not counted. An attachment record is evidence metadata; actual file durability still depends on the configured evidence-storage backend. The current local-filesystem adapter must not be treated as durable on Vercel/serverless.

## Default when no project index exists

For backward compatibility, if a project has no active dossier index rules, the dossier requires at least one current engineering document and requires all current document revisions to be APPROVED. Missing documents do not pass.

## Governance
Project administrators must obtain engineering/client approval for the document types, disciplines, minimum counts, approval requirements and evidence requirements. Record the governing procedure and revision in the controlled Document Register. Revisit the index when the contract, ITP, systemization or turnover requirements change.

The dossier page is an evidence-based readiness view. It does not itself issue MC/RFC certificates or accept custody. Full revision-controlled PDF/ZIP dossier compilation remains a separate implementation increment.
