from pathlib import Path
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from src.dashboard import add_to_watchlist, discover, enrich, run_scan
from src.github_client import GitHubClientError, discover_demo, get_repository
from src.storage import Store

BASE_DIR = Path(__file__).resolve().parent.parent


def index(request):
    return HttpResponse((BASE_DIR / "templates/index.html").read_text(encoding="utf-8"))


def state_api(request):
    return JsonResponse(Store().load())


def discover_api(request):
    store = Store()
    state = store.load()
    query = request.GET.get("q", "topic:security")
    page = request.GET.get("page", 1)
    try:
        results = discover(query=query, page=page, store=store)
        state["last_discovery_query"] = query
        state["last_discovery_count"] = results.get("total_count", len(results.get("repositories", [])))
        state["last_discovery_page"] = results.get("page", 1)
        state["error"] = None
        store.save(state)
        return JsonResponse(results)
    except GitHubClientError as exc:
        state["error"] = str(exc)
        store.save(state)
        return JsonResponse({"repositories": [], "error": str(exc)}, status=503)


def repository_api(request):
    full_name = (request.GET.get("full_name") or "").strip()
    if not full_name or "/" not in full_name:
        return JsonResponse({"error": "A valid owner/name repository is required."}, status=400)
    store = Store()
    state = store.load()
    found = next((r for r in state.get("repositories", []) if r.get("full_name") == full_name), None)
    if found:
        return JsonResponse({"repository": found})
    mode = state.get("mode") or "DEMO"
    try:
        if mode == "DEMO":
            raw = next((r for r in discover_demo() if r["full_name"] == full_name), None)
            if not raw:
                return JsonResponse({"error": "Repository is not present in the demo dataset."}, status=404)
        else:
            raw = get_repository(full_name)
        return JsonResponse({"repository": enrich([raw], state.get("repositories"), demo=(mode == "DEMO"))[0]})
    except GitHubClientError as exc:
        return JsonResponse({"error": str(exc)}, status=503)


@csrf_exempt
def scan_api(request):
    return JsonResponse(run_scan())


@csrf_exempt
def watchlist_add_api(request):
    try:
        payload = json.loads(request.body or "{}")
        return JsonResponse({"repository": add_to_watchlist(payload.get("full_name", ""))})
    except (GitHubClientError, json.JSONDecodeError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)


@csrf_exempt
def watchlist_api(request, repo):
    store = Store()
    state = store.load()
    found = next((r for r in state.get("repositories", []) if r.get("full_name") == repo), None)
    if found:
        found["watchlisted"] = not found.get("watchlisted", False)
        store.save(state)
    return JsonResponse(state)
