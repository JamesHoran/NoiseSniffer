import json
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

RULES_FILE = Path(__file__).parent / "rules.json"

# In-memory store keyed by port — updated by watchdog and POST /rules.
_rules: dict[int, dict] = {}


def get_rules() -> dict[int, dict]:
    return _rules


def load_rules() -> dict[int, dict]:
    """Read rules.json from disk and return as a port-keyed dict."""
    if not RULES_FILE.exists():
        return {}
    try:
        with open(RULES_FILE) as f:
            rules_list = json.load(f)
        return {r["port"]: r for r in rules_list}
    except Exception:
        return {}


def delete_rule(port: int):
    """Remove a rule by port and persist to disk."""
    global _rules
    _rules.pop(port, None)
    with open(RULES_FILE, "w") as f:
        json.dump(list(_rules.values()), f, indent=2)


def save_rule(rule: dict):
    """Insert or overwrite a rule for its port, then persist to disk."""
    global _rules
    _rules[rule["port"]] = rule
    with open(RULES_FILE, "w") as f:
        json.dump(list(_rules.values()), f, indent=2)


class _RulesFileHandler(FileSystemEventHandler):
    def __init__(self, on_change):
        self._on_change = on_change

    def on_modified(self, event):
        if not event.is_directory and Path(event.src_path).resolve() == RULES_FILE.resolve():
            self._on_change(load_rules())


def start_watcher(on_change) -> Observer:
    """
    Load rules from disk, start a watchdog observer that calls
    on_change(rules) whenever rules.json is modified externally.
    Returns the observer so the caller can stop it if needed.
    """
    global _rules
    _rules = load_rules()

    observer = Observer()
    observer.schedule(_RulesFileHandler(on_change), str(RULES_FILE.parent), recursive=False)
    observer.start()
    return observer
