from __future__ import annotations

import smtplib
from email.message import EmailMessage

from it_doc_builder.config import Settings
from it_doc_builder.services.auth import AuthError


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def is_configured(self) -> bool:
        return bool(
            self._settings.smtp_host.strip()
            and self._settings.smtp_from_email.strip()
            and self._settings.app_base_url.strip()
        )

    def send(self, to_email: str, subject: str, body: str) -> None:
        if not self.is_configured():
            raise AuthError("Email is not configured. Ask admin to configure SMTP settings.")

        msg = EmailMessage()
        msg["From"] = self._settings.smtp_from_email.strip()
        msg["To"] = to_email.strip()
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(self._settings.smtp_host.strip(), int(self._settings.smtp_port), timeout=20) as client:
            if self._settings.smtp_use_tls:
                client.starttls()
            if self._settings.smtp_username.strip():
                client.login(self._settings.smtp_username.strip(), self._settings.smtp_password)
            client.send_message(msg)
