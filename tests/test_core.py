from src.detector import detect_changes
from src.github_client import github_url, normalize_repository
from src.github_client import search_repositories
from src.dashboard import add_to_watchlist
from src.scoring import CRITERIA, priority_for, score_repository
from src.storage import Store
from src.army_relevance import assess_army_relevance

def repo(**kw):
    return {"full_name":"acme/tool","stars":10,"forks":2,"open_issues":1,"pushed_at":"a","score":{"total":25,"priority":"LOW"},**kw}

def test_change_detection_metrics_and_update():
    current=repo(stars=20,forks=4,open_issues=3,pushed_at="b")
    kinds={x["type"] for x in detect_changes([repo()], [current], "now")}
    assert kinds == {"STAR_CHANGE","FORK_CHANGE","OPEN_ISSUES_CHANGE","REPOSITORY_UPDATED"}

def test_new_repository():
    assert detect_changes([], [repo()], "now")[0]["type"] == "NEW_REPOSITORY"

def test_score_and_priority_changes_are_detected():
    current=repo(score={"total":34,"priority":"HIGH"})
    kinds={x["type"] for x in detect_changes([repo()], [current], "now")}
    assert {"SCORE_CHANGE", "PRIORITY_CHANGE"} <= kinds

def test_scoring_and_thresholds():
    r=repo(rubric={k:1 for k in CRITERIA},license=None,has_readme=False,topics=[])
    assert score_repository(r)["total"] == 8
    maximum=repo(rubric={k:5 for k in CRITERIA})
    assert score_repository(maximum)["total"] == 40
    assert score_repository(maximum)["percentage"] == 100
    assert priority_for(36)=="HIGH"; assert priority_for(35)=="MEDIUM"; assert priority_for(28)=="MEDIUM"; assert priority_for(27)=="LOW"; assert priority_for(20)=="LOW"; assert priority_for(19)=="REVIEW"

def test_highly_active_adopted_repository_can_reach_high():
    mature_security_repo=repo(
        full_name="vendor/security-platform",
        description="Security monitoring, SIEM, IDS and threat detection platform with deployment guides.",
        stars=52000,
        forks=7200,
        open_issues=200,
        license="Apache-2.0",
        pushed_at="2026-09-01T12:00:00Z",
        updated_at="2026-09-01T12:00:00Z",
        last_release="2026-08-15",
        has_readme=True,
        topics=["security", "siem", "ids", "threat-hunting", "docker"],
    )
    result=score_repository(mature_security_repo)
    assert result["priority"]=="HIGH"
    assert 36 <= result["total"] <= 40

def test_moderately_active_repository_scores_medium():
    moderate_repo=repo(
        full_name="team/security-helper",
        description="Security monitoring helper for engineering teams.",
        stars=1200,
        forks=140,
        license="MIT",
        pushed_at="2026-06-10T00:00:00Z",
        updated_at="2026-06-10T00:00:00Z",
        has_readme=True,
        topics=["security"],
    )
    result=score_repository(moderate_repo)
    assert result["priority"]=="MEDIUM"
    assert 28 <= result["total"] <= 35

def test_weak_inactive_repository_scores_low_or_review():
    weak_repo=repo(
        full_name="old/abandoned-tool",
        description="Small helper script.",
        stars=4,
        forks=0,
        open_issues=12,
        license="Unknown",
        pushed_at="2021-01-01T00:00:00Z",
        updated_at="2021-01-01T00:00:00Z",
        has_readme=False,
        topics=[],
    )
    result=score_repository(weak_repo)
    assert 0 <= result["total"] <= 40
    assert result["priority"] in {"LOW", "REVIEW"}

def test_storage_roundtrip(tmp_path):
    s=Store(tmp_path/"state.json"); state={"repositories":[repo()],"alerts":[]}
    s.save(state); assert s.load()==state

def test_github_search_normalizes_multiple_result_shapes():
    item={"full_name":"org/tool","name":"tool","stargazers_count":1200,"forks_count":80,"open_issues_count":2,"license":{"spdx_id":"MIT"},"default_branch":"main","topics":["security"]}
    normalized=normalize_repository(item)
    assert normalized["full_name"]=="org/tool"
    assert normalized["stars"]==1200
    assert normalized["license"]=="MIT"
    assert normalized["description"]=="No description provided."

def test_search_returns_multiple_normalized_repositories(monkeypatch):
    class Response:
        ok=True; status_code=200; headers={}
        def json(self): return {"items":[
            {"full_name":"org/one","name":"one","stargazers_count":3,"forks_count":1,"open_issues_count":0},
            {"full_name":"org/two","name":"two","stargazers_count":4,"forks_count":2,"open_issues_count":1},
        ]}
    calls=[]
    def fake_get(*args, **kwargs): calls.append(kwargs); return Response()
    monkeypatch.setattr("src.github_client.requests.get", fake_get)
    repos=search_repositories("topic:security", page=3, per_page=2)
    assert [r["full_name"] for r in repos]==["org/one","org/two"]
    assert calls[0]["params"]["page"]==3
    assert calls[0]["params"]["per_page"]==2

def test_discovered_live_repository_can_be_added_to_watchlist(monkeypatch, tmp_path):
    discovered={"full_name":"live/tool","name":"tool","stars":100,"forks":2,"open_issues":1,"language":"Python","license":"MIT","pushed_at":"now","topics":["security"]}
    monkeypatch.setattr("src.dashboard.get_repository", lambda name: discovered)
    store=Store(tmp_path/"state.json")
    record=add_to_watchlist("live/tool", mode="LIVE", store=store)
    assert record["watchlisted"] is True
    assert record["score"]["total"] > 0
    assert store.load()["repositories"][0]["full_name"]=="live/tool"

def test_github_url_uses_repository_full_name():
    assert github_url("wazuh/wazuh")=="https://github.com/wazuh/wazuh"


def test_army_relevance_is_explainable_and_separate():
    strong = {"name":"siem-defense","description":"Security monitoring and threat detection platform","topics":["security","siem","ids","incident-response"]}
    weak = {"name":"photo-organizer","description":"A simple photo organizer","topics":[]}
    s = assess_army_relevance(strong)
    w = assess_army_relevance(weak)
    assert s["score"] >= 4
    assert s["level"] == "HIGH"
    assert s["capabilities"]
    assert "Army" in s["rationale"] or "security capabilities" in s["rationale"]
    assert w["score"] <= 2


def test_fixture_scores_are_not_all_identical():
    sample = [
        repo(full_name="a/security", stars=52000, forks=7000, description="SIEM threat detection security monitoring", license="Apache-2.0", has_readme=True, topics=["security","siem"], pushed_at="2026-09-01T00:00:00Z", updated_at="2026-09-01T00:00:00Z", last_release="2026-08-01"),
        repo(full_name="b/helper", stars=20, forks=2, description="Small security helper", license="MIT", has_readme=True, topics=["security"], pushed_at="2025-01-01T00:00:00Z", updated_at="2025-01-01T00:00:00Z"),
    ]
    scores = [score_repository(r)["total"] for r in sample]
    assert scores[0] != scores[1]


def test_security_risk_model_is_explainable_and_bounded():
    from src.risk_engine import assess_repository, calculate_security_risk
    r = repo(
        pushed_at="2026-09-01T00:00:00Z",
        updated_at="2026-09-01T00:00:00Z",
        license="Apache-2.0",
        has_readme=True,
        topics=["security", "siem"],
        ci_present=True,
        tests_present=True,
        has_security_policy=True,
        signed_commits=True,
        signed_releases=True,
        verified_publisher=True,
        dependencies={"count": 20, "transitive_count": 30, "outdated_ratio": 0.1},
        vulnerabilities={"critical": 0, "high": 0, "moderate": 1, "low": 0},
    )
    result = assess_repository(r)
    assert 0 <= result["security_risk"]["score"] <= 100
    assert result["security_risk"]["components"]
    assert abs(sum(result["security_risk"]["weights"].values()) - 1.0) < 1e-9
    assert result["decision"] in {"SCREENING_PASS", "REVIEW", "HOLD"}


def test_critical_vulnerability_forces_hold():
    from src.risk_engine import assess_repository
    r = repo(
        pushed_at="2026-09-01T00:00:00Z",
        license="Apache-2.0",
        vulnerabilities={"critical": 1, "high": 0, "moderate": 0, "low": 0},
        ci_present=True,
        has_security_policy=True,
        signed_commits=True,
        signed_releases=True,
        verified_publisher=True,
    )
    result = assess_repository(r)
    assert result["decision"] == "HOLD"
    assert "CRITICAL_VULNERABILITY" in result["gates"]


def test_missing_evidence_is_not_treated_as_safe():
    from src.risk_engine import assess_repository
    result = assess_repository(repo(description="Small helper", stars=5, forks=0))
    assert result["confidence"] < 50
    assert "INSUFFICIENT_EVIDENCE" in result["gates"]
    assert result["decision"] == "REVIEW"
