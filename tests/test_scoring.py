"""
Unit tests for calculate_compliance_score().

No RAG, no LLM, no MongoDB -- pure function tests.
Each case constructs findings directly and asserts the exact score output.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from app.services.scoring import calculate_compliance_score


def _f(applicability: str, status: str) -> dict:
    """Minimal finding dict sufficient for scoring."""
    return {"applicability": applicability, "status": status}


def _run(label: str, findings: list[dict], expected_score, expected_display: str,
         expected_status: str, expected_scoreable: int) -> bool:
    result = calculate_compliance_score(findings)
    checks = [
        ("score",         result["score"],         expected_score),
        ("score_display", result["score_display"],  expected_display),
        ("status",        result["status"],         expected_status),
        ("total_scoreable", result["total_scoreable"], expected_scoreable),
    ]
    failures = [f"  {field}: got {got!r}, want {want!r}"
                for field, got, want in checks if got != want]
    if failures:
        print(f"  FAIL  {label}")
        for line in failures:
            print(line)
        return False
    print(f"  PASS  {label}  (score={result['score_display']}, "
          f"scoreable={result['total_scoreable']})")
    return True


def main():
    results = []

    # 1. Single currently_applicable + compliant → 100%
    results.append(_run(
        "TC1  1x compliant",
        [_f("currently_applicable", "compliant")],
        expected_score=100.0, expected_display="100.0%",
        expected_status="assessed", expected_scoreable=1,
    ))

    # 2. Single currently_applicable + partially_compliant → 50%
    results.append(_run(
        "TC2  1x partially_compliant",
        [_f("currently_applicable", "partially_compliant")],
        expected_score=50.0, expected_display="50.0%",
        expected_status="assessed", expected_scoreable=1,
    ))

    # 3. Single currently_applicable + non_compliant → 0%
    results.append(_run(
        "TC3  1x non_compliant",
        [_f("currently_applicable", "non_compliant")],
        expected_score=0.0, expected_display="0.0%",
        expected_status="assessed", expected_scoreable=1,
    ))

    # 4. 2x compliant + 1x partially_compliant + 1x non_compliant
    #    weighted = (2*100 + 1*50 + 1*0) / 4 = 250/4 = 62.5
    results.append(_run(
        "TC4  2xC + 1xPC + 1xNC = 62.5%",
        [
            _f("currently_applicable", "compliant"),
            _f("currently_applicable", "compliant"),
            _f("currently_applicable", "partially_compliant"),
            _f("currently_applicable", "non_compliant"),
        ],
        expected_score=62.5, expected_display="62.5%",
        expected_status="assessed", expected_scoreable=4,
    ))

    # 5. Mixed: only the currently_applicable+compliant finding scores
    #    - currently_applicable + compliant          → scores (100)
    #    - currently_applicable + insufficient_evidence → excluded
    #    - future_requirement   + non_compliant      → excluded
    #    - not_applicable       + non_compliant      → excluded
    #    Result: 1 scoreable, score = 100%
    results.append(_run(
        "TC5  mixed applicability - only 1 scoreable",
        [
            _f("currently_applicable", "compliant"),
            _f("currently_applicable", "insufficient_evidence"),
            _f("future_requirement",   "non_compliant"),
            _f("not_applicable",       "non_compliant"),
        ],
        expected_score=100.0, expected_display="100.0%",
        expected_status="assessed", expected_scoreable=1,
    ))

    # 6. Only future_requirement findings → N/A
    results.append(_run(
        "TC6  all future_requirement → N/A",
        [
            _f("future_requirement", "insufficient_evidence"),
            _f("future_requirement", "insufficient_evidence"),
        ],
        expected_score=None, expected_display="N/A",
        expected_status="not_assessable", expected_scoreable=0,
    ))

    # 7. Only not_applicable findings → N/A
    results.append(_run(
        "TC7  all not_applicable → N/A",
        [
            _f("not_applicable", "not_applicable"),
            _f("not_applicable", "not_applicable"),
        ],
        expected_score=None, expected_display="N/A",
        expected_status="not_assessable", expected_scoreable=0,
    ))

    # 8. currently_applicable but all insufficient_evidence → N/A
    results.append(_run(
        "TC8  currently_applicable + all insufficient_evidence → N/A",
        [
            _f("currently_applicable", "insufficient_evidence"),
            _f("currently_applicable", "insufficient_evidence"),
        ],
        expected_score=None, expected_display="N/A",
        expected_status="not_assessable", expected_scoreable=0,
    ))

    # -------------------------------------------------------------------------
    # Simulation mode scoring tests (TC-S1 through TC-S5)
    # Pure unit tests: verify scoring rules are invariant to how applicability
    # was determined (real date vs simulated date). scoring.py only sees the
    # final applicability/status values it receives.
    # -------------------------------------------------------------------------

    # TC-S1: assessment date before 13 May 2027
    # Substantive DPDP obligations remain future_requirement -> score N/A
    results.append(_run(
        "TC-S1 sim date < 13 May 2027: all future_requirement -> N/A",
        [
            _f("future_requirement", "insufficient_evidence"),
            _f("future_requirement", "insufficient_evidence"),
            _f("not_applicable",     "not_applicable"),
        ],
        expected_score=None, expected_display="N/A",
        expected_status="not_assessable", expected_scoreable=0,
    ))

    # TC-S2: assessment date after 13 May 2027
    # Substantive obligations become currently_applicable and can score
    # (2*100 + 1*50) / 3 would be wrong -- not_applicable is excluded
    # (1*100 + 1*50) / 2 = 75.0
    results.append(_run(
        "TC-S2 sim date > 13 May 2027: currently_applicable findings score",
        [
            _f("currently_applicable", "compliant"),
            _f("currently_applicable", "partially_compliant"),
            _f("not_applicable",       "not_applicable"),
        ],
        expected_score=75.0, expected_display="75.0%",
        expected_status="assessed", expected_scoreable=2,
    ))

    # TC-S3: future requirements excluded even when mixed with current ones
    results.append(_run(
        "TC-S3 future_requirement excluded when mixed with currently_applicable",
        [
            _f("currently_applicable", "compliant"),
            _f("future_requirement",   "insufficient_evidence"),
            _f("future_requirement",   "insufficient_evidence"),
        ],
        expected_score=100.0, expected_display="100.0%",
        expected_status="assessed", expected_scoreable=1,
    ))

    # TC-S4: not_applicable findings never contribute regardless of status
    results.append(_run(
        "TC-S4 not_applicable findings never contribute to score",
        [
            _f("currently_applicable", "compliant"),
            _f("not_applicable",       "not_applicable"),
            _f("not_applicable",       "not_applicable"),
        ],
        expected_score=100.0, expected_display="100.0%",
        expected_status="assessed", expected_scoreable=1,
    ))

    # TC-S5: insufficient_evidence never contributes regardless of applicability
    results.append(_run(
        "TC-S5 insufficient_evidence never contributes to score",
        [
            _f("currently_applicable", "compliant"),
            _f("currently_applicable", "insufficient_evidence"),
            _f("future_requirement",   "insufficient_evidence"),
        ],
        expected_score=100.0, expected_display="100.0%",
        expected_status="assessed", expected_scoreable=1,
    ))

    print()
    passed = sum(results)
    total  = len(results)
    if passed == total:
        print(f"ALL {total} TESTS PASSED")
    else:
        print(f"{passed}/{total} PASSED -- {total - passed} FAILED")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
