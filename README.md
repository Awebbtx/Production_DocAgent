# IT Doc Builder

IT Doc Builder turns rough IT work notes into a structured HTML document and optionally exports it to DOCX using a defined presentation layer.

## What This Scaffold Includes

- FastAPI service entrypoint
- Browser-based GUI for copy/paste intake
- DeepSeek API client using an OpenAI-compatible chat completion request
- Prompted document generation pipeline
- Jinja-based HTML templating with a stylesheet hook
- DOCX export from generated HTML
- Document type catalog for common IT documentation events
- Example configuration and output folders

## Project Layout

```text
src/it_doc_builder/
  api.py
  cli.py
  config.py
  document_types.py
  models.py
  clients/deepseek.py
  services/pipeline.py
  services/docx_exporter.py
templates/
  index.html.j2
  report.html.j2
styles/
  report.css
output/
tests/
```

## Environment

Copy `.env.example` to `.env` and fill in the DeepSeek API key.

Required values:

- `DEEPSEEK_API_KEY`

Optional values:

- `DEEPSEEK_MODEL`
- `DEEPSEEK_BASE_URL`
- `OUTPUT_DIR`
- `STYLE_SHEET_PATH`
- `AUTH_DB_PATH`
- `AUTH_SECRET_KEY`
- `AUTH_SESSION_COOKIE_NAME`
- `AUTH_SESSION_TTL_SECONDS`
- `AUTH_COOKIE_SECURE`
- `BOOTSTRAP_ADMIN_USERNAME`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `BOOTSTRAP_ADMIN_CREDENTIALS_PATH`

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev]
```

## Run The API

```powershell
uvicorn it_doc_builder.api:app --reload
```

The service exposes:

- `GET /`
- `GET /app`
- `GET /settings` (admin UI)
- `GET /account` (user self-service UI)
- `GET /health`
- `GET /auth/me`
- `POST /auth/login`
- `POST /auth/verify-mfa`
- `POST /auth/logout`
- `POST /account/change-password`
- `POST /account/reset-mfa`
- `GET /account/usage`
- `GET /account/defaults`
- `POST /account/defaults`
- `POST /auth/password-reset/request`
- `POST /auth/password-reset/confirm`
- `POST /auth/invitations/accept`
- `GET /admin/users` (admin only)
- `POST /admin/users` (admin only)
- `POST /admin/users/invite` (admin only)
- `POST /admin/users/{username}/daily-limit` (admin only)
- `POST /admin/users/{username}/disable` (admin only)
- `POST /admin/users/{username}/reset-password` (admin only)
- `DELETE /admin/users/{username}` (admin only)
- `GET /admin/settings/deepseek` (admin only)
- `POST /admin/settings/deepseek` (admin only)
- `POST /admin/settings/deepseek/test` (admin only)
- `GET /admin/settings/email` (admin only)
- `POST /admin/settings/email` (admin only)
- `GET /logos`
- `GET /logos/{file_name}`
- `POST /admin/settings/logos` (admin only)
- `DELETE /admin/settings/logos/{file_name}` (admin only)
- `GET /document-types`
- `POST /documents/recommend-template`
- `POST /documents/build`

## Account System and MFA

The API now supports multiple local user accounts and enforces MFA before document operations.

### Bootstrap First Admin

Set these in `.env` before first startup:

- `BOOTSTRAP_ADMIN_USERNAME`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `AUTH_SECRET_KEY` (must be unique in production)

On startup, if the user table is empty, the bootstrap admin is created automatically.

If `BOOTSTRAP_ADMIN_USERNAME` and `BOOTSTRAP_ADMIN_PASSWORD` are not set, DocAgent now
auto-creates a first-deploy admin account with:

- username: `admin`
- password: generated one-time value

The generated credentials are written to `BOOTSTRAP_ADMIN_CREDENTIALS_PATH`
(default: `output/bootstrap-admin-credentials.txt`).

Read and rotate immediately after first login.

### Login Flow

1. `POST /auth/login` with username/password.
2. If the account already has MFA configured, response returns `mfa_required=true` and a `challenge_token`.
3. If MFA is not configured yet, response returns `mfa_enrollment_required=true`, a `challenge_token`, `mfa_secret`, and `otpauth_uri`.
4. User enters a valid TOTP code from authenticator app and calls `POST /auth/verify-mfa`.
5. Server issues an HTTP-only session cookie. Protected endpoints require this cookie and MFA verification.

When MFA enrollment is required, login response now also includes an inline QR image payload (`mfa_qr_svg_data_uri`) so users can scan directly in the browser.

### Admin User Management

- Use `GET /admin/users` to list accounts.
- Use `POST /admin/users` to create additional users with payload:

```json
{
  "username": "tech1",
  "password": "REPLACE_WITH_TEMP_PASSWORD",
  "is_admin": false
}
```

New users enroll MFA during their first successful username/password login.

Additional admin controls:

- `POST /admin/users/{username}/daily-limit` with payload `{"daily_doc_limit": 25}` (or `null` for unlimited)
- `POST /admin/users/{username}/disable` with payload `{"disabled": true}` (or `false` to re-enable)
- `POST /admin/users/{username}/reset-password` with payload `{"password": "REPLACE_WITH_TEMP_PASSWORD"}`
- `DELETE /admin/users/{username}` to permanently remove a user account
- Manage DeepSeek connection settings from the Settings UI or via:
: `GET/POST /admin/settings/deepseek` and `POST /admin/settings/deepseek/test`

Email and invite controls are available via:

- `GET/POST /admin/settings/email`
- `POST /admin/users/invite`
- `POST /auth/password-reset/request`
- `POST /auth/password-reset/confirm`

Password reset clears stored MFA so the user must re-enroll MFA at next login.

### Non-Admin Self Service

- Users can open `/account` to:
: change their password
: reset their own MFA (requires current password and forces fresh MFA enrollment on next login)
: view daily document generation usage/remaining quota

## Production Env Template

For your hosted deployment on `docagent.iknowapro.net`, use [deploy/.env.production.example](deploy/.env.production.example) as the baseline environment file.

## Project Notes

Detailed architecture notes, security checklist, deployment flow, and release notes are tracked in [PROJECT_NOTES.md](PROJECT_NOTES.md).

## GUI Workflow

Open the root URL in the browser after starting the service. The interface supports:

- pasting project details
- asking DeepSeek for the top 3 best template matches from messy notes
- choosing a document type such as Change Order or Network Update
- pasting raw technician notes
- entering work items one per line
- previewing the generated HTML and receiving the DOCX output path

## Intended Workflow

1. Paste copied project details and random technical notes into the GUI.
2. Call the recommendation endpoint so DeepSeek ranks the top 3 matching templates.
3. Let the user choose the final template.
4. Send the selected template details and stylesheet guidance to DeepSeek.
5. Return HTML that is inserted into the report shell and optionally exported to DOCX.

## Initial Template Coverage

The first pass includes 13 common IT documentation events:

- General Work Report
- Change Order
- Network Update
- Incident Report
- Maintenance Window Summary
- System Upgrade Report
- Workstation Deployment
- Access Change Record
- Security Finding
- Backup or Recovery Report
- Vendor Service Update
- Asset Lifecycle Record
- Project Handoff

## Example Request

```json
{
  "title": "Workstation Refresh - Finance",
  "author": "Alex Webb",
  "department": "IT Operations",
  "document_type": "workstation-deployment",
  "project_details": "Finance department workstation refresh covering 12 endpoints before month-end close.",
  "raw_notes": "Replaced two failing SSDs, rejoined one laptop to Entra ID, and updated BitLocker recovery records.",
  "work_items": [
    "Replaced failed SSDs in FIN-WS-14 and FIN-WS-22",
    "Validated user profile migration",
    "Updated asset records and BitLocker escrow"
  ],
  "generate_docx": true
}
```

## Production Deployment

### Systemd Service

Copy `deploy/it-docbuilder.service` to `/etc/systemd/system/` on the host and enable it:

```bash
cp deploy/it-docbuilder.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now it-docbuilder
```

The service listens on all interfaces at port `8000`.

### Caddy Reverse Proxy

A Caddyfile is provided at `deploy/Caddyfile`. It proxies `docagent.iknowapro.net` to the
IT Doc Builder service at `192.168.1.141:8000` with automatic HTTPS, GZIP compression, and
security response headers.

Copy the block into your existing `Caddyfile` (or place the file at `/etc/caddy/Caddyfile`) and
reload Caddy:

```bash
# Append to an existing Caddyfile
cat deploy/Caddyfile >> /etc/caddy/Caddyfile

# Validate and reload
caddy validate --config /etc/caddy/Caddyfile
systemctl reload caddy
```

> If Caddy runs on the same host as the application, replace `192.168.1.141:8000` with
> `localhost:8000` in the Caddyfile.

## Current Tradeoffs

- The initial build assumes DeepSeek returns HTML body content, not a full page.
- DOCX export is based on HTML conversion, so advanced CSS support is limited.
- Template recommendation is LLM-driven with a local heuristic fallback if the API call fails.
- The template catalog currently changes prompt guidance and required sections, but all outputs still share one common visual style.
- For stricter house style control, the next step would be a DOCX template-driven exporter.