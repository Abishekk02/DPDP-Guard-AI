from typing import Any


def calculate_compliance_score(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Calculate compliance score using only findings that are:
      - currently_applicable
      - not insufficient_evidence
      - not not_applicable

    Scoring:
      compliant           = 100
      partially_compliant = 50
      non_compliant       = 0

    Future requirements, not-applicable findings, and insufficient
    evidence do not affect the score.
    """

    eligible_findings = []

    for finding in findings:
        applicability = finding.get("applicability")
        status = finding.get("status")

        # Only currently applicable requirements can affect score
        if applicability != "currently_applicable":
            continue

        # Cannot score something when evidence is insufficient
        if status in {"insufficient_evidence", "not_applicable"}:
            continue

        # Only these statuses have a defined score
        if status not in {
            "compliant",
            "partially_compliant",
            "non_compliant",
        }:
            continue

        eligible_findings.append(finding)

    # No scoreable requirements
    if not eligible_findings:
        return {
            "score": None,
            "score_display": "N/A",
            "status": "not_assessable",
            "message": (
                "No currently applicable requirements have "
                "sufficient evidence for scoring."
            ),
            "total_scoreable": 0,
            "compliant": 0,
            "partially_compliant": 0,
            "non_compliant": 0,
            "insufficient_evidence": sum(
                1
                for f in findings
                if f.get("status") == "insufficient_evidence"
            ),
        }

    compliant = sum(
        1
        for f in eligible_findings
        if f.get("status") == "compliant"
    )

    partially_compliant = sum(
        1
        for f in eligible_findings
        if f.get("status") == "partially_compliant"
    )

    non_compliant = sum(
        1
        for f in eligible_findings
        if f.get("status") == "non_compliant"
    )

    total_scoreable = len(eligible_findings)

    weighted_score = (
        (compliant * 100)
        + (partially_compliant * 50)
        + (non_compliant * 0)
    )

    score = round(weighted_score / total_scoreable, 2)

    return {
        "score": score,
        "score_display": f"{score}%",
        "status": "assessed",
        "message": "Compliance score calculated from currently applicable requirements.",
        "total_scoreable": total_scoreable,
        "compliant": compliant,
        "partially_compliant": partially_compliant,
        "non_compliant": non_compliant,
        "insufficient_evidence": sum(
            1
            for f in findings
            if f.get("status") == "insufficient_evidence"
        ),
    }