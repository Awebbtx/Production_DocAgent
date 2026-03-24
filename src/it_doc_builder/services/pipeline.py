from __future__ import annotations

import json
import re
from datetime import date
from html import escape
from pathlib import Path
from uuid import uuid4

from jinja2 import Environment, FileSystemLoader, select_autoescape

from it_doc_builder.clients.deepseek import DeepSeekClient
from it_doc_builder.config import Settings
from it_doc_builder.document_types import build_document_type_catalog, build_tracking_code, get_document_type, list_document_types
from it_doc_builder.models import (
    AnalyzedNotesResponse,
    DocumentBuildRequest,
    GeneratedDocument,
    TemplateRecommendation,
    TemplateRecommendationRequest,
    TemplateRecommendationResponse,
)
from it_doc_builder.services.docx_exporter import export_html_to_docx


class DocumentPipeline:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = DeepSeekClient(settings)
        template_path = settings.html_template_path
        self._jinja = Environment(
            loader=FileSystemLoader(str(template_path.parent)),
            autoescape=select_autoescape(enabled_extensions=("html", "j2")),
        )

    async def recommend_document_types(
        self,
        request: TemplateRecommendationRequest,
    ) -> TemplateRecommendationResponse:
        prompt = self._build_recommendation_prompt(request)
        if not self._settings.deepseek_api_key:
            recommendations = self._fallback_recommendations(request)
            suggested_title = self._fallback_title(request, recommendations[0].document_name)
            return TemplateRecommendationResponse(suggested_title=suggested_title, recommendations=recommendations)

        try:
            response = await self._client.recommend_templates(prompt)
            suggested_title, recommendations = self._parse_recommendations(response)
        except Exception:
            recommendations = self._fallback_recommendations(request)
            suggested_title = self._fallback_title(request, recommendations[0].document_name)

        if not suggested_title:
            suggested_title = self._fallback_title(request, recommendations[0].document_name)

        return TemplateRecommendationResponse(suggested_title=suggested_title, recommendations=recommendations[:3])

    async def build_document(self, request: DocumentBuildRequest, username: str = "anonymous") -> GeneratedDocument:
        document_type = get_document_type(request.document_type)
        tracking_code = build_tracking_code(
            document_type.key,
            request.document_date,
            sequence=request.tracking_sequence,
            revision=request.revision,
        )
        stylesheet_path = self._resolve_stylesheet_path(request.theme)
        stylesheet = self._read_stylesheet(stylesheet_path)
        prompt = self._build_prompt(request, stylesheet, tracking_code)
        generated_raw = await self._client.generate_html(prompt)
        generated_body = self._normalize_generated_body(generated_raw)
        full_html = self._render_html(
            request=request,
            generated_body=generated_body,
            stylesheet=stylesheet,
            tracking_code=tracking_code,
        )

        doc_id = uuid4().hex
        user_dir = self._settings.output_dir / username / doc_id
        user_dir.mkdir(parents=True, exist_ok=True)

        file_name = self._slugify(request.title)
        html_path = user_dir / f"{file_name}.html"
        html_path.write_text(full_html, encoding="utf-8")

        docx_path: Path | None = None
        if request.generate_docx:
            docx_path = export_html_to_docx(
                full_html,
                user_dir / f"{file_name}.docx",
                request.title,
            )

        return GeneratedDocument(
            html=full_html,
            prompt=prompt,
            document_type=document_type.key,
            tracking_code=tracking_code,
            revision=request.revision,
            document_status=request.document_status,
            classification=request.classification,
            retention_policy=request.retention_policy,
            document_owner=request.document_owner,
            approver=request.approver,
            docx_path=docx_path,
            doc_id=doc_id,
            html_path=html_path,
        )

    def restyle_generated_html(self, full_html: str, theme: str) -> str:
        stylesheet_path = self._resolve_stylesheet_path(theme)
        stylesheet = self._read_stylesheet(stylesheet_path)
        return self._replace_html_stylesheet(full_html, stylesheet)

    def _render_html(self, request: DocumentBuildRequest, generated_body: str, stylesheet: str, tracking_code: str) -> str:
        template = self._jinja.get_template(self._settings.html_template_path.name)
        document_type = get_document_type(request.document_type)
        return template.render(
            title=request.title,
            author=request.author,
            company_name=request.company_name,
            company_logo_url=request.company_logo_url,
            department=request.department,
            document_date=request.document_date.isoformat(),
            tracking_code=tracking_code,
            revision=request.revision,
            document_status=request.document_status,
            classification=request.classification,
            retention_policy=request.retention_policy,
            document_owner=request.document_owner,
            approver=request.approver,
            document_type_name=document_type.name,
            work_items=request.work_items,
            generated_body=generated_body,
            stylesheet=stylesheet,
        )

    @staticmethod
    def _build_prompt(request: DocumentBuildRequest, stylesheet: str, tracking_code: str) -> str:
        document_type = get_document_type(request.document_type)
        work_items = "\n".join(f"- {item}" for item in request.work_items) or "- No discrete work items supplied"
        project_details = request.project_details.strip() or "No separate project details were supplied."
        sections = ", ".join(document_type.required_sections)
        style_guide = DocumentPipeline._style_guide_text(document_type)
        logo_guidance = (
            f"Company logo URL: {request.company_logo_url}. "
            "The report template renders the logo in a fixed 220x70 px frame with object-fit: contain. "
            "Do not emit extra logo images in generated body HTML."
            if request.company_logo_url
            else "No company logo URL provided."
        )
        return (
            f"Create a polished IT work report for the {request.department}.\n"
            f"Document type: {document_type.name}.\n"
            f"Title: {request.title}\n"
            f"Author: {request.author}\n"
            f"Company: {request.company_name or 'Not provided'}\n"
            f"Document date: {request.document_date.isoformat()}\n"
            f"Tracking code: {tracking_code}\n"
            f"Revision: {request.revision}\n"
            f"Document status: {request.document_status}\n"
            f"Classification: {request.classification}\n"
            f"Retention policy: {request.retention_policy or 'Not provided'}\n"
            f"Document owner: {request.document_owner or request.author or 'Not provided'}\n"
            f"Approver: {request.approver or 'Not provided'}\n"
            f"Theme: {request.theme}\n"
            f"Branding guidance: {logo_guidance}\n"
            f"Required sections: {sections}.\n"
            "Use concise business language and structured style tags only.\n"
            "Return only STYLE-TAG output (no HTML, no markdown fences).\n"
            f"Style tag framework:\n{DocumentPipeline._style_tag_framework_text()}\n"
            f"Template guidance: {document_type.description}\n"
            f"Typical triggers: {', '.join(document_type.common_triggers)}\n"
            f"Style guidance: {style_guide}\n"
            f"Template stylesheet:\n{stylesheet}\n\n"
            f"Project details:\n{project_details}\n\n"
            f"Work items:\n{work_items}\n\n"
            f"Raw notes:\n{request.raw_notes}"
        )

    @staticmethod
    def _style_tag_framework_text() -> str:
        return (
            "[SECTION: Heading] starts a section; server closes sections automatically.\n"
            "[P] paragraph text\n"
            "[UL] ... [/UL] with one list item per line (optional '- ' prefix)\n"
            "[OL] ... [/OL] with one list item per line\n"
            "[NOTE] text, [WARNING] text, [SUCCESS] text\n"
            "[CODE] ... [/CODE] for scripts/commands\n"
            "[TABLE] ... [/TABLE] using pipe rows, first row header:\n"
            "| Col A | Col B |\n"
            "| Value A | Value B |\n"
            "Rules: no [TITLE], no logo/image tags, no raw HTML, no markdown code fences."
        )

    @staticmethod
    def _normalize_generated_body(model_output: str) -> str:
        cleaned = model_output.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z0-9]*\n", "", cleaned)
            cleaned = cleaned.removesuffix("```").strip()

        # Style-tag mode
        if re.search(r"\[(SECTION:|P\]|UL\]|OL\]|NOTE\]|WARNING\]|SUCCESS\]|CODE\]|TABLE\]|H[1-6]\])", cleaned):
            return DocumentPipeline._style_tags_to_html(cleaned)

        # Backward-compatible HTML mode
        return DocumentPipeline._sanitize_html_fragment(cleaned)

    @staticmethod
    def _sanitize_html_fragment(fragment: str) -> str:
        content = fragment
        body_match = re.search(r"<body[^>]*>(.*?)</body>", content, flags=re.IGNORECASE | re.DOTALL)
        if body_match:
            content = body_match.group(1).strip()

        # Strip outer shell wrappers commonly returned by LLMs.
        content = re.sub(r"<main[^>]*class=\"[^\"]*report-shell[^\"]*\"[^>]*>", "", content, flags=re.IGNORECASE)
        content = re.sub(r"</main>", "", content, flags=re.IGNORECASE)
        content = re.sub(r"<header[^>]*class=\"[^\"]*report-header[^\"]*\"[^>]*>.*?</header>", "", content, flags=re.IGNORECASE | re.DOTALL)
        content = re.sub(r"<(html|head|body|style|script)[^>]*>.*?</\1>", "", content, flags=re.IGNORECASE | re.DOTALL)
        return content.strip()

    @staticmethod
    def _style_tags_to_html(tag_text: str) -> str:
        lines = [line.rstrip() for line in tag_text.splitlines()]
        out: list[str] = []
        i = 0
        section_open = False
        closing_tag_pattern = re.compile(r"\s*\[/(?:SECTION|P|NOTE|WARNING|SUCCESS|UL|OL|CODE|TABLE|H[1-6])\]\s*$", flags=re.IGNORECASE)

        while i < len(lines):
            raw_line = lines[i]
            line = raw_line.strip()
            i += 1
            if not line:
                continue

            inline_code_match = re.match(r"^\[CODE\](.*?)\[/CODE\]$", line, flags=re.IGNORECASE | re.DOTALL)
            if inline_code_match:
                inline_code = inline_code_match.group(1).strip()
                out.append(f"<pre><code>{escape(inline_code)}</code></pre>")
                continue

            inline_heading_match = re.match(r"^\[H([1-6])\](.*?)\[/H\1\]$", line, flags=re.IGNORECASE | re.DOTALL)
            if inline_heading_match:
                level = inline_heading_match.group(1)
                heading_text = inline_heading_match.group(2).strip()
                out.append(f"<h{level}>{escape(heading_text)}</h{level}>")
                continue

            # Be tolerant of malformed model output where only closing tags are emitted.
            line = closing_tag_pattern.sub("", line).strip()
            if not line:
                continue

            section_match = re.match(r"^\[SECTION:\s*(.+?)\]\s*$", line, flags=re.IGNORECASE)
            if section_match:
                if section_open:
                    out.append("</section>")
                section_open = True
                out.append("<section>")
                out.append(f"<h2>{escape(section_match.group(1).strip())}</h2>")
                continue

            if line.upper().startswith("[P]"):
                out.append(f"<p>{escape(line[3:].strip())}</p>")
                continue

            if line.upper().startswith("[NOTE]"):
                out.append(f"<div class=\"info-box\"><strong>Note:</strong> {escape(line[6:].strip())}</div>")
                continue

            if line.upper().startswith("[WARNING]"):
                out.append(f"<div class=\"warning-box\"><strong>Warning:</strong> {escape(line[9:].strip())}</div>")
                continue

            if line.upper().startswith("[SUCCESS]"):
                out.append(f"<div class=\"success-box\"><strong>Success:</strong> {escape(line[9:].strip())}</div>")
                continue

            implicit_callout_match = re.match(r"^(note|warning|success)\s*:\s*(.+)$", line, flags=re.IGNORECASE)
            if implicit_callout_match:
                kind = implicit_callout_match.group(1).lower()
                content = implicit_callout_match.group(2).strip()
                if kind == "note":
                    out.append(f"<div class=\"info-box\"><strong>Note:</strong> {escape(content)}</div>")
                elif kind == "warning":
                    out.append(f"<div class=\"warning-box\"><strong>Warning:</strong> {escape(content)}</div>")
                else:
                    out.append(f"<div class=\"success-box\"><strong>Success:</strong> {escape(content)}</div>")
                continue

            if line.upper() == "[UL]":
                items: list[str] = []
                while i < len(lines) and lines[i].strip().upper() != "[/UL]":
                    item = lines[i].strip()
                    i += 1
                    if not item:
                        continue
                    items.append(item[2:].strip() if item.startswith("- ") else item)
                if i < len(lines) and lines[i].strip().upper() == "[/UL]":
                    i += 1
                out.append("<ul>")
                out.extend(f"<li>{escape(item)}</li>" for item in items)
                out.append("</ul>")
                continue

            if line.upper() == "[OL]":
                items = []
                while i < len(lines) and lines[i].strip().upper() != "[/OL]":
                    item = lines[i].strip()
                    i += 1
                    if item:
                        items.append(item)
                if i < len(lines) and lines[i].strip().upper() == "[/OL]":
                    i += 1
                out.append("<ol>")
                out.extend(f"<li>{escape(item)}</li>" for item in items)
                out.append("</ol>")
                continue

            if line.upper() == "[CODE]":
                code_lines: list[str] = []
                while i < len(lines) and lines[i].strip().upper() != "[/CODE]":
                    code_lines.append(lines[i])
                    i += 1
                if i < len(lines) and lines[i].strip().upper() == "[/CODE]":
                    i += 1
                out.append(f"<pre><code>{escape(chr(10).join(code_lines).strip())}</code></pre>")
                continue

            if line.upper() == "[TABLE]":
                rows: list[list[str]] = []
                while i < len(lines) and lines[i].strip().upper() != "[/TABLE]":
                    row_line = lines[i].strip()
                    i += 1
                    if not row_line or "|" not in row_line:
                        continue
                    cells = [cell.strip() for cell in row_line.strip("|").split("|")]
                    # Skip markdown-style separator row.
                    if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells if cell):
                        continue
                    rows.append(cells)
                if i < len(lines) and lines[i].strip().upper() == "[/TABLE]":
                    i += 1
                if rows:
                    header = rows[0]
                    body = rows[1:]
                    out.append("<table><thead><tr>")
                    out.extend(f"<th>{escape(cell)}</th>" for cell in header)
                    out.append("</tr></thead><tbody>")
                    for row in body:
                        out.append("<tr>")
                        out.extend(f"<td>{escape(cell)}</td>" for cell in row)
                        out.append("</tr>")
                    out.append("</tbody></table>")
                continue

            # Default fallback: plain paragraph
            out.append(f"<p>{escape(line)}</p>")

        if section_open:
            out.append("</section>")
        return "\n".join(out)

    @staticmethod
    def _build_recommendation_prompt(request: TemplateRecommendationRequest) -> str:
        work_items = "\n".join(f"- {item}" for item in request.work_items) or "- No discrete work items supplied"
        project_details = request.project_details.strip() or "No separate project details were supplied."
        return (
            "From these IT documents, determine the best template match to the context of the notes.\n"
            "Limit the response to the top 3 matches ranked by confidence.\n"
            "Also propose a concise, specific document title based on the context.\n"
            "Return only a JSON object with two keys: suggested_title and recommendations.\n"
            "recommendations must be a JSON array of objects containing rank, document_type, confidence, and rationale.\n"
            "Use confidence values high, medium, or low.\n\n"
            f"Available templates:\n{build_document_type_catalog()}\n\n"
            f"Company: {request.company_name or 'Not provided'}\n"
            f"Department: {request.department}\n"
            f"Document date: {request.document_date.isoformat()}\n"
            f"Project details:\n{project_details}\n\n"
            f"Work items:\n{work_items}\n\n"
            f"Raw notes:\n{request.raw_notes}"
        )

    @staticmethod
    def _parse_recommendations(response: str) -> tuple[str, list[TemplateRecommendation]]:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z0-9]*\n", "", cleaned)
            cleaned = cleaned.removesuffix("```").strip()

        data = json.loads(cleaned)
        suggested_title = ""
        if isinstance(data, dict):
            suggested_title = str(data.get("suggested_title", "")).strip()
            recommendation_data = data.get("recommendations", [])
        elif isinstance(data, list):
            recommendation_data = data
        else:
            raise ValueError("Recommendation payload must be a list or object")

        if not isinstance(recommendation_data, list):
            raise ValueError("recommendations must be a list")

        recommendations: list[TemplateRecommendation] = []
        for index, item in enumerate(recommendation_data[:3], start=1):
            definition = get_document_type(str(item.get("document_type", "")))
            recommendations.append(
                TemplateRecommendation(
                    rank=index,
                    document_type=definition.key,
                    document_name=definition.name,
                    confidence=str(item.get("confidence", "medium")).lower(),
                    rationale=str(item.get("rationale", definition.description)),
                )
            )

        if not recommendations:
            raise ValueError("No recommendations returned")
        return suggested_title, recommendations

    @staticmethod
    def _fallback_recommendations(request: TemplateRecommendationRequest) -> list[TemplateRecommendation]:
        corpus = " ".join([request.department, request.project_details, request.raw_notes, *request.work_items]).lower()
        security_keywords = {
            "vulnerability",
            "cve",
            "ioc",
            "siem",
            "soc",
            "phishing",
            "malware",
            "threat",
            "incident",
            "containment",
            "forensic",
            "penetration",
            "audit",
            "compliance",
            "control",
        }
        has_security_context = any(keyword in corpus for keyword in security_keywords)
        scored: list[tuple[int, str]] = []
        for definition in list_document_types():
            haystack = " ".join(
                [
                    definition.key.replace("-", " "),
                    definition.name,
                    definition.category,
                    definition.description,
                    *definition.common_triggers,
                    *definition.required_sections,
                ]
            ).lower()
            score = sum(2 for token in haystack.split() if token in corpus and len(token) > 3)
            score += sum(4 for trigger in definition.common_triggers if trigger.lower() in corpus)
            if has_security_context and definition.category.lower() == "cybersecurity":
                score += 14
            scored.append((score, definition.key))

        ranked = sorted(scored, key=lambda item: item[0], reverse=True)[:3]
        recommendations: list[TemplateRecommendation] = []
        confidence_labels = ["high", "medium", "medium"]
        for index, (_, key) in enumerate(ranked, start=1):
            definition = get_document_type(key)
            recommendations.append(
                TemplateRecommendation(
                    rank=index,
                    document_type=definition.key,
                    document_name=definition.name,
                    confidence=confidence_labels[index - 1],
                    rationale=definition.description,
                )
            )
        return recommendations

    @staticmethod
    def _style_guide_text(document_type: object) -> str:
        definition = document_type
        return (
            f"Use a formal heading hierarchy, clearly labeled sections for {', '.join(definition.required_sections)}, "
            "short executive prose, and lists or tables where operational details need to scan quickly."
        )

    @staticmethod
    def _fallback_title(request: TemplateRecommendationRequest, document_name: str) -> str:
        project_snippet = request.project_details.strip() or request.raw_notes.strip()
        first_line = project_snippet.splitlines()[0] if project_snippet else "IT Work Summary"
        first_line = re.sub(r"\s+", " ", first_line).strip(" .:-")
        if len(first_line) > 70:
            first_line = first_line[:67].rstrip() + "..."
        return f"{document_name} - {first_line}" if first_line else document_name

    # ------------------------------------------------------------------
    # Notes analysis: single DeepSeek call → all form fields + top 3
    # ------------------------------------------------------------------

    async def analyze_notes(self, raw_notes: str) -> AnalyzedNotesResponse:
        prompt = self._build_analysis_prompt(raw_notes)
        if not self._settings.deepseek_api_key:
            return self._fallback_analysis(raw_notes)
        try:
            response = await self._client.recommend_templates(prompt)
            return self._parse_analysis(response)
        except Exception:
            return self._fallback_analysis(raw_notes)

    @staticmethod
    def _build_analysis_prompt(raw_notes: str) -> str:
        today = date.today().isoformat()
        return (
            "You are an IT documentation specialist. Extract structured metadata from the raw technical notes below.\n"
            f"Today's date is {today}.\n\n"
            "If the notes are security-focused (vulnerabilities, incidents, threats, phishing, control validation, audit/compliance, penetration testing), strongly prioritize cybersecurity templates.\n\n"
            "Return a single JSON object with exactly these keys:\n"
            '  "title"          — concise document title (e.g. "Core Switch Replacement – Building A")\n'
            '  "author"         — technician or engineer name if mentioned, otherwise ""\n'
            '  "company_name"   — organisation or client name if mentioned, otherwise ""\n'
            '  "department"     — department name if mentioned, otherwise "IT Department"\n'
            f'  "document_date"  — date the work occurred in YYYY-MM-DD format, otherwise "{today}"\n'
            '  "project_details"— 2-3 sentence summary of scope and business purpose\n'
            '  "work_items"     — array of discrete completed tasks as short imperative sentences\n'
            '  "document_type"  — the single best-matching template key from the catalog below\n'
            '  "recommendations"— top 3 template matches as [{rank, document_type, confidence (high/medium/low), rationale}]\n\n'
            f"Available templates:\n{build_document_type_catalog()}\n\n"
            f"Raw notes:\n{raw_notes}"
        )

    @staticmethod
    def _parse_analysis(response: str) -> AnalyzedNotesResponse:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z0-9]*\n", "", cleaned)
            cleaned = cleaned.removesuffix("```").strip()
        data = json.loads(cleaned)
        best_type = get_document_type(str(data.get("document_type", "")))
        parsed_date = DocumentPipeline._safe_iso_date(str(data.get("document_date", date.today().isoformat())).strip())
        recommendations: list[TemplateRecommendation] = []
        for index, item in enumerate(data.get("recommendations", [])[:3], start=1):
            definition = get_document_type(str(item.get("document_type", "")))
            recommendations.append(
                TemplateRecommendation(
                    rank=index,
                    document_type=definition.key,
                    document_name=definition.name,
                    confidence=str(item.get("confidence", "medium")).lower(),
                    rationale=str(item.get("rationale", definition.description)),
                )
            )
        if not recommendations:
            recommendations = [
                TemplateRecommendation(
                    rank=1,
                    document_type=best_type.key,
                    document_name=best_type.name,
                    confidence="medium",
                    rationale=best_type.description,
                )
            ]
        return AnalyzedNotesResponse(
            title=str(data.get("title", "")).strip(),
            author=str(data.get("author", "")).strip(),
            company_name=str(data.get("company_name", "")).strip(),
            department=str(data.get("department", "IT Department")).strip() or "IT Department",
            document_date=parsed_date.isoformat(),
            tracking_code=build_tracking_code(best_type.key, parsed_date),
            suggested_theme=DocumentPipeline._suggest_theme_for_document_type(best_type.key),
            project_details=str(data.get("project_details", "")).strip(),
            work_items=[str(i).strip() for i in data.get("work_items", []) if str(i).strip()],
            document_type=best_type.key,
            recommendations=recommendations,
        )

    @staticmethod
    def _fallback_analysis(raw_notes: str) -> AnalyzedNotesResponse:
        request = TemplateRecommendationRequest(raw_notes=raw_notes)
        recommendations = DocumentPipeline._fallback_recommendations(request)
        best = recommendations[0] if recommendations else None
        first_line = raw_notes.strip().splitlines()[0] if raw_notes.strip() else "IT Work Summary"
        first_line = re.sub(r"\s+", " ", first_line).strip(" .:-")
        if len(first_line) > 70:
            first_line = first_line[:67].rstrip() + "..."
        title = f"{best.document_name} – {first_line}" if best and first_line else "IT Work Summary"
        return AnalyzedNotesResponse(
            title=title,
            author="",
            company_name="",
            department="IT Department",
            document_date=date.today().isoformat(),
            tracking_code=build_tracking_code(best.document_type if best else "general-work-report", date.today()),
            suggested_theme=DocumentPipeline._suggest_theme_for_document_type(best.document_type if best else "general-work-report"),
            project_details="",
            work_items=[],
            document_type=best.document_type if best else "general-work-report",
            recommendations=recommendations,
        )

    @staticmethod
    def _read_stylesheet(style_sheet_path: Path) -> str:
        return style_sheet_path.read_text(encoding="utf-8") if style_sheet_path.exists() else ""

    def _resolve_stylesheet_path(self, theme: str) -> Path:
        theme_key = (theme or "smtp").strip().lower()
        theme_map = {
            "smtp": self._settings.style_sheet_path,
            "azure": Path("styles/report-azure.css"),
            "security": Path("styles/report-security.css"),
        }
        return theme_map.get(theme_key, self._settings.style_sheet_path)

    @staticmethod
    def _slugify(value: str) -> str:
        return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-")

    @staticmethod
    def _safe_iso_date(value: str) -> date:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return date.today()

    @staticmethod
    def _replace_html_stylesheet(full_html: str, stylesheet: str) -> str:
        style_block = f"<style>\n{stylesheet}\n    </style>"
        if re.search(r"<style[\s\S]*?</style>", full_html, flags=re.IGNORECASE):
            return re.sub(r"<style[\s\S]*?</style>", style_block, full_html, count=1, flags=re.IGNORECASE)
        if "</head>" in full_html.lower():
            return re.sub(r"</head>", f"{style_block}\n</head>", full_html, count=1, flags=re.IGNORECASE)
        return f"{style_block}\n{full_html}"

    @staticmethod
    def _suggest_theme_for_document_type(document_type_key: str) -> str:
        definition = get_document_type(document_type_key)
        category = (definition.category or "").lower()
        if "cybersecurity" in category or "security" in category:
            return "security"
        if "business reporting" in category or "project delivery" in category:
            return "azure"
        return "smtp"