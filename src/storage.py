"""Small JSON persistence layer for local snapshots."""
import json
from pathlib import Path

class Store:
    def __init__(self, path="data/state.json"):
        self.path = Path(path)
    def load(self):
        if not self.path.exists(): return {"repositories": [], "alerts": [], "history": [], "last_scan": None, "mode": "DEMO", "api_status": "Not scanned", "error": None}
        return json.loads(self.path.read_text())
    def save(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, indent=2, sort_keys=True))
