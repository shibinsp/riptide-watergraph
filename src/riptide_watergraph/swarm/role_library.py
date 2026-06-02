"""A large catalog of domain-specialist agent roles.

Each role is an :class:`AgentRole` with a focused prompt, a `category` group, a short
`description`, and a tool **allow-list** composed from the registered tool categories (so a
role only ever sees relevant tools via on-demand retrieval). Roles are data-driven: add a row
to ``_ROLE_DATA`` to add a specialist. The curated core (``DEFAULT_ROLES``) is merged in and
takes precedence; ``role_for`` keyword-routing covers the highest-traffic roles, while the
rest are selectable in the Studio or via the composer's ``decision.roles``.
"""

from __future__ import annotations

from ..tools import default_registry
from .roles import DEFAULT_ROLES, AgentRole

# Tool names available per category, snapshotted once from the default registry.
_BY_CATEGORY: dict[str, list[str]] = {}
for _spec in default_registry().all_specs():
    _BY_CATEGORY.setdefault(_spec.category, []).append(_spec.name)


def _tools(*categories: str) -> list[str] | None:
    """Allow-list = all tool names in the given categories (None => all tools)."""
    if not categories:
        return None
    names: list[str] = []
    for cat in categories:
        names.extend(_BY_CATEGORY.get(cat, []))
    return sorted(dict.fromkeys(names)) or None


# Default tool categories per role group.
_GROUP_CATS: dict[str, tuple[str, ...]] = {
    "engineering": ("code", "text", "regex", "data"),
    "data": ("data", "math", "code"),
    "devops": ("code", "encoding", "collections"),
    "security": ("hashing", "encoding", "extract", "code"),
    "qa": ("code", "text", "data"),
    "product": ("text", "data", "collections"),
    "writing": ("text", "extract"),
    "research": ("extract", "text", "web"),
    "finance": ("math", "data", "units"),
    "ops": ("code", "collections", "datetime"),
    "design": ("color", "units", "text"),
    "general": (),
}

# (name, group, title, blurb)
_ROLE_DATA: list[tuple[str, str, str, str]] = [
    # engineering
    ("backend_engineer", "engineering", "backend engineer", "design and implement server-side services and APIs"),
    ("frontend_engineer", "engineering", "frontend engineer", "build user-facing UI and client logic"),
    ("fullstack_engineer", "engineering", "full-stack engineer", "work across frontend and backend layers"),
    ("mobile_engineer", "engineering", "mobile engineer", "build native/cross-platform mobile apps"),
    ("api_designer", "engineering", "API designer", "design clean, consistent, versioned APIs"),
    ("code_reviewer", "engineering", "code reviewer", "review diffs for correctness, security, and style"),
    ("refactoring_specialist", "engineering", "refactoring specialist", "restructure code without changing behavior"),
    ("debugger", "engineering", "debugging specialist", "reproduce, isolate, and fix defects"),
    ("performance_engineer", "engineering", "performance engineer", "profile and optimize hot paths"),
    ("build_engineer", "engineering", "build engineer", "own build systems, packaging, and toolchains"),
    ("integration_engineer", "engineering", "integration engineer", "wire systems and third-party services together"),
    ("embedded_engineer", "engineering", "embedded engineer", "write constrained, low-level device code"),
    ("game_developer", "engineering", "game developer", "build game logic and real-time loops"),
    ("cli_developer", "engineering", "CLI developer", "build ergonomic command-line tools"),
    ("library_author", "engineering", "library author", "design reusable, well-documented libraries"),
    ("algorithms_expert", "engineering", "algorithms expert", "design and analyze algorithms and data structures"),
    ("concurrency_expert", "engineering", "concurrency expert", "reason about parallelism and race conditions"),
    ("accessibility_engineer", "engineering", "accessibility engineer", "make software usable for everyone"),
    # data
    ("data_analyst", "data", "data analyst", "explore data and summarize findings"),
    ("data_engineer", "data", "data engineer", "build pipelines and data infrastructure"),
    ("data_scientist", "data", "data scientist", "model data and test hypotheses"),
    ("ml_engineer", "data", "ML engineer", "ship and serve machine-learning models"),
    ("ml_researcher", "data", "ML researcher", "investigate novel modeling approaches"),
    ("statistician", "data", "statistician", "apply rigorous statistical methods"),
    ("sql_developer", "data", "SQL developer", "write and optimize SQL queries"),
    ("etl_developer", "data", "ETL developer", "extract, transform, and load data"),
    ("bi_analyst", "data", "BI analyst", "build dashboards and business reports"),
    ("data_viz_specialist", "data", "data-visualization specialist", "turn data into clear visuals"),
    ("nlp_engineer", "data", "NLP engineer", "process and model natural language"),
    ("cv_engineer", "data", "computer-vision engineer", "process and model images"),
    ("mlops_engineer", "data", "MLOps engineer", "operationalize ML lifecycles"),
    ("analytics_engineer", "data", "analytics engineer", "model trusted analytics datasets"),
    # devops / SRE
    ("devops_engineer", "devops", "DevOps engineer", "automate build, deploy, and operations"),
    ("sre", "devops", "site reliability engineer", "keep systems reliable and observable"),
    ("platform_engineer", "devops", "platform engineer", "build internal developer platforms"),
    ("cloud_architect", "devops", "cloud architect", "design scalable cloud infrastructure"),
    ("kubernetes_admin", "devops", "Kubernetes administrator", "operate container orchestration"),
    ("cicd_engineer", "devops", "CI/CD engineer", "build continuous delivery pipelines"),
    ("release_manager", "devops", "release manager", "coordinate safe, repeatable releases"),
    ("infrastructure_engineer", "devops", "infrastructure engineer", "provision and manage infrastructure"),
    ("network_engineer", "devops", "network engineer", "design and troubleshoot networks"),
    ("observability_engineer", "devops", "observability engineer", "instrument metrics, logs, and traces"),
    ("incident_responder", "devops", "incident responder", "triage and resolve production incidents"),
    ("capacity_planner", "devops", "capacity planner", "forecast and plan resource capacity"),
    # security
    ("security_analyst", "security", "security analyst", "assess and improve security posture"),
    ("penetration_tester", "security", "penetration tester", "find exploitable vulnerabilities"),
    ("appsec_engineer", "security", "application-security engineer", "secure the software supply chain"),
    ("security_auditor", "security", "security auditor", "audit systems against controls"),
    ("cryptographer", "security", "cryptographer", "apply and review cryptographic schemes"),
    ("compliance_officer", "security", "compliance officer", "ensure regulatory compliance"),
    ("threat_modeler", "security", "threat modeler", "enumerate threats and mitigations"),
    ("forensics_analyst", "security", "forensics analyst", "investigate breaches and artifacts"),
    ("iam_specialist", "security", "IAM specialist", "design identity and access controls"),
    ("vuln_researcher", "security", "vulnerability researcher", "discover and report new flaws"),
    # qa
    ("qa_engineer", "qa", "QA engineer", "verify quality across features"),
    ("test_automation_engineer", "qa", "test-automation engineer", "build automated test suites"),
    ("manual_tester", "qa", "manual tester", "execute exploratory and manual tests"),
    ("performance_tester", "qa", "performance tester", "load- and stress-test systems"),
    ("qa_lead", "qa", "QA lead", "plan and prioritize quality strategy"),
    ("accessibility_tester", "qa", "accessibility tester", "validate accessibility compliance"),
    ("regression_analyst", "qa", "regression analyst", "guard against reintroduced defects"),
    ("test_designer", "qa", "test designer", "design thorough test cases"),
    # product
    ("product_manager", "product", "product manager", "define what to build and why"),
    ("project_manager", "product", "project manager", "plan and track delivery"),
    ("scrum_master", "product", "scrum master", "facilitate agile delivery"),
    ("business_analyst", "product", "business analyst", "translate needs into requirements"),
    ("ux_researcher", "product", "UX researcher", "study users and synthesize insights"),
    ("product_designer", "product", "product designer", "design product flows and screens"),
    ("ux_writer", "product", "UX writer", "craft clear in-product copy"),
    ("roadmap_planner", "product", "roadmap planner", "sequence initiatives over time"),
    ("stakeholder_liaison", "product", "stakeholder liaison", "align stakeholders and expectations"),
    ("requirements_analyst", "product", "requirements analyst", "elicit and document requirements"),
    # writing
    ("technical_writer", "writing", "technical writer", "write clear technical documentation"),
    ("copywriter", "writing", "copywriter", "write persuasive marketing copy"),
    ("editor", "writing", "editor", "improve clarity, flow, and correctness"),
    ("documentation_specialist", "writing", "documentation specialist", "structure and maintain docs"),
    ("api_docs_writer", "writing", "API documentation writer", "document endpoints and usage"),
    ("blogger", "writing", "blog writer", "write engaging long-form posts"),
    ("content_strategist", "writing", "content strategist", "plan content for an audience"),
    ("proofreader", "writing", "proofreader", "catch grammar and spelling errors"),
    ("translator", "writing", "translator", "translate text between languages"),
    ("summarizer", "writing", "summarizer", "condense text to its essence"),
    ("release_notes_writer", "writing", "release-notes writer", "summarize changes for users"),
    ("knowledge_manager", "writing", "knowledge manager", "curate institutional knowledge"),
    # research
    ("market_researcher", "research", "market researcher", "analyze markets and demand"),
    ("literature_reviewer", "research", "literature reviewer", "survey and synthesize prior work"),
    ("fact_checker", "research", "fact checker", "verify claims against sources"),
    ("competitive_analyst", "research", "competitive analyst", "analyze competitors and positioning"),
    ("academic_researcher", "research", "academic researcher", "investigate questions rigorously"),
    ("patent_analyst", "research", "patent analyst", "analyze patents and prior art"),
    ("trend_analyst", "research", "trend analyst", "identify emerging trends"),
    # finance / analysis
    ("financial_analyst", "finance", "financial analyst", "analyze financial performance"),
    ("accountant", "finance", "accountant", "track and reconcile finances"),
    ("budget_analyst", "finance", "budget analyst", "plan and monitor budgets"),
    ("risk_analyst", "finance", "risk analyst", "quantify and mitigate risk"),
    ("investment_analyst", "finance", "investment analyst", "evaluate investment options"),
    ("pricing_analyst", "finance", "pricing analyst", "optimize pricing strategy"),
    ("forecaster", "finance", "forecaster", "project future values from data"),
    ("auditor", "finance", "auditor", "examine records for accuracy"),
    ("quant_analyst", "finance", "quantitative analyst", "build quantitative models"),
    # ops / support
    ("customer_support", "ops", "customer support specialist", "resolve customer issues"),
    ("ops_analyst", "ops", "operations analyst", "analyze and improve operations"),
    ("sysadmin", "ops", "system administrator", "operate and maintain systems"),
    ("database_administrator", "ops", "database administrator", "operate and tune databases"),
    ("support_engineer", "ops", "support engineer", "debug customer-facing problems"),
    ("onboarding_specialist", "ops", "onboarding specialist", "guide new users and hires"),
    ("triage_specialist", "ops", "triage specialist", "classify and route incoming work"),
    ("escalation_manager", "ops", "escalation manager", "drive urgent issues to resolution"),
    ("workflow_automator", "ops", "workflow automator", "automate repetitive processes"),
    # design
    ("ui_designer", "design", "UI designer", "design polished interfaces"),
    ("graphic_designer", "design", "graphic designer", "create visual assets"),
    ("brand_designer", "design", "brand designer", "shape brand identity"),
    ("interaction_designer", "design", "interaction designer", "design how users interact"),
    ("design_systems_lead", "design", "design-systems lead", "own components and tokens"),
    # general
    ("planner", "general", "planner", "break goals into a concrete plan"),
    ("coordinator", "general", "coordinator", "sequence and delegate subtasks"),
    ("assistant", "general", "assistant", "help with general tasks pragmatically"),
]


def _build() -> dict[str, AgentRole]:
    catalog: dict[str, AgentRole] = {}
    for name, group, title, blurb in _ROLE_DATA:
        if name in DEFAULT_ROLES:  # curated core takes precedence
            continue
        catalog[name] = AgentRole(
            name=name,
            system_prompt=(
                f"You are a worker acting as a {title}. Your job: {blurb}. Use the most "
                "specific available tool when helpful; otherwise answer directly and concisely."
            ),
            tools=_tools(*_GROUP_CATS.get(group, ())),
            category=group,
            description=blurb,
            tags=[group],
        )
    return catalog


# Curated core first, then the catalog (core names win).
ROLE_CATALOG: dict[str, AgentRole] = {**_build(), **DEFAULT_ROLES}
