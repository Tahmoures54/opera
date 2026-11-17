# OPERA — Commissioning, Pre-Commissioning & Start-up

**OPERA** is a project-scoped commissioning and start-up management platform for EPC, industrial and construction projects. It provides controlled project/system/subsystem structure, check-sheet execution, punch management, witness/hold points, Mechanical Completion (MC), Ready for Start-up (RFSU), handover and progress evidence.

OPERA is an independent product focused exclusively on Operations, Pre-commissioning, Commissioning, Systemization, Mechanical Completion, Handover and project readiness. Its Flask, SQLAlchemy, Alembic, authentication, TOTP and tenant-security infrastructure is maintained as OPERA infrastructure.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Flask](https://img.shields.io/badge/Flask-3.x-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Product capabilities

- Project → System → Subsystem → Equipment hierarchy.
- Commissioning Task Register with CCK / STS / PIP / PRC / FTS / OTS / PVP activity codes, discipline, progress stage/substage, man-hours, dates and links to equipment and check sheets.
- Project-scoped membership and OPERA roles, independent from legacy account roles.
- Pre-commissioning A/B, commissioning C and functional-test check sheets.
- Sequential numbering, item-level results, independent QC verification, issue/rejection workflow and two-party sign-off.
- Signed-off check sheets are immutable; corrections create a new revision.
- Punch A/B/C/D, project-member assignment, closure, independent verification and controlled waiver with history.
- Witness, Hold and Review point scheduling, attendance and release.
- MC / RF certification, RFSU and operations acceptance gates.
- Progress snapshots, project audit evidence and private PDF/image/text/CSV attachments for check sheets, Punch items and handover packages.
- Tenant-scoped database constraints and authorization checks.

## Quick start

```bash
git clone https://github.com/Tahmoures54/opera.git
cd opera
python -m venv .venv
# Linux/macOS
source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env
```

Set a unique SECRET_KEY and a database URL in .env. For local development, SQLite is supported; PostgreSQL is recommended for shared and production deployments.

```bash
python -c "import secrets; print(secrets.token_hex(32))"
flask --app wsgi db upgrade
python app.py
```

Open http://127.0.0.1:5000 and sign in using an existing OPERA-enabled account. The account's company boundary is reused as the OPERA tenant boundary.

The application exposes only OPERA product workflows. Legacy procurement, warehouse, supplier, delivery, intelligence, generic reporting and role-workspace routes have been removed. Historical database mappings and migration history remain temporarily for safe upgrades; see [Legacy database compatibility](docs/LEGACY_DATA_COMPATIBILITY.md). Shared authentication, TOTP, sessions and project-scoped authorization remain active.

## Database and upgrade

Always back up the database before upgrading. Apply schema changes with:

```bash
flask --app wsgi db heads
flask --app wsgi db upgrade
```

The OPERA foundation migration is 20261116_0019, chained after the inherited schema revision 20261017_0018. It creates OPERA-owned tables only. Do not run downgrade against production without a verified backup and an approved rollback plan.

## Project onboarding

1. Sign in as an organization administrator or project manager.
2. Open OPERA Commissioning and create a project.
3. Define systems and subsystems in the project structure.
4. Open Operations and assign project members their OPERA roles.
5. Create check sheets and add inspection items.
6. Issue the check sheet, record actual results and required witness releases.
7. Record separate contractor and client sign-offs. A signed-off sheet is immutable.
8. Raise and resolve punch items. Category A/B punch items block MC certification.
9. Create subsystem handover packages and progress snapshots.

## Task register\n\nThe task register is a project-scoped execution planning register. It records task number, activity type, title, discipline, project hierarchy, optional equipment and check-sheet links, progress stage/substage, assigned group, estimated/actual man-hours and planned/actual dates. Task status begins at Not Started; controlled execution transitions and dependency sequencing are subsequent increments.\n\n## OPERA roles

| Role | Primary responsibilities |
|---|---|
| Commissioning Manager | Project setup, membership, workflow administration and MC/RF management |
| Commissioning Engineer | Check-sheet preparation/execution and punch raising |
| QC Inspector | Independent check-sheet verification, Punch verification and witness attendance |
| Client Representative | Client-side check-sheet sign-off |
| Operations Lead | Operations acceptance of handover |
| Viewer | Read-only access granted by project membership |

Membership roles are project-scoped and do not alter the inherited account role.

## Security and operational notes

- All OPERA records are scoped to the signed-in user's company.
- State-changing browser forms use Flask-WTF CSRF protection.
- Role checks are enforced server-side; hiding a UI action is not treated as authorization.
- Check-sheet sign-off is an authenticated electronic acknowledgement, not a qualified cryptographic certificate or legally accredited digital signature.
- Audit records, signatures, Punch history and check-sheet revision records are append-only through ORM safeguards.
- Production deployment requires HTTPS, PostgreSQL, a strong secret, backups, monitored migrations and a persistent private evidence volume. Evidence files must be backed up and restored together with PostgreSQL.
- Never commit .env, passwords, TOTP secrets or recovery codes.

## CI and validation

GitHub Actions runs Ruff, Mypy, pytest, Bandit, pip-audit, PostgreSQL integration checks, migration checks, backup/restore verification and Docker image scanning. A green unit-test job alone is not production-readiness evidence; review every workflow job before release.

## Documentation

- [ICAPS Functional & Technical Analysis](docs/ICAPS_ANALYSIS.md)\n- [Functional Gap Analysis](docs/FUNCTIONAL_GAP_ANALYSIS.md)\n- [OPERA Architecture](docs/OPERA_ARCHITECTURE.md)
- [Workflow Guide](docs/WORKFLOW_GUIDE.md)
- [Document Templates](docs/DOCUMENT_TEMPLATES.md)
- [User Manual](docs/USER_MANUAL.md)
- [Administrator Guide](docs/ADMINISTRATOR_GUIDE.md)
- [Testing Report](docs/TESTING_REPORT.md)
- [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)\n- [OPERA Phase 1 architecture and migration notes](docs/OPERA_PHASE1.md)
- [Production launch checklist](docs/PRODUCTION_LAUNCH.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

## License

MIT — see LICENSE.
