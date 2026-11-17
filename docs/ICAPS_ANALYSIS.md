# ICAPS Functional & Technical Analysis

**Assessment date:** 17 November 2026  
**Scope:** Public TotalEnergies ICAPS Mobiweb product information and an independently hosted project ICAPS manual (project-specific, version 3.21 / 2013). This is a source-bounded analysis, not a claim of access to the current ICAPS application, its installer, tenant database, administrator manual, or current customer configuration.

## 1. Evidence register and confidence

| Ref | Source | What it supports | Confidence / limitation |
|---|---|---|---|
| S1 | [TotalEnergies ICAPS product page](https://icaps.mobiweb.totalenergies.com/icaps) | Product purpose, roles, check/test sheets, operational tests, handover, Excel import/export, preservation, reporting, sequencing, punch list | High for public product positioning; not a field-level manual |
| S2 | [TotalEnergies OPERCOM methodology](https://icaps.mobiweb.totalenergies.com/our-methodology) | Lifecycle scope, system/subsystem breakdown, preparation/execution, disciplines, test sheets and traceability | High for methodology overview; detailed contractual procedures remain project-specific |
| S3 | [TotalEnergies training/support](https://icaps.mobiweb.totalenergies.com/formations) | Engineering preparation, task definition, status-index preparation, commissioning dossier, resource estimate, conformity/static/piping tests, functional/operational tests, punch clearance | High for published training scope |
| S4 | [ICAPS Engineering Manual R3.10, externally hosted copy](https://www.scribd.com/document/411212418/ICAPS-Engineering-Manual-R3-10-pdf) | Historical database hierarchy, import concepts, task/activity/progress relationships and selected numbering rules | Medium/low: historical copy, third-party host, not independently authenticated as current product behavior |
| S5 | [Project ICAPS Manual, version 3.21, externally hosted copy](https://pdfcoffee.com/icaps-manual-pdf-free.html) | A 2013 project manual's task types, list fields, user levels, dossier printing and punch details | Medium/low: project-specific and explicitly carries a company confidentiality notice; used only as a high-level factual reference, not copied |
| S6 | [Commissioning dossier template example](https://img1.wsimg.com/blobby/go/09f0ef90-bff0-456e-a29c-0d6d48226dbe/downloads/Commissioning%20Template%20Dossier.pdf?ver=1555594913416) | Example dossier index structure and document checklist | Medium/low: project-specific example, not a universal ICAPS form |

### Not available during this assessment
- Current ICAPS installer or live tenant access.
- Current User Manual and Administrator Manual.
- Current import/export annex and exact workbook schemas.
- Authorized database schema or sample database.
- A representative project export and signed blank forms from the user's project.

Consequently, the exact current ICAPS menu tree, all fields, workflow transitions, permission matrix, report catalogue, validation rules and current punch categories remain **unverified**. They must not be inferred from the historical project manual.

## 2. Product purpose and user roles

The current public product description positions ICAPS as a tool for preparing and monitoring Mechanical Completion / Pre-commissioning and Commissioning, with traceability of tests, detection and closure of anomalies, and a clear Construction-to-Operations interface (S1).

The public product page describes three broad operational profiles:
- **Local administrator:** application configuration, administration and data installation.
- **Superintendent:** installs data items and sequences, prepares tasks and certificates, manages punch lists.
- **Operator / executor:** executes tasks, accesses reference documents, raises anomalies and attaches pictures (S1).

A 2013 project manual describes four access levels for its specific deployment. That historical project-specific role model is not treated as the current global ICAPS permission model (S5).

## 3. Published functional areas

| Area | Confirmed function at public-product level | Inputs / outputs known from sources | Unverified detail |
|---|---|---|---|
| Project data preparation | Engineering data is loaded through Excel import/export and an internal data model (S1, S2) | Engineering lists / workbook data; project database | Current workbook names, mandatory columns, error log layout |
| Physical breakdown | System and subsystem breakdown is a core OPERCOM preparation activity (S2, S3) | Project equipment and system boundaries | Exact current hierarchy depth and tag field schema |
| Task preparation | Task definition and sequencing are preparation activities (S1, S3) | Task, equipment association, discipline, sequence | Current dependency engine and all task attributes |
| Pre-commissioning | Check/test sheets and operational follow-up (S1) | Executed checks and test records | Current sheet library and detailed acceptance logic |
| Commissioning | Operational tests and test sheets (S1, S3) | Functional and operational execution records | Exact test-pack and certificate rules by release |
| Punch list | Tracking from creation to closure (S1) | Defect/anomaly, assignment and clearance evidence | Current category definitions and closure approval matrix |
| Handover | Milestones, procedures and certificates for transfer of responsibility (S1) | Dossier and acceptance evidence | Current certificate names, signatures and gates |
| Preservation | Dedicated preservation module and associated check/test sheets (S1) | Preservation activities and records | Scope, triggers, frequencies and sheet catalogue |
| Reporting | More than 30 reports/dashboards are advertised (S1) | Ground execution data | Names, calculations, filters and export formats |
| Sequencing | A module plans and breaks down future activities (S1) | Activity sequence / plan | Critical-path, predecessor and resource scheduling rules |

## 4. Historical task/activity taxonomy

The historical project ICAPS manual identifies these activity codes (S5):
- **CCK** — Conformity Check
- **STS** — Static Test
- **PIP** — Piping Test
- **PRC** — Preliminary Check
- **FTS** — Functional Test
- **OTS** — Operational Test
- **PVP** — Piping and Vessel Preparation

The historical engineering manual describes four conceptual branches (S4):
1. Equipment Branch — hierarchical physical equipment breakdown.
2. Task Branch — Pre-commissioning and Commissioning tasks associated with equipment, progress substage, task activity and one or more disciplines.
3. Progress Branch — project sequence represented as project / subproject / stage / substage in that historical model.
4. Punch List Branch — punch items managed across the project.

This is an evidence-backed conceptual reference for OPERA's independent design. It is not represented as the exact schema of current ICAPS Mobiweb.

## 5. Execution lifecycle supported by published sources

The public OPERCOM overview covers contract and engineering preparation through construction, completion, commissioning and start-up (S2). Published training material distinguishes engineering preparation from execution and lists examples such as:
- Engineering / preparation: system and subsystem breakdown, database preparation, dossier and certificate preparation, task definition, resource estimates and operational test procedure preparation (S3).
- Pre-commissioning execution: conformity checks, static tests, vessels and piping tests, dossier compilation and punch clearance (S3).
- Commissioning execution: preliminary checks, functional tests, operational tests, piping/vessel preparation for start-up, dossier compilation and punch clearance (S3).

These activity names are not sufficient to define a universal pass/fail workflow. Acceptance criteria, safety prerequisites, witness requirements and certificate gates must be configured from the applicable project specifications and approved procedures.

## 6. Document and dossier evidence

Public sources confirm check/test sheets, procedures, dossiers, certificates and traceability as core elements (S1-S3). A project dossier example contains a subsystem definition, commissioning documentation, pre-start-up activities, vendor documentation and a review/observation area (S6).

The exact ICAPS blank form templates, their controlled revisions, page layouts, signature fields and print styles are not available. OPERA must therefore create its own configurable templates and must not brand them as official ICAPS forms.

## 7. Import/export and data validation

Public ICAPS material confirms Excel-based data import/export and an internal connected data model (S1). Historical engineering material describes type-based import/export rules, project database identifiers and import logs (S4). Exact current validation rules and workbook contracts are not available.

OPERA implementation rule:
- Publish its own versioned Excel templates and field dictionary.
- Validate project, system, subsystem, equipment/tag, task, activity and discipline references before commit.
- Produce row-level import errors and a dry-run summary.
- Reject cross-project and cross-tenant references.
- Never silently remap identifiers or overwrite approved execution records.

## 8. Punch list

The public ICAPS description confirms a dedicated punch list lifecycle from creation through closure (S1). A project-specific historical manual shows details such as punch number, category, subsystem, equipment, discipline, originator, date, action party, defect description, corrective action and clearance roles (S5).

The exact current ICAPS categories and their contractual meanings are not confirmed. OPERA's existing A/B/C/D enum is an OPERA configuration, not a verified claim about current ICAPS. Category definitions and closure rules must be project-configurable and approved by the client.

## 9. Reporting and progress

ICAPS publicly advertises detailed progress reporting and more than 30 reports/dashboards (S1). The historical manual indicates progress data is tied to task and equipment branches (S4). The actual current formulas and denominators are unknown.

OPERA must calculate progress only from its persisted execution records and approved weights. Empty denominators must display “Not available” or 0 with an explicit denominator, not a fabricated progress percentage.

## 10. Outstanding evidence required

To elevate this report from source-bounded analysis to a full release-specific reverse-engineering assessment, obtain authorized copies of:
1. Current ICAPS Mobiweb User Manual.
2. Current Administrator Manual and permission matrix.
3. Current Engineering Manual and import/export annex.
4. Blank check/test sheets, certificates, dossier index and punch form.
5. Redacted sample import/export workbooks and import error logs.
6. Redacted sample project export and report catalogue.
7. Confirmation of product release/version and client-specific OPERCOM deviations.

**Conclusion:** ICAPS's public capabilities and a historical project manual establish a reliable conceptual baseline. They do not establish the complete behavior of the current application. OPERA's implementation is independently designed and explicitly records that boundary.
