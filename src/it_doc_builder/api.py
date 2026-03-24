import asyncio
import re
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from it_doc_builder.clients.deepseek import DeepSeekClient
from it_doc_builder.config import get_settings
from it_doc_builder.document_types import list_document_types
from it_doc_builder.models import (
    AccountDefaultsResponse,
    AccountUsageResponse,
    AnalyzedNotesResponse,
    AnalyzeNotesRequest,
    AuthSessionResponse,
    ChangeOwnPasswordRequest,
    CreateUserRequest,
    DeepSeekConnectionTestResponse,
    DeepSeekSettingsResponse,
    DocumentBuildRequest,
    DocumentBuildResponse,
    DocumentDefaultsResponse,
    DocumentHistoryItem,
    EmailSettingsResponse,
    InvitationAcceptRequest,
    InviteUserRequest,
    LoginRequest,
    LoginResponse,
    LogoLibraryResponse,
    LogoOption,
    ResetOwnMfaRequest,
    ResetUserPasswordRequest,
    RestyleHtmlRequest,
    RestyleHtmlResponse,
    SaveDocumentRequest,
    SaveDocumentResponse,
    SetUserDailyLimitRequest,
    SetUserDisabledRequest,
    UpdateDeepSeekSettingsRequest,
    UpdateEmailSettingsRequest,
    UpdateDocumentDefaultsRequest,
    UpdateAccountDefaultsRequest,
    UserAccount,
    VerifyMfaRequest,
    TemplateRecommendationRequest,
    TemplateRecommendationResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
)
from it_doc_builder.services.auth import (
    AuthError,
    AuthService,
    AuthenticationError,
    AuthorizationError,
    SessionIdentity,
)
from it_doc_builder.services.docx_exporter import export_html_to_docx
from it_doc_builder.services.document_store import DocumentStore
from it_doc_builder.services.email_service import EmailService
from it_doc_builder.services.logo_store import LogoStore
from it_doc_builder.services.pipeline import DocumentPipeline
from it_doc_builder.services.runtime_settings import (
    get_email_settings,
    get_deepseek_settings,
    get_document_defaults,
    update_email_settings,
    update_deepseek_settings,
    update_document_defaults,
)

app = FastAPI(title="DocAgent", version="0.1.0")
templates = Jinja2Templates(directory="templates")


def _auth_service() -> AuthService:
    return AuthService(get_settings())


def _slugify_filename(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value or "document").strip("-").lower()
    return slug[:80] or "document"


def _absolute_logo_url(value: str, request: Request) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    if parsed.scheme in {"http", "https"}:
        return raw
    if raw.startswith("/"):
        return str(request.base_url).rstrip("/") + raw
    return raw


def _absolutize_logo_urls_in_html(html: str, request: Request) -> str:
    base = str(request.base_url).rstrip("/")
    return re.sub(r'src="(/logos/[^"]+)"', lambda m: f'src="{base}{m.group(1)}"', html)


@app.on_event("startup")
async def startup_event() -> None:
    _auth_service()
    asyncio.create_task(_purge_loop())


async def _purge_loop() -> None:
    while True:
        try:
            DocumentStore(get_settings()).purge_expired()
        except Exception:
            pass
        await asyncio.sleep(3600)


def _session_identity_or_none(request: Request) -> SessionIdentity | None:
    settings = get_settings()
    token = request.cookies.get(settings.auth_session_cookie_name)
    if not token:
        return None
    try:
        return _auth_service().decode_session(token)
    except AuthenticationError:
        return None


def require_mfa_session(request: Request) -> SessionIdentity:
    identity = _session_identity_or_none(request)
    if not identity or not identity.mfa_verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return identity


def require_admin_session(identity: SessionIdentity = Depends(require_mfa_session)) -> SessionIdentity:
    if not identity.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return identity


@app.get("/", response_class=HTMLResponse)
async def login_landing(request: Request) -> HTMLResponse:
    identity = _session_identity_or_none(request)
    if identity and identity.mfa_verified:
        return RedirectResponse(url="/app", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request,
        "login.html.j2",
        {
            "request": request,
        },
    )


@app.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str = "") -> HTMLResponse:
    return templates.TemplateResponse(request, "reset_password.html.j2", {"request": request, "token": token})


@app.get("/accept-invite", response_class=HTMLResponse)
async def accept_invite_page(request: Request, token: str = "") -> HTMLResponse:
    return templates.TemplateResponse(request, "accept_invite.html.j2", {"request": request, "token": token})


@app.get("/history", response_class=HTMLResponse)
async def history_page(request: Request) -> HTMLResponse:
    identity = _session_identity_or_none(request)
    if not identity or not identity.mfa_verified:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request,
        "history.html.j2",
        {"request": request, "username": identity.username, "is_admin": identity.is_admin},
    )


@app.get("/app", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    identity = _session_identity_or_none(request)
    if not identity or not identity.mfa_verified:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request,
        "index.html.j2",
        {
            "request": request,
            "document_types": list_document_types(),
            "is_admin": identity.is_admin,
        },
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request) -> HTMLResponse:
    identity = _session_identity_or_none(request)
    if not identity or not identity.mfa_verified:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    if not identity.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return templates.TemplateResponse(
        request,
        "settings.html.j2",
        {
            "request": request,
            "username": identity.username,
        },
    )


@app.get("/account", response_class=HTMLResponse)
async def account_page(request: Request) -> HTMLResponse:
    identity = _session_identity_or_none(request)
    if not identity or not identity.mfa_verified:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request,
        "account.html.j2",
        {
            "request": request,
            "username": identity.username,
            "is_admin": identity.is_admin,
        },
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/logos/{file_name}")
async def get_logo_file(file_name: str) -> FileResponse:
    path = LogoStore(get_settings()).resolve_logo_path(file_name)
    if not path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Logo not found.")
    media_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return FileResponse(str(path), media_type=media_type, filename=path.name)


@app.get("/logos", response_model=LogoLibraryResponse)
async def list_logos(_: SessionIdentity = Depends(require_mfa_session)) -> JSONResponse:
    store = LogoStore(get_settings())
    items = [LogoOption(**row) for row in store.list_logos()]
    payload = LogoLibraryResponse(
        logos=items,
        max_items=store.max_items,
        max_file_size_bytes=store.max_file_size_bytes,
    )
    return JSONResponse(content=payload.model_dump())


@app.post("/admin/settings/logos", response_model=LogoLibraryResponse)
async def upload_logo(
    file: UploadFile = File(...),
    _: SessionIdentity = Depends(require_admin_session),
) -> JSONResponse:
    data = await file.read()
    store = LogoStore(get_settings())
    try:
        store.save_logo(file.filename or "logo", data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    items = [LogoOption(**row) for row in store.list_logos()]
    payload = LogoLibraryResponse(
        logos=items,
        max_items=store.max_items,
        max_file_size_bytes=store.max_file_size_bytes,
    )
    return JSONResponse(content=payload.model_dump())


@app.delete("/admin/settings/logos/{file_name}", response_model=LogoLibraryResponse)
async def delete_logo(file_name: str, _: SessionIdentity = Depends(require_admin_session)) -> JSONResponse:
    store = LogoStore(get_settings())
    if not store.delete_logo(file_name):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Logo not found.")

    defaults = get_document_defaults()
    if defaults.company_logo_url.endswith(f"/{file_name}"):
        update_document_defaults(
            UpdateDocumentDefaultsRequest(
                author=defaults.author,
                company_name=defaults.company_name,
                company_logo_url="",
            )
        )

    items = [LogoOption(**row) for row in store.list_logos()]
    payload = LogoLibraryResponse(
        logos=items,
        max_items=store.max_items,
        max_file_size_bytes=store.max_file_size_bytes,
    )
    return JSONResponse(content=payload.model_dump())


@app.get("/auth/me", response_model=AuthSessionResponse)
async def auth_me(request: Request) -> JSONResponse:
    identity = _session_identity_or_none(request)
    if not identity:
        return JSONResponse(content=AuthSessionResponse(authenticated=False).model_dump())
    return JSONResponse(
        content=AuthSessionResponse(
            authenticated=True,
            username=identity.username,
            is_admin=identity.is_admin,
            mfa_verified=identity.mfa_verified,
        ).model_dump()
    )


@app.post("/auth/login", response_model=LoginResponse)
async def auth_login(request: LoginRequest) -> JSONResponse:
    try:
        result = _auth_service().begin_login(request.username, request.password)
        return JSONResponse(content=LoginResponse(success=True, **result).model_dump())
    except (AuthenticationError, AuthorizationError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@app.post("/auth/verify-mfa", response_model=AuthSessionResponse)
async def auth_verify_mfa(request: VerifyMfaRequest, response: Response) -> JSONResponse:
    try:
        session_token = _auth_service().verify_mfa_and_create_session(request.challenge_token, request.code)
        identity = _auth_service().decode_session(session_token)
    except (AuthenticationError, AuthorizationError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    settings = get_settings()
    payload = AuthSessionResponse(
        authenticated=True,
        username=identity.username,
        is_admin=identity.is_admin,
        mfa_verified=True,
    )
    json_response = JSONResponse(content=payload.model_dump())
    json_response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=session_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.auth_session_ttl_seconds,
    )
    return json_response


@app.post("/auth/logout")
async def auth_logout() -> JSONResponse:
    settings = get_settings()
    response = JSONResponse(content={"success": True})
    response.delete_cookie(settings.auth_session_cookie_name)
    return response


@app.post("/auth/password-reset/request")
async def request_password_reset(request: PasswordResetRequest) -> JSONResponse:
    try:
        token_payload = _auth_service().create_password_reset_token_for_email(request.email)
        if token_payload:
            token, target_email = token_payload
            settings = get_settings()
            link = f"{settings.app_base_url.rstrip('/')}/reset-password?token={token}"
            EmailService(settings).send(
                target_email,
                "DocAgent password reset",
                f"Use this link to reset your DocAgent password (valid 1 hour):\n\n{link}\n",
            )
        # Always return success to avoid account enumeration.
        return JSONResponse(content={"success": True})
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post("/auth/password-reset/confirm")
async def confirm_password_reset(request: PasswordResetConfirmRequest) -> JSONResponse:
    try:
        _auth_service().reset_password_with_token(request.token, request.new_password)
        return JSONResponse(content={"success": True})
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post("/auth/invitations/accept")
async def accept_invitation(request: InvitationAcceptRequest) -> JSONResponse:
    try:
        _auth_service().accept_invitation(request.token, request.username, request.password)
        return JSONResponse(content={"success": True})
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post("/account/change-password")
async def account_change_password(
    request: ChangeOwnPasswordRequest,
    identity: SessionIdentity = Depends(require_mfa_session),
) -> JSONResponse:
    try:
        _auth_service().change_own_password(identity.username, request.current_password, request.new_password)
        return JSONResponse(content={"success": True})
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post("/account/reset-mfa")
async def account_reset_mfa(
    request: ResetOwnMfaRequest,
    identity: SessionIdentity = Depends(require_mfa_session),
) -> JSONResponse:
    try:
        _auth_service().reset_own_mfa(identity.username, request.current_password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    settings = get_settings()
    response = JSONResponse(content={"success": True})
    response.delete_cookie(settings.auth_session_cookie_name)
    return response


@app.get("/account/usage", response_model=AccountUsageResponse)
async def account_usage(identity: SessionIdentity = Depends(require_mfa_session)) -> JSONResponse:
    used, limit = _auth_service().get_daily_usage(identity.username)
    remaining = None if limit is None else max(limit - used, 0)
    return JSONResponse(
        content=AccountUsageResponse(
            username=identity.username,
            used_today=used,
            daily_doc_limit=limit,
            remaining_today=remaining,
        ).model_dump()
    )


@app.get("/account/defaults", response_model=AccountDefaultsResponse)
async def account_defaults(identity: SessionIdentity = Depends(require_mfa_session)) -> JSONResponse:
    try:
        author, company_name = _auth_service().get_account_defaults(identity.username)
        return JSONResponse(content=AccountDefaultsResponse(author=author, company_name=company_name).model_dump())
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post("/account/defaults", response_model=AccountDefaultsResponse)
async def update_account_defaults(
    request: UpdateAccountDefaultsRequest,
    identity: SessionIdentity = Depends(require_mfa_session),
) -> JSONResponse:
    try:
        author, company_name = _auth_service().update_account_defaults(
            identity.username,
            request.author,
            request.company_name,
        )
        return JSONResponse(content=AccountDefaultsResponse(author=author, company_name=company_name).model_dump())
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.get("/admin/users", response_model=list[UserAccount])
async def list_users(_: SessionIdentity = Depends(require_admin_session)) -> JSONResponse:
    users = _auth_service().list_users()
    return JSONResponse(content=[user.model_dump() for user in users])


@app.post("/admin/users", response_model=UserAccount)
async def create_user(request: CreateUserRequest, _: SessionIdentity = Depends(require_admin_session)) -> JSONResponse:
    try:
        user = _auth_service().create_user(
            username=request.username,
            password=request.password,
            email=request.email,
            is_admin=request.is_admin,
            daily_doc_limit=request.daily_doc_limit,
        )
        return JSONResponse(content=user.model_dump())
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post("/admin/users/invite")
async def invite_user(request: InviteUserRequest, _: SessionIdentity = Depends(require_admin_session)) -> JSONResponse:
    try:
        token = _auth_service().create_invitation_token(request.email, request.is_admin, request.daily_doc_limit)
        settings = get_settings()
        link = f"{settings.app_base_url.rstrip('/')}/accept-invite?token={token}"
        EmailService(settings).send(
            request.email,
            "DocAgent account invitation",
            "You were invited to DocAgent. Use this link to create your account (valid 7 days):\n\n"
            f"{link}\n",
        )
        return JSONResponse(content={"success": True})
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post("/admin/users/{username}/daily-limit", response_model=UserAccount)
async def set_user_daily_limit(
    username: str,
    request: SetUserDailyLimitRequest,
    _: SessionIdentity = Depends(require_admin_session),
) -> JSONResponse:
    try:
        user = _auth_service().set_user_daily_limit(username, request.daily_doc_limit)
        return JSONResponse(content=user.model_dump())
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post("/admin/users/{username}/disable", response_model=UserAccount)
async def set_user_disabled(
    username: str,
    request: SetUserDisabledRequest,
    identity: SessionIdentity = Depends(require_admin_session),
) -> JSONResponse:
    try:
        user = _auth_service().set_user_disabled(username, request.disabled, identity.username)
        return JSONResponse(content=user.model_dump())
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.post("/admin/users/{username}/reset-password", response_model=UserAccount)
async def reset_user_password(
    username: str,
    request: ResetUserPasswordRequest,
    _: SessionIdentity = Depends(require_admin_session),
) -> JSONResponse:
    try:
        user = _auth_service().reset_user_password(username, request.password, reset_mfa=True)
        return JSONResponse(content=user.model_dump())
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.delete("/admin/users/{username}")
async def delete_user(
    username: str,
    identity: SessionIdentity = Depends(require_admin_session),
) -> JSONResponse:
    try:
        _auth_service().delete_user(username, identity.username)
        return JSONResponse(content={"success": True})
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.get("/admin/settings/deepseek", response_model=DeepSeekSettingsResponse)
async def admin_get_deepseek_settings(_: SessionIdentity = Depends(require_admin_session)) -> JSONResponse:
    return JSONResponse(content=get_deepseek_settings().model_dump())


@app.post("/admin/settings/deepseek", response_model=DeepSeekSettingsResponse)
async def admin_update_deepseek_settings(
    request: UpdateDeepSeekSettingsRequest,
    _: SessionIdentity = Depends(require_admin_session),
) -> JSONResponse:
    updated = update_deepseek_settings(request)
    return JSONResponse(content=updated.model_dump())


@app.get("/admin/settings/email", response_model=EmailSettingsResponse)
async def admin_get_email_settings(_: SessionIdentity = Depends(require_admin_session)) -> JSONResponse:
    return JSONResponse(content=get_email_settings().model_dump())


@app.post("/admin/settings/email", response_model=EmailSettingsResponse)
async def admin_update_email_settings(
    request: UpdateEmailSettingsRequest,
    _: SessionIdentity = Depends(require_admin_session),
) -> JSONResponse:
    updated = update_email_settings(request)
    return JSONResponse(content=updated.model_dump())


@app.post("/admin/settings/deepseek/test", response_model=DeepSeekConnectionTestResponse)
async def admin_test_deepseek_connection(_: SessionIdentity = Depends(require_admin_session)) -> JSONResponse:
    settings = get_settings()
    client = DeepSeekClient(settings)
    try:
        response = await client.complete(
            system_prompt="You are validating API connectivity. Return exactly OK.",
            user_prompt="Return OK",
            temperature=0.0,
        )
        return JSONResponse(content=DeepSeekConnectionTestResponse(success=True, detail=response[:200]).model_dump())
    except Exception as exc:
        return JSONResponse(
            content=DeepSeekConnectionTestResponse(success=False, detail=str(exc)).model_dump(),
            status_code=status.HTTP_400_BAD_REQUEST,
        )


@app.get("/admin/settings/document-defaults", response_model=DocumentDefaultsResponse)
async def admin_get_document_defaults(_: SessionIdentity = Depends(require_admin_session)) -> JSONResponse:
    return JSONResponse(content=get_document_defaults().model_dump())


@app.post("/admin/settings/document-defaults", response_model=DocumentDefaultsResponse)
async def admin_update_document_defaults(
    request: UpdateDocumentDefaultsRequest,
    _: SessionIdentity = Depends(require_admin_session),
) -> JSONResponse:
    updated = update_document_defaults(request)
    return JSONResponse(content=updated.model_dump())


@app.get("/document-types")
async def document_types(_: SessionIdentity = Depends(require_mfa_session)) -> list[dict[str, object]]:
    return [item.model_dump() for item in list_document_types()]


@app.post("/documents/recommend-template", response_model=TemplateRecommendationResponse)
async def recommend_template(
    request: TemplateRecommendationRequest,
    _: SessionIdentity = Depends(require_mfa_session),
) -> JSONResponse:
    pipeline = DocumentPipeline(get_settings())
    result = await pipeline.recommend_document_types(request)
    return JSONResponse(content=result.model_dump())


@app.post("/documents/analyze-notes", response_model=AnalyzedNotesResponse)
async def analyze_notes(request: AnalyzeNotesRequest, _: SessionIdentity = Depends(require_mfa_session)) -> JSONResponse:
    pipeline = DocumentPipeline(get_settings())
    result = await pipeline.analyze_notes(request.raw_notes)
    return JSONResponse(content=result.model_dump())


@app.post("/documents/build", response_model=DocumentBuildResponse)
async def build_document(
    http_request: Request,
    request: DocumentBuildRequest,
    identity: SessionIdentity = Depends(require_mfa_session),
) -> JSONResponse:
    try:
        _auth_service().consume_document_generation(identity.username)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    pipeline = DocumentPipeline(get_settings())
    build_request = request.model_copy(
        update={
            "generate_docx": False,
            "company_logo_url": _absolute_logo_url(request.company_logo_url, http_request),
        }
    )
    result = await pipeline.build_document(build_request, identity.username)

    payload = DocumentBuildResponse(
        doc_id=None,
        html=result.html,
        prompt=result.prompt,
        document_type=result.document_type,
        tracking_code=result.tracking_code,
        docx_path=None,
    )
    return JSONResponse(content=payload.model_dump())


@app.post("/documents/save", response_model=SaveDocumentResponse)
async def save_document(
    http_request: Request,
    request: SaveDocumentRequest,
    identity: SessionIdentity = Depends(require_mfa_session),
) -> JSONResponse:
    if not request.html.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to save.")

    settings = get_settings()
    doc_id = uuid4().hex
    user_dir = settings.output_dir / identity.username / doc_id
    user_dir.mkdir(parents=True, exist_ok=True)

    file_name = _slugify_filename(request.title)
    html_path = user_dir / f"{file_name}.html"
    docx_path = user_dir / f"{file_name}.docx"

    saved_html = _absolutize_logo_urls_in_html(request.html, http_request)
    html_path.write_text(saved_html, encoding="utf-8")
    export_html_to_docx(saved_html, docx_path, request.title)

    DocumentStore(settings).save_document(
        doc_id=doc_id,
        username=identity.username,
        title=request.title,
        document_type=request.document_type,
        tracking_code=request.tracking_code,
        html_path=html_path,
        docx_path=docx_path,
    )

    return JSONResponse(content=SaveDocumentResponse(doc_id=doc_id, tracking_code=request.tracking_code).model_dump())


@app.get("/documents/history", response_model=list[DocumentHistoryItem])
async def get_document_history(identity: SessionIdentity = Depends(require_mfa_session)) -> JSONResponse:
    rows = DocumentStore(get_settings()).list_documents(identity.username)
    items = [
        DocumentHistoryItem(
            doc_id=r["doc_id"],
            title=r["title"],
            document_type=r["document_type"],
            tracking_code=r["tracking_code"],
            created_at=r["created_at"],
            has_html=bool(r.get("html_path")),
            has_docx=bool(r.get("docx_path")),
            file_size_bytes=r["file_size_bytes"],
        )
        for r in rows
    ]
    return JSONResponse(content=[i.model_dump() for i in items])


@app.get("/documents/{doc_id}/download")
async def download_document(
    doc_id: str,
    format: str = "docx",
    identity: SessionIdentity = Depends(require_mfa_session),
) -> FileResponse:
    from pathlib import Path as _Path
    record = DocumentStore(get_settings()).get_document(doc_id, identity.username)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    if format == "docx":
        raw = record.get("docx_path")
        if not raw or not _Path(raw).exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DOCX file not available.")
        p = _Path(raw)
        return FileResponse(
            str(p),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=p.name,
        )
    if format == "html":
        raw = record.get("html_path")
        if not raw or not _Path(raw).exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HTML file not available.")
        p = _Path(raw)
        return FileResponse(str(p), media_type="text/html", filename=p.name)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid format. Use docx or html.")


@app.get("/documents/{doc_id}/preview", response_class=HTMLResponse)
async def preview_document(
    doc_id: str,
    autoprint: bool = False,
    identity: SessionIdentity = Depends(require_mfa_session),
) -> HTMLResponse:
    from pathlib import Path as _Path
    record = DocumentStore(get_settings()).get_document(doc_id, identity.username)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    raw = record.get("html_path")
    if not raw or not _Path(raw).exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="HTML file not available.")
    html = _Path(raw).read_text(encoding="utf-8")
    if autoprint:
        html = html.replace(
            "</body>",
            "<script>window.addEventListener('load',()=>window.print());</script></body>",
        )
    return HTMLResponse(content=html)


@app.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    identity: SessionIdentity = Depends(require_mfa_session),
) -> JSONResponse:
    DocumentStore(get_settings()).delete_document(doc_id, identity.username)
    return JSONResponse(content={"success": True})


@app.post("/documents/restyle-html", response_model=RestyleHtmlResponse)
async def restyle_html(request: RestyleHtmlRequest, _: SessionIdentity = Depends(require_mfa_session)) -> JSONResponse:
    pipeline = DocumentPipeline(get_settings())
    updated_html = pipeline.restyle_generated_html(request.html, request.theme)
    return JSONResponse(content=RestyleHtmlResponse(html=updated_html, theme=request.theme).model_dump())