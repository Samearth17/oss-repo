"""Previous/current snapshot comparison."""
FIELDS = (("stars", "STAR_CHANGE"), ("forks", "FORK_CHANGE"), ("open_issues", "OPEN_ISSUES_CHANGE"))

def detect_changes(previous, current, now):
    old = {r["full_name"]: r for r in (previous or [])}
    changes = []
    for repo in current:
        name = repo["full_name"]
        if name not in old:
            changes.append(event("NEW_REPOSITORY", repo, None, None, now))
            continue
        prior = old[name]
        for field, kind in FIELDS:
            before, after = prior.get(field, 0), repo.get(field, 0)
            if before != after:
                changes.append(event(kind, repo, before, after, now, field))
        if prior.get("pushed_at") != repo.get("pushed_at"):
            changes.append(event("REPOSITORY_UPDATED", repo, prior.get("pushed_at"), repo.get("pushed_at"), now, "pushed_at"))
        old_score = prior.get("score", {}).get("total")
        new_score = repo.get("score", {}).get("total")
        if old_score is not None and old_score != new_score:
            changes.append(event("SCORE_CHANGE", repo, old_score, new_score, now, "score"))
            if prior.get("score", {}).get("priority") != repo["score"]["priority"]:
                changes.append(event("PRIORITY_CHANGE", repo, prior["score"]["priority"], repo["score"]["priority"], now, "priority"))
    return changes

def event(kind, repo, before, after, detected_at, field=None):
    return {"id": f"{detected_at}-{repo['full_name']}-{kind}-{field or 'new'}", "type": kind,
            "repository": repo["full_name"], "field": field, "previous": before, "current": after,
            "delta": after - before if isinstance(after, (int, float)) and isinstance(before, (int, float)) else None,
            "detected_at": detected_at, "priority": repo.get("score", {}).get("priority", "REVIEW"), "status": "OPEN"}
