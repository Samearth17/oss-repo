"""Application service: discovery, snapshot comparison, and persistence."""
import os
from .detector import detect_changes
from .github_client import GITHUB_SEARCH_PAGE_SIZE, GitHubClientError, discover_demo, get_repository, github_url, search_repositories, utc_now
from .scoring import explain_score, score_repository
from .army_relevance import assess_army_relevance
from .risk_engine import assess_repository
from .storage import Store
DEFAULT_LIVE_QUERY="topic:security"

def enrich(repositories,previous=None,demo=False):
    previous={repo["full_name"]:repo for repo in (previous or [])}; enriched=[]
    for repo in repositories:
        record=dict(repo); record["github_url"]=github_url(record["full_name"]); record["watchlisted"]=previous.get(record["full_name"],{}).get("watchlisted",demo); record["score"]=score_repository(record); record["score_explanation"]=explain_score(record); record["army_relevance"]=assess_army_relevance(record); record["assurance"]=assess_repository(record); enriched.append(record)
    return enriched

def discover(query=DEFAULT_LIVE_QUERY,page=1,per_page=GITHUB_SEARCH_PAGE_SIZE,mode=None,store=None):
    """Return dynamic discovery results without changing the monitoring snapshot."""
    mode=mode or os.getenv("OSS_WATCH_MODE","DEMO"); state=(store or Store()).load()
    if mode=="DEMO":
        results=discover_demo(); return {"repositories":enrich(results,state.get("repositories"),demo=True),"total_count":len(results),"page":1,"per_page":GITHUB_SEARCH_PAGE_SIZE}
    result=search_repositories(query=query,page=page,per_page=per_page,with_metadata=True)
    result["repositories"]=enrich(result["repositories"],state.get("repositories"))
    return result

def add_to_watchlist(full_name,mode=None,store=None):
    """Persist a selected repository; live entries are fetched again server-side."""
    mode=mode or os.getenv("OSS_WATCH_MODE","DEMO"); state_store=store or Store(); state=state_store.load()
    existing=next((repo for repo in state.get("repositories",[]) if repo["full_name"]==full_name),None)
    if existing:
        existing["watchlisted"]=True; state_store.save(state); return existing
    if mode=="DEMO":
        raw=next((repo for repo in discover_demo() if repo["full_name"]==full_name),None)
        if not raw: raise GitHubClientError("Repository is not available in the local demo dataset.")
    else: raw=get_repository(full_name)
    record=enrich([raw],state.get("repositories"),demo=False)[0]; record["watchlisted"]=True
    state.setdefault("repositories",[]).append(record); state_store.save(state); return record

def run_scan(mode=None,store=None):
    mode=mode or os.getenv("OSS_WATCH_MODE","DEMO"); state_store=store or Store(); state=state_store.load(); now=utc_now()
    try:
        if mode=="DEMO": repos=enrich(discover_demo(),state.get("repositories"),demo=True)
        else:
            repos=[]
            for previous in state.get("repositories",[]):
                if not previous.get("watchlisted"): continue
                try: repos.append(enrich([get_repository(previous["full_name"])],state.get("repositories"))[0])
                except GitHubClientError: repos.append(previous)
        changes=detect_changes(state.get("repositories"),repos,now)
        state.update({"repositories":repos,"last_scan":now,"mode":mode,"api_status":"Fixture dataset / offline" if mode=="DEMO" else "GitHub REST API connected","error":None,"last_discovery_query":DEFAULT_LIVE_QUERY})
        state["alerts"]=(state.get("alerts",[])+changes)[-200:]
        state["history"]=(state.get("history",[])+[{"at":now,"scores":{repo["full_name"]:repo["score"]["total"] for repo in repos}}])[-30:]
    except GitHubClientError as exc:
        state.update({"mode":mode,"api_status":"GitHub API unavailable","error":str(exc)})
    state_store.save(state); return state
