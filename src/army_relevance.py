"""Explainable Indian Army relevance assessment for repository capabilities."""

CAPABILITY_RULES = {
    "Cyber Defence": {"cybersecurity", "security", "siem", "soc", "xdr", "edr", "threat", "incident", "response", "hunting"},
    "Network Security": {"network", "nsm", "ids", "ips", "firewall", "packet", "traffic", "dns"},
    "Threat Detection": {"detection", "detect", "sigma", "yara", "rules", "threat", "hunting", "alert"},
    "Security Monitoring": {"monitoring", "observability", "siem", "logging", "logs", "telemetry", "audit"},
    "Incident Response": {"incident", "response", "forensics", "case-management", "case", "investigation"},
    "Digital Forensics": {"forensics", "memory-analysis", "disk-analysis", "artifact", "malware-analysis"},
    "Infrastructure Security": {"cloud", "kubernetes", "docker", "terraform", "ansible", "infrastructure", "endpoint", "server"},
    "Data / Intelligence Analysis": {"osint", "intelligence", "analytics", "analysis", "search", "correlation"},
}

DIRECT_TERMS = {"siem", "soc", "ids", "ips", "edr", "xdr", "incident", "forensics", "threat", "cybersecurity", "security-monitoring", "network-security"}

def _text(repo):
    return " ".join([
        str(repo.get("name", "")),
        str(repo.get("description", "")),
        " ".join(repo.get("topics") or []),
        str(repo.get("language", "")),
    ]).lower()

def assess_army_relevance(repo):
    text = _text(repo)
    matched = []
    capability_hits = {}
    for capability, terms in CAPABILITY_RULES.items():
        hits = sum(1 for term in terms if term in text)
        if hits:
            capability_hits[capability] = hits
            matched.append(capability)
    direct_hits = sum(1 for term in DIRECT_TERMS if term in text)
    score = 1
    if direct_hits >= 3 or len(matched) >= 4:
        score = 5
    elif direct_hits >= 2 or len(matched) >= 3:
        score = 4
    elif direct_hits >= 1 or len(matched) >= 2:
        score = 3
    elif matched:
        score = 2

    level = "HIGH" if score >= 4 else "MEDIUM" if score == 3 else "LOW"
    capabilities = sorted(matched, key=lambda x: (-capability_hits[x], x))[:5]
    if score >= 4:
        rationale = "Strong alignment with security capabilities that could support further Army technical evaluation in controlled environments."
    elif score == 3:
        rationale = "Relevant supporting security capability with potential value for Army-focused technical evaluation and integration."
    elif score == 2:
        rationale = "Some security capability signals are present, but Army-specific value would require further technical assessment."
    else:
        rationale = "No strong Army-specific capability signal was identified from the available repository metadata."
    return {
        "score": score,
        "level": level,
        "capabilities": capabilities,
        "rationale": rationale,
        "considerations": [
            "Security review before any operational use",
            "Integration and compatibility testing",
            "Deployment suitability must be evaluated in the intended environment",
        ],
    }
