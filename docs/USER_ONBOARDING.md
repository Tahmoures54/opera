# OPERA User Onboarding

This guide describes the onboarding steps that exist in the current code. Each
step names the route it uses, so it can be checked against
`blueprints/auth.py` and `blueprints/commissioning/`.

## 1. Register your organization

- Open `/auth/register`.
- Enter the company name, company email, company phone, full name and a password.
- Complete the captcha question and accept the terms.
- Scan the TOTP (two-factor) QR code in an authenticator app, then confirm the
  six-digit code. Registration is complete after this confirmation.

The trial period starts when the TOTP code is confirmed. In the code, it lasts
45 days (`blueprints/auth.py`, `trial_ends_at = trial_started + timedelta(days=45)`).

## 2. Sign in

- Open `/auth/login` and enter your credentials and TOTP code.
- Password reset is available at `/auth/reset_password_request`. Lost two-factor
  access is handled at `/auth/reset_totp`.

## 3. Create a project

- Open `/commissioning/projects/new`.
- Enter the project code, name, client and contractor.
- Each project is scoped to your organization. Other organizations cannot see it.

## 4. Build the project structure

- Add systems at `/commissioning/projects/<project_id>/systems/new`.
- Add subsystems under each system.
- Systems and subsystems carry weight percentages. Progress is calculated from
  these weights; no progress value is invented.

## 5. Invite project members

- Add members to the project from the project page (`POST /commissioning/projects/<project_id>/members`).
- Each member receives a project role (for example Commissioning Manager, QC
  Inspector, Client Representative, Viewer). Permissions are enforced on the server.
- Deactivate a member with `POST /commissioning/projects/<project_id>/members/<membership_id>/deactivate`.

## 6. Configure readiness rules

- Open `/commissioning/projects/<project_id>/readiness-policy`.
- Set which Punch categories block MC, RFC and RFSU, which Hold points block each
  gate, and which Check Sheet types are required. Changes are audited.
- Invalid settings are rejected, and readiness fails closed until they are corrected.

## 7. Import engineering data (optional)

- Open `/commissioning/projects/<project_id>/engineering-data/import`.
- Use a dry run first. The dry run reports errors per row without saving anything.
- Formula cells and rows outside the project scope are rejected.

## 8. Start execution

- Create check sheets, record results, and route them for QC verification and sign-off.
- Raise Punch items and assign them. Close and verify them with a second user.
- Schedule Witness and Hold points, record attendance, and release them with a note.

## Demonstration project (not for production)

A fictional demonstration project can be created with
`scripts/seed_commissioning_demo.py`. The script:

- runs only when `SEED_COMMISSIONING_DEMO=1` is set;
- requires an existing user in the target organization, and creates no users;
- refuses to run if a project with the same code already exists.

Do not run it against a production database. Use a separate organization for
demonstrations.

## Limits of this guide

- Email delivery for account recovery depends on SMTP configuration. If it is not
  configured, the application does not claim that a message was sent.
- Production onboarding has not been verified end to end in a deployed
  environment. See `docs/PRODUCTION_LAUNCH.md` for the acceptance scenario.
