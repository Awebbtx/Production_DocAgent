from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field


class DocumentTypeDefinition(BaseModel):
    key: str
    name: str
    category: str
    type_code: str = "GEN"
    subtype_code: str = "000"
    description: str
    common_triggers: list[str] = Field(default_factory=list)
    required_sections: list[str] = Field(default_factory=list)


class TemplateRecommendationRequest(BaseModel):
    company_name: str = ""
    department: str = "IT Department"
    document_date: date = Field(default_factory=date.today)
    project_details: str = ""
    raw_notes: str
    work_items: list[str] = Field(default_factory=list)


class TemplateRecommendation(BaseModel):
    rank: int
    document_type: str
    document_name: str
    confidence: str
    rationale: str


class TemplateRecommendationResponse(BaseModel):
    suggested_title: str
    recommendations: list[TemplateRecommendation]


class AnalyzeNotesRequest(BaseModel):
    raw_notes: str


class AnalyzedNotesResponse(BaseModel):
    title: str
    author: str
    company_name: str
    department: str
    document_date: str  # ISO YYYY-MM-DD for direct JS/form use
    tracking_code: str
    suggested_theme: str
    project_details: str
    work_items: list[str]
    document_type: str
    recommendations: list[TemplateRecommendation]


class DocumentBuildRequest(BaseModel):
    title: str
    author: str = ""
    company_name: str = ""
    company_logo_url: str = ""
    department: str = "IT Department"
    document_date: date = Field(default_factory=date.today)
    theme: str = "smtp"
    document_type: str = "general-work-report"
    project_details: str = ""
    raw_notes: str
    work_items: list[str] = Field(default_factory=list)
    template_name: str = "default"
    generate_docx: bool = True


class GeneratedDocument(BaseModel):
    html: str
    prompt: str
    document_type: str
    tracking_code: str
    docx_path: Path | None = None
    doc_id: str = ""
    html_path: Path | None = None


class DocumentBuildResponse(BaseModel):
    doc_id: str | None = None
    html: str
    prompt: str
    document_type: str
    tracking_code: str
    docx_path: str | None = None


class SaveDocumentRequest(BaseModel):
    title: str
    document_type: str
    tracking_code: str
    html: str


class SaveDocumentResponse(BaseModel):
    doc_id: str
    tracking_code: str
    saved: bool = True


class DocumentHistoryItem(BaseModel):
    doc_id: str
    title: str
    document_type: str
    tracking_code: str
    created_at: str
    has_html: bool
    has_docx: bool
    file_size_bytes: int


class RestyleHtmlRequest(BaseModel):
    html: str
    theme: str = "smtp"


class RestyleHtmlResponse(BaseModel):
    html: str
    theme: str


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    mfa_required: bool = False
    mfa_enrollment_required: bool = False
    challenge_token: str | None = None
    otpauth_uri: str | None = None
    mfa_secret: str | None = None
    mfa_qr_svg_data_uri: str | None = None


class VerifyMfaRequest(BaseModel):
    challenge_token: str
    code: str


class AuthSessionResponse(BaseModel):
    authenticated: bool
    username: str | None = None
    is_admin: bool = False
    mfa_verified: bool = False


class CreateUserRequest(BaseModel):
    username: str
    password: str
    email: str = ""
    is_admin: bool = False
    daily_doc_limit: int | None = 25


class UserAccount(BaseModel):
    username: str
    email: str = ""
    is_admin: bool
    mfa_enabled: bool
    disabled: bool
    daily_doc_limit: int | None = None
    created_at: str


class SetUserDisabledRequest(BaseModel):
    disabled: bool


class ResetUserPasswordRequest(BaseModel):
    password: str


class SetUserDailyLimitRequest(BaseModel):
    daily_doc_limit: int | None = None


class AccountUsageResponse(BaseModel):
    username: str
    used_today: int
    daily_doc_limit: int | None = None
    remaining_today: int | None = None


class ChangeOwnPasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ResetOwnMfaRequest(BaseModel):
    current_password: str


class DeepSeekSettingsResponse(BaseModel):
    deepseek_model: str
    deepseek_base_url: str
    api_key_configured: bool


class UpdateDeepSeekSettingsRequest(BaseModel):
    deepseek_model: str
    deepseek_base_url: str
    deepseek_api_key: str = ""


class DeepSeekConnectionTestResponse(BaseModel):
    success: bool
    detail: str


class DocumentDefaultsResponse(BaseModel):
    author: str = ""
    company_name: str = ""
    company_logo_url: str = ""


class UpdateDocumentDefaultsRequest(BaseModel):
    author: str = ""
    company_name: str = ""
    company_logo_url: str = ""


class AccountDefaultsResponse(BaseModel):
    author: str = ""
    company_name: str = ""


class UpdateAccountDefaultsRequest(BaseModel):
    author: str = ""
    company_name: str = ""


class LogoOption(BaseModel):
    filename: str
    url: str
    size_bytes: int
    created_at: str


class LogoLibraryResponse(BaseModel):
    logos: list[LogoOption] = Field(default_factory=list)
    max_items: int = 5
    max_file_size_bytes: int = 1048576


class EmailSettingsResponse(BaseModel):
    app_base_url: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_use_tls: bool
    smtp_from_email: str
    smtp_configured: bool


class UpdateEmailSettingsRequest(BaseModel):
    app_base_url: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_email: str


class InviteUserRequest(BaseModel):
    email: str
    is_admin: bool = False
    daily_doc_limit: int | None = 25


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirmRequest(BaseModel):
    token: str
    new_password: str


class InvitationAcceptRequest(BaseModel):
    token: str
    username: str
    password: str