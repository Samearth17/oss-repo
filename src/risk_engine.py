"""Explainable security, maturity and supply-chain assurance model for OSS WATCH.

This module deliberately separates *risk* from *quality*. A popular, mature
repository can still be risky when it has vulnerable dependencies or weak
provenance. Missing evidence lowers confidence; it does not get treated as
proof of safety.
"""
from __future__ import annotations

from datetime import datetime, timezone
from math import exp


# Weights sum to 1.0. These are deliberately explicit so the model can be
# audited, tuned, and replaced with calibrated weights later.
RISK_WEIGHTS = {
    "vulnerability_exposure": 0.30,
    "dependency_freshness": 0.15,
    "maintenance_risk": 0.15,
    "provenance_weakness": 0.15,
    "security_control_weakness": 0.15,
    "dependency_complexity": 0.10,
}

MATURITY_WEIGHTS = {
    "maintenance": 0.25,
    "community": 0.15,
    "documentation": 0.15,
    "release_discipline": 0.15,
    "testing_ci": 0.15,
    "project_maturity": 0.15,
}

ASSURANCE_WEIGHTS = {
    "provenance": 0.25,
    "dependency_transparency": 0.20,
    "security_policy": 0.15,
    "ci_security": 0.15,
    "release_integrity": 0.15,
    "license": 0.10,
}


def _clamp01(value):
    return max(0.0, min(1.0, float(value)))


def _clamp100(value):
    return round(max(0.0, min(100.0, float(value))), 1)


def _number(repo, key, default=0.0):
    try:
        return float(repo.get(key, default) or default)
    except (TypeError, ValueError):
        return float(default)


def _dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def days_since(value):
    parsed = _dt(value)
    if not parsed:
        return None
    return max(0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days)


def _recency_risk(days):
    if days is None:
        return 0.50
    if days <= 30:
        return 0.05
    if days <= 90:
        return 0.15
    if days <= 180:
        return 0.30
    if days <= 365:
        return 0.55
    if days <= 730:
        return 0.80
    return 1.0


def _recency_quality(days):
    return 1.0 - _recency_risk(days)


def _presence(repo, key):
    value = repo.get(key)
    if isinstance(value, bool):
        return value
    return bool(value)


def _vulnerability_exposure(repo):
    """Use supplied vulnerability evidence only; absence of a scan is unknown."""
    vulns = repo.get("vulnerabilities") or repo.get("vulnerability_summary") or {}
    if isinstance(vulns, int):
        count = max(0, vulns)
        critical = min(count, int(_number(repo, "critical_vulnerabilities", 0)))
        high = min(max(count - critical, 0), int(_number(repo, "high_vulnerabilities", 0)))
        return _clamp01(0.80 * min(1.0, critical / 3) + 0.20 * min(1.0, high / 5))
    if not isinstance(vulns, dict):
        return 0.0
    critical = _number(vulns, "critical")
    high = _number(vulns, "high")
    moderate = _number(vulns, "moderate")
    total = critical + high + moderate + _number(vulns, "low")
    if total <= 0:
        return 0.0
    # Severity-weighted exposure, saturating so one noisy feed cannot dominate.
    weighted = (1.0 * critical) + (0.65 * high) + (0.30 * moderate) + (0.10 * _number(vulns, "low"))
    return _clamp01(1.0 - exp(-weighted / 4.0))


def _dependency_freshness(repo):
    value = repo.get("dependency_freshness_risk")
    if value is not None:
        return _clamp01(value)
    deps = repo.get("dependencies")
    if isinstance(deps, dict):
        return _clamp01(_number(deps, "outdated_ratio", 0.0))
    return 0.0


def _maintenance_risk(repo):
    if repo.get("archived") or repo.get("disabled"):
        return 1.0
    days = days_since(repo.get("pushed_at") or repo.get("updated_at"))
    return _recency_risk(days)


def _provenance_weakness(repo):
    # Missing evidence is treated as partial uncertainty rather than a binary
    # accusation. Explicit negative signals carry more weight.
    if repo.get("provenance_risk") is not None:
        return _clamp01(repo["provenance_risk"])
    score = 0.0
    checks = 0
    for key, penalty in (
        ("signed_commits", 0.30),
        ("signed_releases", 0.30),
        ("verified_publisher", 0.25),
        ("release_provenance", 0.15),
    ):
        if key in repo:
            checks += 1
            if not repo.get(key):
                score += penalty
    if checks == 0:
        return 0.35
    return _clamp01(score / sum(p for k, p in (("signed_commits", .30), ("signed_releases", .30), ("verified_publisher", .25), ("release_provenance", .15)) if k in repo))


def _security_control_weakness(repo):
    if repo.get("security_control_risk") is not None:
        return _clamp01(repo["security_control_risk"])
    signals = []
    for key in ("has_security_policy", "has_codeowners", "branch_protection", "dependabot_enabled", "ci_present"):
        if key in repo:
            signals.append(0.0 if repo.get(key) else 1.0)
    if not signals:
        # Current GitHub metadata does not expose these checks in our MVP.
        return 0.35
    return _clamp01(sum(signals) / len(signals))


def _dependency_complexity(repo):
    value = repo.get("dependency_complexity_risk")
    if value is not None:
        return _clamp01(value)
    deps = repo.get("dependencies")
    if isinstance(deps, dict):
        count = _number(deps, "count")
        transitive = _number(deps, "transitive_count")
        return _clamp01((min(count / 100.0, 1.0) * 0.6) + (min(transitive / 150.0, 1.0) * 0.4))
    return 0.0


def _community_quality(repo):
    stars = _number(repo, "stars")
    forks = _number(repo, "forks")
    contributors = _number(repo, "contributors", 0)
    return _clamp01(
        0.50 * min(stars / 15000.0, 1.0)
        + 0.25 * min(forks / 3000.0, 1.0)
        + 0.25 * min(contributors / 250.0, 1.0)
    )


def _documentation_quality(repo):
    score = 0.0
    if repo.get("has_readme"):
        score += 0.55
    if repo.get("description"):
        score += 0.20
    if len(repo.get("topics") or []) >= 3:
        score += 0.15
    if repo.get("docs_present"):
        score += 0.10
    return _clamp01(score)


def _release_quality(repo):
    if repo.get("release_count") is not None:
        return _clamp01(min(_number(repo, "release_count") / 10.0, 1.0))
    return _recency_quality(days_since(repo.get("last_release"))) if repo.get("last_release") else 0.35


def _testing_ci_quality(repo):
    if "testing_ci_score" in repo:
        return _clamp01(repo["testing_ci_score"])
    signals = []
    for key in ("ci_present", "tests_present"):
        if key in repo:
            signals.append(1.0 if repo.get(key) else 0.0)
    return sum(signals) / len(signals) if signals else 0.35


def _project_maturity(repo):
    created = _dt(repo.get("created_at"))
    if not created:
        return 0.35
    years = max(0.0, (datetime.now(timezone.utc) - created.astimezone(timezone.utc)).days / 365.25)
    return _clamp01(years / 5.0)


def _provenance_quality(repo):
    return 1.0 - _provenance_weakness(repo)


def _dependency_transparency(repo):
    if repo.get("dependency_transparency") is not None:
        return _clamp01(repo["dependency_transparency"])
    if repo.get("dependencies") is not None:
        return 1.0
    return 0.35


def _security_policy_quality(repo):
    if "has_security_policy" in repo:
        return 1.0 if repo.get("has_security_policy") else 0.0
    return 0.35


def _ci_security_quality(repo):
    if repo.get("ci_security_score") is not None:
        return _clamp01(repo["ci_security_score"])
    if "ci_present" in repo:
        return 0.65 if repo.get("ci_present") else 0.15
    return 0.35


def _release_integrity(repo):
    if repo.get("release_integrity_score") is not None:
        return _clamp01(repo["release_integrity_score"])
    if "signed_releases" in repo:
        return 1.0 if repo.get("signed_releases") else 0.0
    return 0.35


def _license_quality(repo):
    license_value = repo.get("license")
    return 1.0 if license_value and license_value != "Unknown" else 0.0


def _weighted(values, weights):
    return sum(_clamp01(values[key]) * weight for key, weight in weights.items())


def calculate_security_risk(repo):
    """Return 0-100 where higher means greater security/supply-chain risk."""
    components = {
        "vulnerability_exposure": _vulnerability_exposure(repo),
        "dependency_freshness": _dependency_freshness(repo),
        "maintenance_risk": _maintenance_risk(repo),
        "provenance_weakness": _provenance_weakness(repo),
        "security_control_weakness": _security_control_weakness(repo),
        "dependency_complexity": _dependency_complexity(repo),
    }
    base = _weighted(components, RISK_WEIGHTS)

    # Interaction terms model compounding risk without hiding the base score.
    interaction = (
        0.15 * components["vulnerability_exposure"] * components["dependency_freshness"]
        + 0.10 * components["maintenance_risk"] * components["provenance_weakness"]
        + 0.10 * components["security_control_weakness"] * components["dependency_complexity"]
    )
    score = _clamp100((base + interaction) * 100.0)

    hard_gates = []
    vulns = repo.get("vulnerabilities") or repo.get("vulnerability_summary") or {}
    critical = _number(vulns, "critical") if isinstance(vulns, dict) else 0
    if critical > 0 or repo.get("critical_vulnerability"):
        hard_gates.append("CRITICAL_VULNERABILITY")
    if repo.get("provenance_failure"):
        hard_gates.append("PROVENANCE_FAILURE")

    return {
        "score": score,
        "level": "HIGH" if score >= 70 else "MEDIUM" if score >= 40 else "LOW",
        "base_score": _clamp100(base * 100.0),
        "interaction_penalty": _clamp100(interaction * 100.0),
        "components": {key: round(value * 100, 1) for key, value in components.items()},
        "weights": RISK_WEIGHTS.copy(),
        "hard_gates": hard_gates,
    }


def calculate_technical_maturity(repo):
    values = {
        "maintenance": _recency_quality(days_since(repo.get("pushed_at") or repo.get("updated_at"))),
        "community": _community_quality(repo),
        "documentation": _documentation_quality(repo),
        "release_discipline": _release_quality(repo),
        "testing_ci": _testing_ci_quality(repo),
        "project_maturity": _project_maturity(repo),
    }
    score = _clamp100(_weighted(values, MATURITY_WEIGHTS) * 100)
    return {
        "score": score,
        "level": "HIGH" if score >= 75 else "MEDIUM" if score >= 50 else "LOW",
        "components": {key: round(value * 100, 1) for key, value in values.items()},
        "weights": MATURITY_WEIGHTS.copy(),
    }


def calculate_supply_assurance(repo):
    values = {
        "provenance": _provenance_quality(repo),
        "dependency_transparency": _dependency_transparency(repo),
        "security_policy": _security_policy_quality(repo),
        "ci_security": _ci_security_quality(repo),
        "release_integrity": _release_integrity(repo),
        "license": _license_quality(repo),
    }
    score = _clamp100(_weighted(values, ASSURANCE_WEIGHTS) * 100)
    return {
        "score": score,
        "level": "HIGH" if score >= 75 else "MEDIUM" if score >= 50 else "LOW",
        "components": {key: round(value * 100, 1) for key, value in values.items()},
        "weights": ASSURANCE_WEIGHTS.copy(),
    }


def calculate_confidence(repo):
    """Estimate how much of the risk model is backed by actual evidence."""
    evidence_keys = {
        "vulnerability_exposure": any(k in repo for k in ("vulnerabilities", "vulnerability_summary", "critical_vulnerability")),
        "dependency_freshness": any(k in repo for k in ("dependency_freshness_risk", "dependencies")),
        "maintenance_risk": any(k in repo for k in ("pushed_at", "updated_at")),
        "provenance_weakness": any(k in repo for k in ("provenance_risk", "signed_commits", "signed_releases", "verified_publisher", "release_provenance")),
        "security_control_weakness": any(k in repo for k in ("security_control_risk", "has_security_policy", "has_codeowners", "branch_protection", "dependabot_enabled", "ci_present")),
        "dependency_complexity": any(k in repo for k in ("dependency_complexity_risk", "dependencies")),
    }
    confidence = _weighted({k: 1.0 if present else 0.0 for k, present in evidence_keys.items()}, RISK_WEIGHTS)
    return round(confidence * 100, 1)


def assess_repository(repo):
    """Calculate all assurance dimensions and an explainable decision."""
    risk = calculate_security_risk(repo)
    maturity = calculate_technical_maturity(repo)
    assurance = calculate_supply_assurance(repo)
    confidence = calculate_confidence(repo)

    gates = list(risk["hard_gates"])
    if confidence < 50:
        gates.append("INSUFFICIENT_EVIDENCE")

    if "CRITICAL_VULNERABILITY" in gates or "PROVENANCE_FAILURE" in gates or risk["score"] >= 70:
        decision = "HOLD"
    elif "INSUFFICIENT_EVIDENCE" in gates:
        decision = "REVIEW"
    elif risk["score"] <= 35 and assurance["score"] >= 60 and maturity["score"] >= 50:
        decision = "SCREENING_PASS"
    else:
        decision = "REVIEW"

    rationale = []
    if risk["score"] >= 70:
        rationale.append("security risk is high")
    elif risk["score"] >= 40:
        rationale.append("security risk requires review")
    else:
        rationale.append("no high aggregate security-risk signal is present")
    if assurance["score"] < 50:
        rationale.append("supply-chain assurance evidence is weak or incomplete")
    if maturity["score"] < 50:
        rationale.append("technical maturity evidence is limited")
    if confidence < 50:
        rationale.append("important evidence is not yet available")
    if decision == "SCREENING_PASS":
        rationale.append("the result is still a screening outcome, not a safety certification")

    return {
        "security_risk": risk,
        "technical_maturity": maturity,
        "supply_assurance": assurance,
        "confidence": confidence,
        "decision": decision,
        "gates": gates,
        "rationale": "; ".join(rationale).capitalize() + ".",
        "model_version": "0.1",
    }
