import json
from datetime import date, datetime
from app.services.rag import search_documents
from app.services.llm_service import call_llm
from app.services.scoring import calculate_compliance_score

VALID_STATUSES = {
    "compliant", "partially_compliant", "non_compliant",
    "insufficient_evidence", "not_applicable",
}
VALID_APPLICABILITY = {
    "currently_applicable", "future_requirement",
    "not_applicable", "applicability_unknown",
}
VALID_SUFFICIENCY = {"sufficient", "insufficient"}

# After RAG retrieval, send only the top N chunks to Gemini to avoid timeouts.
# RAG retrieval itself is unchanged — this only limits what is sent to the LLM.
MAX_LLM_LEGAL_CHUNKS = 12

# ---------------------------------------------------------------------------
# Commencement schedules — kept strictly separate for Act and Rules
# ---------------------------------------------------------------------------
#
# DPDP Rules 2025 (S.O. 1009(E)) — published 13 November 2025
#   Immediately:          Rules 1, 2, 17, 18, 19, 20, 21
#   +1 year  (13 Nov 2026): Rule 4
#   +18 months (13 May 2027): Rules 3, 5-16, 22, 23
#
# DPDP Act 2023 (G.S.R. 843(E)) — notified 13 November 2025
#   Immediately:          s.1(2), s.2, ss.18-26, s.35, ss.38-43, s.44(1), s.44(3)
#   +1 year  (13 Nov 2026): s.6(9), s.27(1)(d)
#   +18 months (13 May 2027): ss.3-5, ss.6(1)-6(8), s.6(10), ss.7-17,
#                              s.27 (except 27(1)(d)), ss.28-34, ss.36-37, s.44(2)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Commencement schedule — fixed legal dates, never modified.
# The assessment date (real or simulated) is injected per-call in
# _build_system_prompt(), not here.
# ---------------------------------------------------------------------------
_COMMENCEMENT_SCHEDULE_TEMPLATE = """
=== DPDP Rules 2025 — Commencement Schedule (S.O. 1009(E), published 13 November 2025) ===
Fixed commencement dates (these never change):
  Rules 1, 2, 17, 18, 19, 20, 21  — in force from 13 November 2025
  Rule 4                           — in force from 13 November 2026
  Rules 3, 5-16, 22, 23           — in force from 13 May 2027

IMPORTANT: Rules 6, 8, 9, 10 are DPDP Rules 2025 provisions.
Their commencement date is 13 May 2027 per the Rules' own schedule.
Do NOT assign the Act's commencement dates to Rules provisions.

=== DPDP Act 2023 — Commencement Schedule (G.S.R. 843(E), notified 13 November 2025) ===
Fixed commencement dates (these never change):
  s.1(2), s.2, ss.18-26, s.35, ss.38-43, s.44(1), s.44(3) — in force from 13 November 2025
  s.6(9), s.27(1)(d)                                        — in force from 13 November 2026
  ss.3-5, ss.6(1)-6(8), s.6(10), ss.7-17,
  s.27 (except 27(1)(d)), ss.28-34, ss.36-37, s.44(2)      — in force from 13 May 2027

=== TODAY'S ASSESSMENT DATE: {assessment_date} ===

Using the assessment date above, classify each provision as follows:

Step 1 — Who does the obligation apply to?
  If the obligation applies to the Central Government, Data Protection Board,
  or any authority OTHER than a Data Fiduciary / website operator:
    → applicability: not_applicable  (regardless of assessment date)
    → status: not_applicable
    → counts_toward_score: false

  Examples of not_applicable obligations:
    • s.1(2) of the Act: Short title and commencement — administrative enactment
      provision only; imposes no obligation on a Data Fiduciary or website operator.
    • s.2 of the Act: Definitions only — no actionable obligation on a Data Fiduciary.
    • s.35 of the Act: Central Government power to issue directions — not a Data
      Fiduciary obligation.
    • ss.38-43 of the Act: Miscellaneous/savings provisions — not Data Fiduciary
      obligations.
    • s.44(1), s.44(3) of the Act: Repeal and savings — administrative provisions only.
    • Rules 1, 2 of the Rules: Short title, commencement, and definitions — no
      actionable obligation on a Data Fiduciary.
    • Rule 17: Central Government constituting a Search-cum-Selection Committee
    • Rules 18-21: Appointment/removal of Board Chairperson and members
    • Sections 18-26 of the Act: Powers and procedures of the Data Protection Board
    • Data Principal duties (not Data Fiduciary obligations)

  CRITICAL: A provision is only currently_applicable if it BOTH (a) has commenced
  AND (b) imposes a specific, actionable obligation on the assessed Data Fiduciary
  (website operator). Commencement alone does not make a provision scoreable.
  Administrative, definitional, enactment, and government-power provisions are
  ALWAYS not_applicable regardless of their commencement date.

Step 2 — If the obligation applies to a Data Fiduciary, compare its commencement
  date to the assessment date above:
  • If commencement date <= assessment date  → currently_applicable
  • If commencement date >  assessment date  → future_requirement
  • If rule/section number cannot be determined → applicability_unknown

Step 3 — Status enforcement:
  • NEVER mark a future_requirement as non_compliant → use insufficient_evidence
  • NEVER mark a not_applicable finding with any status other than not_applicable
  • not_applicable findings MUST NOT count toward the compliance score
"""

_SYSTEM_PROMPT_TEMPLATE = """You are a legal compliance analyst specializing in India's Digital Personal Data Protection (DPDP) Act 2023 and DPDP Rules 2025.

You will be given:
1. Retrieved legal requirements from official DPDP source documents (with page references)
2. Evidence collected by a web crawler from a real website

{commencement_schedule}

Evidence inference rules — strictly follow these:
- Registration or payment forms do NOT prove that children are using the service.
- A generic support email does NOT prove compliance with contact-information requirements.
- TLS/payment encryption does NOT prove all security safeguards under Rule 6 are implemented.
- Privacy policy mentioning retention does NOT prove compliance with specific retention schedules.
- Do NOT infer facts not explicitly present in the crawler evidence.
- If a necessary fact is absent from crawler evidence → status: insufficient_evidence, NOT non_compliant.

Produce one finding per distinct legal obligation in the retrieved source text.

Return a JSON object in this exact format:
{{
    "findings": [
        {{
            "requirement": "<specific legal obligation quoted or closely paraphrased from source text>",
            "applicability": "<currently_applicable | future_requirement | not_applicable | applicability_unknown>",
            "status": "<compliant | partially_compliant | non_compliant | insufficient_evidence | not_applicable>",
            "counts_toward_score": <true | false>,
            "evidence_sufficiency": "<sufficient | insufficient>",
            "evidence": "<exact crawler evidence — quote from crawler data, or 'none' if not_applicable>",
            "source": "<source filename>",
            "page": <page number as integer>,
            "explanation": "<how evidence satisfies/fails the requirement, or why not_applicable>",
            "recommendation": "<specific action for the website, or 'No action required' if not_applicable>"
        }}
    ]
}}"""


def _build_system_prompt(assessment_date: date) -> str:
    schedule = _COMMENCEMENT_SCHEDULE_TEMPLATE.format(
        assessment_date=assessment_date.strftime("%d %B %Y")
    )
    return _SYSTEM_PROMPT_TEMPLATE.format(commencement_schedule=schedule)


def _build_rag_queries(category: str, crawler_data: dict) -> list[str]:
    base_queries = [
    "Data Fiduciary obligations under DPDP Act 2023 currently applicable",
    "DPDP Act 2023 provisions in force 13 November 2025 Data Fiduciary",
    "DPDP Rules 2025 provisions currently in force Data Fiduciary",
    "Data Fiduciary notice personal data collection",
    "Data Fiduciary reasonable security safeguards personal data",
    "personal data breach Data Fiduciary notification",
    "Data Fiduciary contact information grievance redressal",
    "DPDP Rules 2025 commencement provisions currently in force",
    # Queries that match the actual text on the commencement page (p.24 of Rules)
    "Digital Personal Data Protection Rules 2025 short title commencement Rule 1 Rule 2",
    "Rules 1 2 17 18 19 20 21 come into force date of publication Official Gazette",
    "Rule 2 definitions Act techno-legal measures user account verifiable consent",
    "contact information Data Protection Officer Data Fiduciary website Rule 9",
]

    category_queries = {
        "ecommerce":    ["processing personal data purchase transactions delivery",
                         "sharing personal data third party delivery partners processors"],
        "finance":      ["processing sensitive financial personal data",
                         "significant Data Fiduciary obligations"],
        "healthcare":   ["processing health medical personal data",
                         "significant Data Fiduciary children data parental consent"],
        "education":    ["processing children personal data verifiable parental consent",
                         "significant Data Fiduciary obligations"],
        "government":   ["government entity exemptions processing personal data",
                         "public interest processing personal data"],
        "social_media": ["significant Data Fiduciary social media two crore users",
                         "children personal data parental consent social media"],
        "insurance":    ["processing sensitive personal data insurance",
                         "significant Data Fiduciary obligations"],
    }

    queries = base_queries + category_queries.get(category, [])

    if crawler_data.get("cookies"):
        queries.append("consent mechanism cookies tracking personal data withdrawal")
    if crawler_data.get("forms"):
        queries.append("purpose limitation personal data collection forms specified")
    if crawler_data.get("personal_data_collected"):
        queries.append("security safeguards reasonable protect personal data breach")

    return queries


def _deduplicate_chunks(chunks: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for chunk in chunks:
        # Deduplicate by text prefix — prevents true duplicates while preserving
        # multiple distinct chunks from the same page (e.g. pages 27, 28, 30).
        key = chunk["text"][:120]
        if key not in seen:
            seen.add(key)
            unique.append(chunk)
    return unique


def _select_top_chunks(chunks: list[dict], limit: int) -> list[dict]:
    """Select the top-scoring chunks to send to the LLM.
    RAG retrieval is unchanged — this only limits what is forwarded to Gemini."""
    sorted_chunks = sorted(chunks, key=lambda c: c.get("score", 0.0), reverse=True)
    return sorted_chunks[:limit]


def _format_legal_context(chunks: list[dict]) -> str:
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        parts.append(
            f"[{i}] Source: {chunk['source']}, Page {chunk['page']}\n{chunk['text']}"
        )
    return "\n\n".join(parts)


def _counts_toward_score(applicability: str, status: str) -> bool:
    if applicability != "currently_applicable":
        return False
    if status in ("not_applicable", "insufficient_evidence"):
        return False
    return True


def _validate_finding(finding: dict) -> dict:
    applicability = finding.get("applicability", "applicability_unknown")
    if applicability not in VALID_APPLICABILITY:
        applicability = "applicability_unknown"

    status = finding.get("status", "insufficient_evidence")
    if status not in VALID_STATUSES:
        status = "insufficient_evidence"

    # Hard enforcement — LLM output cannot override these rules
    if applicability == "not_applicable":
        status = "not_applicable"
    elif applicability == "future_requirement" and status == "non_compliant":
        status = "insufficient_evidence"

    sufficiency = finding.get("evidence_sufficiency", "insufficient")
    if sufficiency not in VALID_SUFFICIENCY:
        sufficiency = "insufficient"

    return {
        "requirement":          finding.get("requirement", ""),
        "applicability":        applicability,
        "status":               status,
        "counts_toward_score":  _counts_toward_score(applicability, status),
        "evidence_sufficiency": sufficiency,
        "evidence":             finding.get("evidence", ""),
        "source":               finding.get("source", ""),
        "page":                 int(finding.get("page", 0)),
        "explanation":          finding.get("explanation", ""),
        "recommendation":       finding.get("recommendation", ""),
    }


def _ensure_current_rules_finding(
    findings: list[dict],
    chunks: list[dict]
) -> list[dict]:
    """Placeholder — no artificial findings are injected."""
    return findings


def _parse_assessment_date(assessment_date: str | None) -> tuple[date, bool]:
    """Return (date_to_use, is_simulated). None → real mode using today."""
    if assessment_date is None:
        return date.today(), False
    return datetime.strptime(assessment_date, "%Y-%m-%d").date(), True


async def analyze_compliance(
    crawler_data: dict,
    category: str,
    assessment_date: str | None = None,
) -> dict:
    assessed_on, simulation_mode = _parse_assessment_date(assessment_date)
    system_prompt = _build_system_prompt(assessed_on)

    # --- RAG retrieval (unchanged) ---
    queries = _build_rag_queries(category, crawler_data)
    raw_chunks = []
    for query in queries:
        raw_chunks.extend(search_documents(query, top_k=3))

    all_chunks = _deduplicate_chunks(raw_chunks)

    # --- Select top chunks for LLM (does not affect retrieval) ---
    llm_chunks = _select_top_chunks(all_chunks, MAX_LLM_LEGAL_CHUNKS)
    legal_context = _format_legal_context(llm_chunks)

    evidence_summary = {
        "url":                     crawler_data.get("url", ""),
        "title":                   crawler_data.get("title", ""),
        "forms":                   crawler_data.get("forms", []),
        "personal_data_collected": crawler_data.get("personal_data_collected", []),
        "cookies":                 crawler_data.get("cookies", []),
        "consent_mechanisms":      crawler_data.get("consent_mechanisms", []),
        "privacy_policy":          str(crawler_data.get("privacy_policy",
                                       crawler_data.get("privacy_policy_text", "")))[:2000],
        "page_text":               str(crawler_data.get("page_text",
                                       crawler_data.get("page_content", "")))[:2000],
    }

    user_prompt = (
        f"Website category: {category}\n\n"
        f"=== RETRIEVED LEGAL REQUIREMENTS (DPDP Act 2023 & Rules 2025) ===\n{legal_context}\n\n"
        f"=== CRAWLER EVIDENCE ===\n{json.dumps(evidence_summary, indent=2)}"
    )

    result = await call_llm(system_prompt, user_prompt)
    findings = [_validate_finding(f) for f in result.get("findings", [])]
    findings = _ensure_current_rules_finding(findings, all_chunks)
    score_result = calculate_compliance_score(findings)

    return {
        "category":           category,
        "assessment_date":    assessed_on.isoformat(),
        "simulation_mode":    simulation_mode,
        "chunks_retrieved":   len(all_chunks),
        "chunks_sent_to_llm": len(llm_chunks),
        "findings":           findings,
        "score":              score_result,
    }
