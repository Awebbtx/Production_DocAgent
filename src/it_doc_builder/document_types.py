from __future__ import annotations

from datetime import date

from it_doc_builder.models import DocumentTypeDefinition


DOCUMENT_TYPES: list[DocumentTypeDefinition] = [
    DocumentTypeDefinition(
        key="general-work-report",
        name="General Work Report",
        category="Operational",
        type_code="GWR",
        subtype_code="001",
        description="A broad summary of IT work completed for a project, ticket set, or service window.",
        common_triggers=["Weekly summary", "Project milestone", "Service desk wrap-up"],
        required_sections=["Executive Summary", "Work Performed", "Open Items", "Recommended Follow-up"],
    ),
    DocumentTypeDefinition(
        key="change-order",
        name="Change Order",
        category="Change Management",
        type_code="CHO",
        subtype_code="002",
        description="Formal documentation for planned infrastructure or service changes requiring approvals and rollback notes.",
        common_triggers=["Firewall changes", "Server reconfiguration", "Production release"],
        required_sections=["Change Summary", "Business Justification", "Implementation Plan", "Rollback Plan", "Approval Status"],
    ),
    DocumentTypeDefinition(
        key="network-update",
        name="Network Update",
        category="Network",
        type_code="NET",
        subtype_code="003",
        description="Captures switch, routing, wireless, VLAN, ISP, and cabling changes affecting network operations.",
        common_triggers=["VLAN updates", "Switch replacement", "WAN failover changes"],
        required_sections=["Scope of Change", "Network Components Affected", "Validation Results", "Risks and Dependencies"],
    ),
    DocumentTypeDefinition(
        key="incident-report",
        name="Incident Report",
        category="Operations",
        type_code="INC",
        subtype_code="004",
        description="Records an outage, service degradation, or support incident with cause, response, and resolution.",
        common_triggers=["Email outage", "Authentication failure", "Major ticket escalation"],
        required_sections=["Incident Summary", "Timeline", "Impact", "Root Cause", "Corrective Actions"],
    ),
    DocumentTypeDefinition(
        key="maintenance-window",
        name="Maintenance Window Summary",
        category="Operations",
        type_code="MWN",
        subtype_code="005",
        description="Summarizes after-hours or planned maintenance work across one or more systems.",
        common_triggers=["Patch weekend", "Storage maintenance", "Hypervisor maintenance"],
        required_sections=["Maintenance Objectives", "Tasks Completed", "Validation", "Outstanding Issues"],
    ),
    DocumentTypeDefinition(
        key="system-upgrade",
        name="System Upgrade Report",
        category="Infrastructure",
        type_code="SUP",
        subtype_code="006",
        description="Tracks software, firmware, or platform upgrades with prechecks and post-upgrade status.",
        common_triggers=["OS upgrade", "Application version upgrade", "Firmware refresh"],
        required_sections=["Upgrade Scope", "Pre-Upgrade Checks", "Execution Summary", "Post-Upgrade Validation"],
    ),
    DocumentTypeDefinition(
        key="workstation-deployment",
        name="Workstation Deployment",
        category="Endpoint",
        type_code="WSD",
        subtype_code="007",
        description="Documents endpoint builds, replacements, user migration, and handoff status.",
        common_triggers=["New hire setup", "Laptop refresh", "Department rollout"],
        required_sections=["Deployment Scope", "Assets Provisioned", "User Impact", "Completion Status"],
    ),
    DocumentTypeDefinition(
        key="access-change",
        name="Access Change Record",
        category="Identity",
        type_code="ACR",
        subtype_code="008",
        description="Records permission changes, onboarding, offboarding, or privileged access updates.",
        common_triggers=["Role changes", "Terminations", "Admin group updates"],
        required_sections=["Requested Change", "Systems Affected", "Approvals", "Verification"],
    ),
    DocumentTypeDefinition(
        key="security-finding",
        name="Security Finding",
        category="Security",
        type_code="SCF",
        subtype_code="009",
        description="Formal write-up for vulnerabilities, suspicious activity, or security control gaps.",
        common_triggers=["Vulnerability scan result", "Phishing incident", "Audit exception"],
        required_sections=["Finding Summary", "Risk Rating", "Affected Assets", "Mitigation Plan", "Owner and Due Date"],
    ),
    DocumentTypeDefinition(
        key="backup-recovery",
        name="Backup or Recovery Report",
        category="Resilience",
        type_code="BKR",
        subtype_code="010",
        description="Documents restore tests, backup issues, or disaster recovery actions and outcomes.",
        common_triggers=["Restore validation", "Recovery operation", "Backup job failures"],
        required_sections=["Scenario", "Systems Protected", "Recovery Steps", "Results", "Gaps Identified"],
    ),
    DocumentTypeDefinition(
        key="vendor-service-update",
        name="Vendor Service Update",
        category="Service Management",
        type_code="VSU",
        subtype_code="011",
        description="Summarizes provider-led changes, outages, deliverables, or implementation milestones.",
        common_triggers=["ISP cutover", "SaaS change notice", "Consultant delivery"],
        required_sections=["Vendor Activity", "Customer Impact", "Dependencies", "Next Actions"],
    ),
    DocumentTypeDefinition(
        key="asset-lifecycle",
        name="Asset Lifecycle Record",
        category="Asset Management",
        type_code="ALR",
        subtype_code="012",
        description="Tracks procurement, installation, reassignment, retirement, or disposal of equipment.",
        common_triggers=["Device retirement", "Inventory adjustments", "Warranty replacement"],
        required_sections=["Asset Summary", "Lifecycle Event", "Chain of Custody", "Record Updates"],
    ),
    DocumentTypeDefinition(
        key="project-handoff",
        name="Project Handoff",
        category="Project Delivery",
        type_code="PHO",
        subtype_code="013",
        description="Transfers a delivered solution into operations with support details and unresolved items.",
        common_triggers=["Go-live handoff", "Implementation closeout", "Operational transition"],
        required_sections=["Delivered Scope", "Operational Notes", "Known Issues", "Support Model"],
    ),
    DocumentTypeDefinition(
        key="executive-summary",
        name="Executive Summary Brief",
        category="Business Reporting",
        type_code="EXE",
        subtype_code="101",
        description="Leadership-focused summary of initiative status, outcomes, blockers, and decisions required.",
        common_triggers=["Steering committee update", "Quarterly review", "Executive checkpoint"],
        required_sections=["Business Context", "Current Status", "Risks", "Decisions Needed", "Next Milestones"],
    ),
    DocumentTypeDefinition(
        key="kpi-status-report",
        name="KPI Status Report",
        category="Business Reporting",
        type_code="KPI",
        subtype_code="102",
        description="Tracks performance metrics against target with commentary on trends and corrective actions.",
        common_triggers=["Monthly dashboard", "SLA review", "Performance reporting"],
        required_sections=["KPI Snapshot", "Target vs Actual", "Variance Analysis", "Corrective Actions"],
    ),
    DocumentTypeDefinition(
        key="financial-impact-summary",
        name="Financial Impact Summary",
        category="Business Reporting",
        type_code="FIN",
        subtype_code="103",
        description="Summarizes spend, savings, budget variance, and forecast impact for IT initiatives.",
        common_triggers=["Budget review", "Cost optimization update", "Funding request support"],
        required_sections=["Cost Summary", "Budget Variance", "Business Impact", "Forecast"],
    ),
    DocumentTypeDefinition(
        key="risk-register-update",
        name="Risk Register Update",
        category="Business Reporting",
        type_code="RSK",
        subtype_code="104",
        description="Structured update of open risks, severity shifts, owners, due dates, and mitigation status.",
        common_triggers=["Governance review", "Audit prep", "Program risk checkpoint"],
        required_sections=["Risk Overview", "Changes Since Last Update", "Top Risks", "Mitigation Progress", "Escalations"],
    ),
    DocumentTypeDefinition(
        key="project-status-brief",
        name="Project Status Brief",
        category="Business Reporting",
        type_code="PSB",
        subtype_code="105",
        description="Concise stakeholder update covering scope, schedule, dependencies, and upcoming deliverables.",
        common_triggers=["Weekly project update", "Client status update", "PMO reporting"],
        required_sections=["Scope Status", "Schedule Status", "Dependencies", "Issues and Blockers", "Upcoming Deliverables"],
    ),
    DocumentTypeDefinition(
        key="vulnerability-assessment",
        name="Vulnerability Assessment Report",
        category="Cybersecurity",
        type_code="VUL",
        subtype_code="201",
        description="Summarizes vulnerability scanning results, severity distribution, and remediation priorities.",
        common_triggers=["Monthly vulnerability scan", "External attack surface review", "Patch cycle planning"],
        required_sections=["Assessment Scope", "Findings Summary", "Severity Breakdown", "Remediation Plan", "Target Dates"],
    ),
    DocumentTypeDefinition(
        key="penetration-test-report",
        name="Penetration Test Report",
        category="Cybersecurity",
        type_code="PEN",
        subtype_code="202",
        description="Formal report of penetration testing methodology, exploitable findings, and recommendations.",
        common_triggers=["Annual pentest", "Pre-go-live security validation", "Regulatory testing requirement"],
        required_sections=["Test Scope", "Methodology", "Exploitable Findings", "Risk Ratings", "Recommendations"],
    ),
    DocumentTypeDefinition(
        key="threat-hunt-report",
        name="Threat Hunt Report",
        category="Cybersecurity",
        type_code="THR",
        subtype_code="203",
        description="Captures hypotheses, telemetry analysis, indicators, and conclusions from proactive threat hunting.",
        common_triggers=["SOC hunt cycle", "Suspicious behavior trend", "New threat intel advisory"],
        required_sections=["Hunt Hypothesis", "Data Sources", "Findings", "Indicators Observed", "Follow-up Actions"],
    ),
    DocumentTypeDefinition(
        key="incident-response-report",
        name="Incident Response Report",
        category="Cybersecurity",
        type_code="IRR",
        subtype_code="204",
        description="Detailed incident response record including detection, containment, eradication, and recovery.",
        common_triggers=["Malware outbreak", "Account compromise", "Data exfiltration alert"],
        required_sections=["Incident Overview", "Timeline", "Containment Actions", "Root Cause", "Lessons Learned"],
    ),
    DocumentTypeDefinition(
        key="security-control-validation",
        name="Security Control Validation",
        category="Cybersecurity",
        type_code="SCV",
        subtype_code="205",
        description="Evidence-based validation that technical and procedural controls are operating effectively.",
        common_triggers=["Audit preparation", "Post-hardening verification", "Control owner review"],
        required_sections=["Control Scope", "Validation Method", "Test Evidence", "Results", "Exceptions"],
    ),
    DocumentTypeDefinition(
        key="third-party-security-review",
        name="Third-Party Security Review",
        category="Cybersecurity",
        type_code="TPS",
        subtype_code="206",
        description="Security assessment of a vendor or SaaS provider with risk disposition and contract requirements.",
        common_triggers=["New vendor onboarding", "Renewal risk review", "Procurement due diligence"],
        required_sections=["Vendor Profile", "Security Posture", "Risk Findings", "Compensating Controls", "Decision"],
    ),
    DocumentTypeDefinition(
        key="phishing-campaign-analysis",
        name="Phishing Campaign Analysis",
        category="Cybersecurity",
        type_code="PHI",
        subtype_code="207",
        description="Analysis of phishing attempts, user impact, indicators, and response effectiveness.",
        common_triggers=["Reported phishing spike", "Mailbox compromise investigation", "Awareness campaign review"],
        required_sections=["Campaign Summary", "Indicators", "Impacted Users", "Response Actions", "Prevention Improvements"],
    ),
]


def list_document_types() -> list[DocumentTypeDefinition]:
    return DOCUMENT_TYPES


def get_document_type(key: str) -> DocumentTypeDefinition:
    for definition in DOCUMENT_TYPES:
        if definition.key == key:
            return definition
    return DOCUMENT_TYPES[0]


def build_document_type_catalog() -> str:
    blocks: list[str] = []
    for item in DOCUMENT_TYPES:
        blocks.append(
            "\n".join(
                [
                    f"Key: {item.key}",
                    f"Name: {item.name}",
                    f"Category: {item.category}",
                    f"Tracking code prefix: {item.type_code}-{item.subtype_code}",
                    f"Description: {item.description}",
                    f"Common triggers: {', '.join(item.common_triggers)}",
                    f"Required sections: {', '.join(item.required_sections)}",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_tracking_code(document_type_key: str, document_date: date) -> str:
    definition = get_document_type(document_type_key)
    date_code = document_date.strftime("%y%m%d")
    return f"{definition.type_code}-{definition.subtype_code}-{date_code}"