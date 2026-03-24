# Production DocAgent Project Notes

## Overview
Production DocAgent is a FastAPI-based document builder that converts technician notes into structured HTML and optional DOCX output.

Core capabilities:
- Multi-user authentication with MFA
- Role-based admin/user controls
- Per-user builder defaults
- Template recommendation and document generation
- Logo library (upload, list, delete) with hosted URLs
- Document history and retention controls
- Email-based password reset and user invitations

## Architecture
- API layer: src/it_doc_builder/api.py
- Configuration: src/it_doc_builder/config.py
- Auth and account services: src/it_doc_builder/services/auth.py
- Runtime admin settings: src/it_doc_builder/services/runtime_settings.py
- Document pipeline: src/it_doc_builder/services/pipeline.py
- Static templates: templates/
- Stylesheets: styles/

## Security Notes
- No private credentials should be committed.
- Local .env is intentionally ignored by git.
- Environment templates include placeholders only.
- Secrets expected from environment variables:
  - DEEPSEEK_API_KEY
  - AUTH_SECRET_KEY
  - SMTP_PASSWORD
  - BOOTSTRAP_ADMIN_PASSWORD (if used)
- Admin account recovery options:
  - Admin password reset endpoint
  - Email-based reset with expiring token
- Delete-user guardrail:
  - Admins cannot delete their own active account via API

## Deployment Notes
Primary deployment model:
- Host: Proxmox root access
- Container: VMID 103
- App path in container: /opt/it-docbuilder
- Service: systemctl restart it-docbuilder

Typical update flow:
1. Package changed files.
2. Copy bundle to Proxmox host.
3. Push bundle into container 103.
4. Extract under /opt/it-docbuilder.
5. Restart it-docbuilder service.
6. Verify /health returns 200.

## Operational Endpoints
Authentication and account:
- POST /auth/login
- POST /auth/verify-mfa
- POST /auth/logout
- POST /auth/password-reset/request
- POST /auth/password-reset/confirm
- POST /auth/invitations/accept
- GET /account/defaults
- POST /account/defaults
- POST /account/change-password
- POST /account/reset-mfa

Admin management:
- GET /admin/users
- POST /admin/users
- POST /admin/users/invite
- POST /admin/users/{username}/daily-limit
- POST /admin/users/{username}/disable
- POST /admin/users/{username}/reset-password
- DELETE /admin/users/{username}
- GET /admin/settings/deepseek
- POST /admin/settings/deepseek
- GET /admin/settings/email
- POST /admin/settings/email

Logo library:
- GET /logos
- GET /logos/{file_name}
- POST /admin/settings/logos
- DELETE /admin/settings/logos/{file_name}

## Release Notes (Current)
Latest project changes include:
- Added user delete action in admin settings table
- Added delete-user backend endpoint and service method
- Added guard against admin self-deletion
- Added email settings and invitation flows
- Added password reset request and confirm flows
- Added account defaults for author and company per user
- Added logo upload/list/delete management and dropdown selection
- Fixed logo rendering by converting relative logo URLs to absolute URLs for output

## Repository Hygiene
This repository is prepared for production publishing:
- Non-production files removed
- Temporary deployment bundles excluded
- Test artifacts excluded
- Build metadata excluded
- Working branch main tracks GitHub origin/main
