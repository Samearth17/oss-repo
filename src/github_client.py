"""GitHub public REST discovery with server-side token support."""
import json
import os
from datetime import datetime, timezone
import requests

GITHUB_SEARCH_PAGE_SIZE = 20

class GitHubClientError(RuntimeError):
    """A user-safe summary of a GitHub API failure."""

def utc_now(): return datetime.now(timezone.utc).isoformat()

def github_url(full_name):
    """Return the canonical public URL for a normalized repository name."""
    return f"https://github.com/{full_name}"

def discover_demo(path="fixtures/repositories.json"):
    with open(path, encoding="utf-8") as fixture: return json.load(fixture)

def normalize_repository(item):
    """Normalize a GitHub search result to OSS Watch's stable schema."""
    return {"full_name":item["full_name"],"name":item["name"],"description":item.get("description") or "No description provided.","language":item.get("language") or "—","stars":item.get("stargazers_count",0),"forks":item.get("forks_count",0),"open_issues":item.get("open_issues_count",0),"license":(item.get("license") or {}).get("spdx_id") or "Unknown","default_branch":item.get("default_branch") or "main","created_at":item.get("created_at"),"updated_at":item.get("updated_at"),"pushed_at":item.get("pushed_at"),"last_release":None,"topics":item.get("topics") or [],"has_readme":item.get("has_readme")}

def _headers():
    headers={"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
    if token:=os.getenv("GITHUB_TOKEN"): headers["Authorization"]=f"Bearer {token}"
    return headers

def _request(url,params=None):
    try:
        response=requests.get(url,params=params,headers=_headers(),timeout=15)
    except requests.RequestException as exc:
        raise GitHubClientError("GitHub API is temporarily unavailable. Check your network connection and try again.") from exc
    if response.status_code==403 and response.headers.get("X-RateLimit-Remaining")=="0":
        raise GitHubClientError("GitHub API rate limit reached. Set GITHUB_TOKEN for a higher request limit, then retry.")
    if response.status_code in {401,403}: raise GitHubClientError("GitHub API authorization failed. Check GITHUB_TOKEN and retry.")
    if not response.ok: raise GitHubClientError(f"GitHub API request failed ({response.status_code}). Please retry shortly.")
    return response

def search_repositories(query="topic:security", page=1, per_page=GITHUB_SEARCH_PAGE_SIZE, sort="updated", with_metadata=False):
    """Search GitHub repositories. Tokens remain exclusively server-side."""
    page=max(int(page),1); per_page=min(max(int(per_page),1),100)
    response=_request("https://api.github.com/search/repositories",{"q":query or "topic:security","sort":sort,"order":"desc","page":page,"per_page":per_page})
    payload=response.json(); repositories=[normalize_repository(item) for item in payload.get("items",[])]
    result={"repositories":repositories,"total_count":payload.get("total_count",len(repositories)),"page":page,"per_page":per_page}
    return result if with_metadata else repositories

def get_repository(full_name):
    """Fetch fresh metadata for a selected live watchlist repository."""
    return normalize_repository(_request(f"https://api.github.com/repos/{full_name}").json())

def discover_live(query="topic:security",per_page=GITHUB_SEARCH_PAGE_SIZE): return search_repositories(query=query,per_page=per_page,sort="updated")
