# OPERA Validation Record

This file is maintained with the productization pull request. The latest GitHub Actions result on the final head is the authority for automated validation.

## Required checks
- Ruff static analysis
- Mypy type analysis
- Shell script syntax validation
- Full pytest suite and coverage threshold
- Bandit security scan
- pip-audit dependency audit
- PostgreSQL migration/integration
- Docker production image build
- Trivy image scan
- Backup/restore revision validation

## Acceptance constraints
- No production database or external customer data is included in the repository.
- No default demo-user passwords are distributed.
- OPERA demo seed is opt-in, creates no user accounts and requires an existing tenant user.
- Production deploy helper does not seed demo data.
- Check-sheet signatures are authenticated audit acknowledgements, not qualified PKI signatures.
