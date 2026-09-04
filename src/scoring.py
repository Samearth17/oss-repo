"""Explainable repository scoring and priority calculation."""
from datetime import datetime, timezone

CRITERIA = (
    "security_functionality", "detection_capability", "activity_maintenance",
    "community_adoption", "documentation", "deployment_practicality",
    "open_source_health", "defence_relevance",
)

PRIORITY_THRESHOLDS = {"HIGH": 36, "MEDIUM": 28, "LOW": 20, "REVIEW": 0}

SECURITY_TERMS = {
    "security", "secure", "siem", "soc", "xdr", "edr", "ids", "ips", "nsm",
    "threat", "detection", "detect", "monitoring", "incident", "response",
    "forensics", "malware", "vulnerability", "scanner", "audit", "firewall",
    "sigma", "yara", "osint", "hunting", "defence", "defense",
}

DETECTION_TERMS = {
    "detection", "detect", "ids", "ips", "siem", "sigma", "yara", "rules",
    "threat-hunting", "hunting", "monitoring", "nsm", "edr", "xdr", "alert",
}

DEFENCE_TERMS = {
    "siem", "soc", "xdr", "edr", "ids", "ips", "nsm", "threat", "incident",
    "forensics", "malware", "sigma", "yara", "hunting", "defence", "defense",
}

DEPLOYMENT_TERMS = {
    "docker", "kubernetes", "helm", "terraform", "ansible", "cli", "agent",
    "server", "api", "library", "package", "operator", "deployment",
}


def priority_for(score):
    for label, minimum in PRIORITY_THRESHOLDS.items():
        if score >= minimum:
            return label
    return "REVIEW"


def _clamp(value):
    return max(1, min(5, int(round(value))))


def _to_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.fromisoformat(str(value) + "T00:00:00+00:00")
        except ValueError:
            return None


def _days_since(value):
    parsed = _to_datetime(value)
    if not parsed:
        return None
    delta = datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)
    return max(delta.days, 0)


def _recency_score(days):
    if days is None:
        return 1
    if days <= 30:
        return 5
    if days <= 120:
        return 4
    if days <= 365:
        return 3
    if days <= 730:
        return 2
    return 1


def _band(value, bands):
    for minimum, score in bands:
        if value >= minimum:
            return score
    return 1


def _text(repo):
    pieces = [
        repo.get("full_name", ""), repo.get("name", ""), repo.get("description", ""),
        " ".join(repo.get("topics") or []), repo.get("language", ""),
    ]
    return " ".join(str(piece).lower() for piece in pieces if piece)


def _term_hits(text, terms):
    return sum(1 for term in terms if term in text)


def _has_license(repo):
    return bool(repo.get("license") and repo.get("license") != "Unknown")


def _activity_maintenance(repo):
    if repo.get("archived"):
        return 1
    dates = [repo.get("pushed_at"), repo.get("updated_at"), repo.get("last_release")]
    score = max(_recency_score(_days_since(value)) for value in dates)
    if repo.get("last_release") and _days_since(repo.get("last_release")) is not None:
        score = min(5, score + 1)
    return score


def _community_adoption(repo):
    stars = int(repo.get("stars") or 0)
    forks = int(repo.get("forks") or 0)
    contributors = repo.get("contributors")
    star_score = _band(stars, ((15000, 5), (3000, 4), (500, 3), (50, 2)))
    fork_score = _band(forks, ((3000, 5), (500, 4), (100, 3), (10, 2)))
    if isinstance(contributors, int):
        contributor_score = _band(contributors, ((250, 5), (75, 4), (20, 3), (5, 2)))
        return _clamp((star_score * 0.5) + (fork_score * 0.25) + (contributor_score * 0.25))
    return _clamp((star_score * 0.72) + (fork_score * 0.28))


def _documentation(repo):
    description = repo.get("description") or ""
    topics = repo.get("topics") or []
    text = _text(repo)
    has_readme = repo.get("has_readme")
    score = 1 if has_readme is False else 2 if has_readme is None else 3
    if len(description.strip()) >= 45:
        score += 1
    if len(topics) >= 3:
        score += 1
    if any(term in text for term in ("docs", "documentation", "readme", "examples", "guide")):
        score += 1
    if has_readme is None:
        score = min(score, 4)
    return _clamp(score)


def _open_source_health(repo):
    if repo.get("archived") or repo.get("disabled"):
        return 1
    activity = _activity_maintenance(repo)
    community = _community_adoption(repo)
    score = 1
    if _has_license(repo):
        score += 2
    if activity >= 4:
        score += 1
    elif activity >= 2:
        score += 0.5
    if community >= 4:
        score += 1
    elif community >= 3:
        score += 0.5
    if repo.get("open_issues", 0) > 0 and activity <= 1:
        score -= 0.5
    return _clamp(score)


def _metadata_security_functionality(repo):
    hits = _term_hits(_text(repo), SECURITY_TERMS)
    if hits >= 5:
        return 5
    if hits >= 3:
        return 4
    if hits >= 1:
        return 3
    return 2 if repo.get("description") else 1


def _metadata_detection_capability(repo):
    text = _text(repo)
    hits = _term_hits(text, DETECTION_TERMS)
    if hits >= 4:
        return 5
    if hits >= 2:
        return 4
    if hits == 1:
        return 3
    return 2 if _term_hits(text, SECURITY_TERMS) else 1


def _metadata_deployment_practicality(repo):
    text = _text(repo)
    docs = _documentation(repo)
    activity = _activity_maintenance(repo)
    score = 1
    if docs >= 3:
        score += 1
    if _has_license(repo):
        score += 1
    if activity >= 4:
        score += 1
    if _term_hits(text, DEPLOYMENT_TERMS):
        score += 1
    return _clamp(score)


def _metadata_defence_relevance(repo):
    text = _text(repo)
    defence_hits = _term_hits(text, DEFENCE_TERMS)
    security_hits = _term_hits(text, SECURITY_TERMS)
    if defence_hits >= 4:
        return 5
    if defence_hits >= 2:
        return 4
    if defence_hits == 1 or security_hits >= 2:
        return 3
    if security_hits == 1:
        return 2
    return 1


AUTOMATED_SCORERS = {
    "activity_maintenance": _activity_maintenance,
    "community_adoption": _community_adoption,
    "documentation": _documentation,
    "open_source_health": _open_source_health,
}

QUALITATIVE_FALLBACKS = {
    "security_functionality": _metadata_security_functionality,
    "detection_capability": _metadata_detection_capability,
    "deployment_practicality": _metadata_deployment_practicality,
    "defence_relevance": _metadata_defence_relevance,
}


def score_repository(repo):
    """Combine structured rubric values with metadata-derived evidence."""
    manual = repo.get("rubric") or {}
    breakdown = {}
    for key in CRITERIA:
        if key in manual:
            breakdown[key] = _clamp(manual[key])
        elif key in AUTOMATED_SCORERS:
            breakdown[key] = AUTOMATED_SCORERS[key](repo)
        else:
            breakdown[key] = QUALITATIVE_FALLBACKS[key](repo)
    total = max(0, min(40, sum(breakdown.values())))
    return {
        "total": total,
        "percentage": round(total / 40 * 100),
        "priority": priority_for(total),
        "breakdown": breakdown,
    }


def explain_score(repo):
    """Return an evidence-grounded explanation without overstating GitHub metadata."""
    score = repo.get("score") or score_repository(repo)
    reasons = []
    stars = int(repo.get("stars") or 0)
    forks = int(repo.get("forks") or 0)
    activity = score["breakdown"]["activity_maintenance"]
    community = score["breakdown"]["community_adoption"]
    docs = score["breakdown"]["documentation"]
    health = score["breakdown"]["open_source_health"]

    if activity >= 4:
        reasons.append("recent repository activity supports the maintenance score")
    elif activity <= 2:
        reasons.append("limited recent activity lowers the maintenance score")
    if community >= 4:
        reasons.append(f"community adoption is supported by {stars:,} stars and {forks:,} forks")
    elif community <= 2:
        reasons.append("modest star and fork counts keep adoption conservative")
    if docs >= 4:
        reasons.append("description, topics, and documentation signals support the documentation score")
    elif docs <= 2:
        reasons.append("limited description or documentation signals reduce the documentation score")
    if health >= 4 and _has_license(repo):
        reasons.append("license and activity signals support open-source health")
    elif health <= 2:
        reasons.append("missing license or weak activity reduces open-source health")
    if repo.get("rubric"):
        reasons.append("security-specific dimensions use the stored structured assessment")
    else:
        reasons.append("security-specific dimensions use conservative metadata keyword evidence")
    return "; ".join(reasons).capitalize() + "."
