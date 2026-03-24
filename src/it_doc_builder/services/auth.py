from __future__ import annotations

import sqlite3
from base64 import b64encode
from dataclasses import dataclass
from datetime import date, datetime, timezone
from io import BytesIO
from secrets import token_urlsafe

import pyotp
import qrcode
import qrcode.image.svg
from itsdangerous import BadSignature, BadTimeSignature, URLSafeTimedSerializer
from passlib.context import CryptContext

from it_doc_builder.config import Settings
from it_doc_builder.models import UserAccount


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass(slots=True)
class SessionIdentity:
    username: str
    is_admin: bool
    mfa_verified: bool


class AuthError(Exception):
    pass


class AuthenticationError(AuthError):
    pass


class AuthorizationError(AuthError):
    pass


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._serializer = URLSafeTimedSerializer(settings.auth_secret_key)
        self._ensure_schema()
        self._ensure_bootstrap_admin()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._settings.auth_db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    email TEXT NOT NULL DEFAULT '',
                    password_hash TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    mfa_secret TEXT,
                    disabled INTEGER NOT NULL DEFAULT 0,
                    daily_doc_limit INTEGER,
                    default_author TEXT NOT NULL DEFAULT '',
                    default_company_name TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(users)").fetchall()
            }
            if "email" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''")
            if "daily_doc_limit" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN daily_doc_limit INTEGER")
            if "default_author" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN default_author TEXT NOT NULL DEFAULT ''")
            if "default_company_name" not in columns:
                connection.execute("ALTER TABLE users ADD COLUMN default_company_name TEXT NOT NULL DEFAULT ''")

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS usage_daily (
                    username TEXT NOT NULL,
                    usage_date TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (username, usage_date)
                )
                """
            )
            connection.commit()

    def _ensure_bootstrap_admin(self) -> None:
        with self._connect() as connection:
            count = connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()["count"]
            if count:
                return

        bootstrap_username = (self._settings.bootstrap_admin_username or "admin").strip().lower()
        bootstrap_password = self._settings.bootstrap_admin_password.strip()
        generated = False
        if not bootstrap_password:
            # One-time first-deploy fallback password when env is not preseeded.
            bootstrap_password = token_urlsafe(18)
            generated = True

        self.create_user(
            username=bootstrap_username,
            password=bootstrap_password,
            is_admin=True,
            daily_doc_limit=None,
        )
        if generated:
            self._write_bootstrap_credentials_file(bootstrap_username, bootstrap_password)

    def _write_bootstrap_credentials_file(self, username: str, password: str) -> None:
        credentials_path = self._settings.bootstrap_admin_credentials_path
        content = (
            "DocAgent first-deploy bootstrap admin credentials\n"
            "Rotate after first login.\n\n"
            f"username={username}\n"
            f"password={password}\n"
        )
        credentials_path.write_text(content, encoding="utf-8")

    def create_user(
        self,
        username: str,
        password: str,
        email: str = "",
        is_admin: bool = False,
        daily_doc_limit: int | None = 25,
    ) -> UserAccount:
        clean_username = username.strip().lower()
        clean_email = email.strip().lower()
        if len(clean_username) < 3:
            raise AuthError("Username must be at least 3 characters.")
        if len(password) < 10:
            raise AuthError("Password must be at least 10 characters.")
        if daily_doc_limit is not None and daily_doc_limit < 1:
            raise AuthError("Daily document limit must be at least 1 when configured.")

        now = datetime.now(timezone.utc).isoformat()
        password_hash = pwd_context.hash(password)

        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO users (username, email, password_hash, is_admin, mfa_secret, disabled, daily_doc_limit, created_at, updated_at)
                    VALUES (?, ?, ?, ?, NULL, 0, ?, ?, ?)
                    """,
                    (clean_username, clean_email, password_hash, int(is_admin), daily_doc_limit, now, now),
                )
                connection.commit()
        except sqlite3.IntegrityError as exc:
            raise AuthError("User already exists.") from exc

        return self.get_user(clean_username)

    def get_user(self, username: str) -> UserAccount:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT username, email, is_admin, mfa_secret, disabled, daily_doc_limit, created_at
                FROM users
                WHERE username = ?
                """,
                (username.strip().lower(),),
            ).fetchone()

        if not row:
            raise AuthenticationError("Invalid credentials.")

        return UserAccount(
            username=row["username"],
            email=row["email"] or "",
            is_admin=bool(row["is_admin"]),
            mfa_enabled=bool(row["mfa_secret"]),
            disabled=bool(row["disabled"]),
            daily_doc_limit=row["daily_doc_limit"],
            created_at=row["created_at"],
        )

    def list_users(self) -> list[UserAccount]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT username, email, is_admin, mfa_secret, disabled, daily_doc_limit, created_at
                FROM users
                ORDER BY username ASC
                """
            ).fetchall()

        return [
            UserAccount(
                username=row["username"],
                email=row["email"] or "",
                is_admin=bool(row["is_admin"]),
                mfa_enabled=bool(row["mfa_secret"]),
                disabled=bool(row["disabled"]),
                daily_doc_limit=row["daily_doc_limit"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def set_user_daily_limit(self, username: str, daily_doc_limit: int | None) -> UserAccount:
        clean_username = username.strip().lower()
        if daily_doc_limit is not None and daily_doc_limit < 1:
            raise AuthError("Daily document limit must be at least 1 when configured.")

        with self._connect() as connection:
            row = connection.execute(
                "SELECT username FROM users WHERE username = ?",
                (clean_username,),
            ).fetchone()
            if not row:
                raise AuthError("User not found.")
            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                "UPDATE users SET daily_doc_limit = ?, updated_at = ? WHERE username = ?",
                (daily_doc_limit, now, clean_username),
            )
            connection.commit()

        return self.get_user(clean_username)

    def get_daily_usage(self, username: str, usage_date: date | None = None) -> tuple[int, int | None]:
        clean_username = username.strip().lower()
        day = (usage_date or date.today()).isoformat()
        with self._connect() as connection:
            user_row = connection.execute(
                "SELECT daily_doc_limit FROM users WHERE username = ?",
                (clean_username,),
            ).fetchone()
            if not user_row:
                raise AuthError("User not found.")

            usage_row = connection.execute(
                "SELECT count FROM usage_daily WHERE username = ? AND usage_date = ?",
                (clean_username, day),
            ).fetchone()

        used = int(usage_row["count"]) if usage_row else 0
        return used, user_row["daily_doc_limit"]

    def consume_document_generation(self, username: str) -> None:
        clean_username = username.strip().lower()
        day = date.today().isoformat()
        with self._connect() as connection:
            user_row = connection.execute(
                "SELECT daily_doc_limit FROM users WHERE username = ?",
                (clean_username,),
            ).fetchone()
            if not user_row:
                raise AuthorizationError("User account not found.")
            limit = user_row["daily_doc_limit"]

            usage_row = connection.execute(
                "SELECT count FROM usage_daily WHERE username = ? AND usage_date = ?",
                (clean_username, day),
            ).fetchone()
            used = int(usage_row["count"]) if usage_row else 0

            if limit is not None and used >= int(limit):
                raise AuthorizationError("Daily document generation limit reached.")

            if usage_row:
                connection.execute(
                    "UPDATE usage_daily SET count = ? WHERE username = ? AND usage_date = ?",
                    (used + 1, clean_username, day),
                )
            else:
                connection.execute(
                    "INSERT INTO usage_daily (username, usage_date, count) VALUES (?, ?, 1)",
                    (clean_username, day),
                )
            connection.commit()

    def set_user_disabled(self, username: str, disabled: bool, acting_username: str) -> UserAccount:
        clean_username = username.strip().lower()
        acting = acting_username.strip().lower()
        if clean_username == acting and disabled:
            raise AuthError("You cannot disable your own account.")

        with self._connect() as connection:
            row = connection.execute(
                "SELECT username FROM users WHERE username = ?",
                (clean_username,),
            ).fetchone()
            if not row:
                raise AuthError("User not found.")

            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                "UPDATE users SET disabled = ?, updated_at = ? WHERE username = ?",
                (int(disabled), now, clean_username),
            )
            connection.commit()

        return self.get_user(clean_username)

    def reset_user_password(self, username: str, password: str, reset_mfa: bool = True) -> UserAccount:
        clean_username = username.strip().lower()
        if len(password) < 10:
            raise AuthError("Password must be at least 10 characters.")

        password_hash = pwd_context.hash(password)
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT username FROM users WHERE username = ?",
                (clean_username,),
            ).fetchone()
            if not row:
                raise AuthError("User not found.")

            if reset_mfa:
                connection.execute(
                    """
                    UPDATE users
                    SET password_hash = ?, mfa_secret = NULL, updated_at = ?
                    WHERE username = ?
                    """,
                    (password_hash, now, clean_username),
                )
            else:
                connection.execute(
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE username = ?",
                    (password_hash, now, clean_username),
                )
            connection.commit()

        return self.get_user(clean_username)

    def change_own_password(self, username: str, current_password: str, new_password: str) -> None:
        clean_username = username.strip().lower()
        if len(new_password) < 10:
            raise AuthError("New password must be at least 10 characters.")

        with self._connect() as connection:
            row = connection.execute(
                "SELECT password_hash FROM users WHERE username = ?",
                (clean_username,),
            ).fetchone()
            if not row or not pwd_context.verify(current_password, row["password_hash"]):
                raise AuthenticationError("Current password is incorrect.")

            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE username = ?",
                (pwd_context.hash(new_password), now, clean_username),
            )
            connection.commit()

    def reset_own_mfa(self, username: str, current_password: str) -> None:
        clean_username = username.strip().lower()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT password_hash FROM users WHERE username = ?",
                (clean_username,),
            ).fetchone()
            if not row or not pwd_context.verify(current_password, row["password_hash"]):
                raise AuthenticationError("Current password is incorrect.")

            now = datetime.now(timezone.utc).isoformat()
            connection.execute(
                "UPDATE users SET mfa_secret = NULL, updated_at = ? WHERE username = ?",
                (now, clean_username),
            )
            connection.commit()

    def create_password_reset_token_for_email(self, email: str) -> tuple[str, str] | None:
        clean_email = email.strip().lower()
        if not clean_email:
            return None
        with self._connect() as connection:
            row = connection.execute(
                "SELECT username, email FROM users WHERE lower(email) = ?",
                (clean_email,),
            ).fetchone()
        if not row:
            return None
        token = self._serializer.dumps(
            {"action": "password-reset", "username": row["username"]},
            salt="account-email-action",
        )
        return (token, row["email"])

    def reset_password_with_token(self, token: str, new_password: str) -> None:
        if len(new_password) < 10:
            raise AuthError("Password must be at least 10 characters.")
        payload = self._load_payload(token, salt="account-email-action", max_age=3600)
        if payload.get("action") != "password-reset":
            raise AuthError("Invalid reset token.")
        username = str(payload.get("username", "")).strip().lower()
        if not username:
            raise AuthError("Invalid reset token.")
        self.reset_user_password(username, new_password, reset_mfa=True)

    def create_invitation_token(self, email: str, is_admin: bool, daily_doc_limit: int | None) -> str:
        clean_email = email.strip().lower()
        if not clean_email:
            raise AuthError("Email is required.")
        payload = {
            "action": "invite",
            "email": clean_email,
            "is_admin": bool(is_admin),
            "daily_doc_limit": daily_doc_limit,
        }
        return self._serializer.dumps(payload, salt="account-email-action")

    def accept_invitation(self, token: str, username: str, password: str) -> UserAccount:
        payload = self._load_payload(token, salt="account-email-action", max_age=604800)
        if payload.get("action") != "invite":
            raise AuthError("Invalid invitation token.")
        email = str(payload.get("email", "")).strip().lower()
        is_admin = bool(payload.get("is_admin", False))
        daily_doc_limit = payload.get("daily_doc_limit", 25)
        return self.create_user(
            username=username,
            password=password,
            email=email,
            is_admin=is_admin,
            daily_doc_limit=daily_doc_limit,
        )

    def get_account_defaults(self, username: str) -> tuple[str, str]:
        clean_username = username.strip().lower()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT default_author, default_company_name FROM users WHERE username = ?",
                (clean_username,),
            ).fetchone()
        if not row:
            raise AuthError("User not found.")
        return (row["default_author"] or "", row["default_company_name"] or "")

    def update_account_defaults(self, username: str, author: str, company_name: str) -> tuple[str, str]:
        clean_username = username.strip().lower()
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            row = connection.execute("SELECT username FROM users WHERE username = ?", (clean_username,)).fetchone()
            if not row:
                raise AuthError("User not found.")
            connection.execute(
                """
                UPDATE users
                SET default_author = ?, default_company_name = ?, updated_at = ?
                WHERE username = ?
                """,
                ((author or "").strip(), (company_name or "").strip(), now, clean_username),
            )
            connection.commit()
        return self.get_account_defaults(clean_username)

    def delete_user(self, username: str, acting_username: str) -> None:
        clean_username = username.strip().lower()
        acting = acting_username.strip().lower()
        if clean_username == acting:
            raise AuthError("You cannot delete your own account.")

        with self._connect() as connection:
            row = connection.execute(
                "SELECT username FROM users WHERE username = ?",
                (clean_username,),
            ).fetchone()
            if not row:
                raise AuthError("User not found.")

            connection.execute("DELETE FROM users WHERE username = ?", (clean_username,))
            connection.execute("DELETE FROM usage_daily WHERE username = ?", (clean_username,))
            connection.commit()

    def begin_login(self, username: str, password: str) -> dict[str, object]:
        clean_username = username.strip().lower()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT username, password_hash, is_admin, mfa_secret, disabled
                FROM users
                WHERE username = ?
                """,
                (clean_username,),
            ).fetchone()

        if not row or not pwd_context.verify(password, row["password_hash"]):
            raise AuthenticationError("Invalid credentials.")
        if row["disabled"]:
            raise AuthorizationError("Account is disabled.")

        if row["mfa_secret"]:
            challenge_token = self._serializer.dumps(
                {"username": row["username"], "action": "verify"}, salt="mfa-challenge"
            )
            return {
                "mfa_required": True,
                "mfa_enrollment_required": False,
                "challenge_token": challenge_token,
            }

        mfa_secret = pyotp.random_base32()
        challenge_token = self._serializer.dumps(
            {"username": row["username"], "action": "enroll", "mfa_secret": mfa_secret},
            salt="mfa-challenge",
        )
        otpauth_uri = pyotp.TOTP(mfa_secret).provisioning_uri(
            name=row["username"],
            issuer_name="DocAgent",
        )
        mfa_qr_svg_data_uri = self._build_qr_svg_data_uri(otpauth_uri)
        return {
            "mfa_required": False,
            "mfa_enrollment_required": True,
            "challenge_token": challenge_token,
            "otpauth_uri": otpauth_uri,
            "mfa_secret": mfa_secret,
            "mfa_qr_svg_data_uri": mfa_qr_svg_data_uri,
        }

    def verify_mfa_and_create_session(self, challenge_token: str, code: str) -> str:
        payload = self._load_payload(challenge_token, salt="mfa-challenge", max_age=600)
        username = str(payload.get("username", "")).strip().lower()
        action = str(payload.get("action", "")).strip().lower()

        if action not in {"verify", "enroll"}:
            raise AuthenticationError("Invalid MFA challenge.")

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT username, is_admin, mfa_secret, disabled
                FROM users
                WHERE username = ?
                """,
                (username,),
            ).fetchone()

            if not row or row["disabled"]:
                raise AuthenticationError("Account is not available.")

            if action == "verify":
                mfa_secret = row["mfa_secret"]
                if not mfa_secret:
                    raise AuthenticationError("MFA enrollment is required.")
            else:
                mfa_secret = str(payload.get("mfa_secret", "")).strip()
                if not mfa_secret:
                    raise AuthenticationError("MFA setup token is invalid.")

            totp = pyotp.TOTP(mfa_secret)
            if not totp.verify(code.strip(), valid_window=1):
                raise AuthenticationError("Invalid MFA code.")

            if action == "enroll":
                now = datetime.now(timezone.utc).isoformat()
                connection.execute(
                    """
                    UPDATE users
                    SET mfa_secret = ?, updated_at = ?
                    WHERE username = ?
                    """,
                    (mfa_secret, now, username),
                )
                connection.commit()

        return self._serializer.dumps(
            {"username": username, "is_admin": bool(row["is_admin"]), "mfa_verified": True},
            salt="session",
        )

    def decode_session(self, token: str) -> SessionIdentity:
        payload = self._load_payload(token, salt="session", max_age=self._settings.auth_session_ttl_seconds)
        return SessionIdentity(
            username=str(payload.get("username", "")).strip().lower(),
            is_admin=bool(payload.get("is_admin", False)),
            mfa_verified=bool(payload.get("mfa_verified", False)),
        )

    def _load_payload(self, token: str, salt: str, max_age: int) -> dict[str, object]:
        try:
            return self._serializer.loads(token, salt=salt, max_age=max_age)
        except (BadSignature, BadTimeSignature) as exc:
            raise AuthenticationError("Invalid or expired token.") from exc

    @staticmethod
    def _build_qr_svg_data_uri(value: str) -> str:
        qr = qrcode.QRCode(border=2, box_size=8)
        qr.add_data(value)
        qr.make(fit=True)
        image = qr.make_image(image_factory=qrcode.image.svg.SvgImage)
        with BytesIO() as buffer:
            image.save(buffer)
            encoded = b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"
