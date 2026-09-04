from django.urls import path, re_path
from .views import discover_api, index, state_api, scan_api, watchlist_add_api, watchlist_api, repository_api

urlpatterns = [
    path("api/state", state_api),
    path("api/discover", discover_api),
    path("api/repository", repository_api),
    path("api/scan", scan_api),
    path("api/watchlist", watchlist_add_api),
    re_path(r"^api/watchlist/(?P<repo>.+)$", watchlist_api),
    re_path(r"^(?!api/).*$", index),
]
