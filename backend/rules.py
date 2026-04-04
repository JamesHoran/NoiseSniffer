import json
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

RULES_FILE = Path(__file__).parent / "rules.json"

# In-memory store keyed by port — updated by watchdog and POST /rules.
_rules: dict[int, dict] = {}


def get_rules() -> dict[int, dict]:
    print(f"[rules get] Returning {len(_rules)} rule(s) from memory: {list(_rules.keys())}")
    return _rules


def load_rules() -> dict[int, dict]:
    """Read rules.json from disk and return as a port-keyed dict."""
    if not RULES_FILE.exists():
        print(f"[rules load] File {RULES_FILE} does not exist, returning empty dict")
        return {}
    try:
        with open(RULES_FILE) as f:
            rules_list = json.load(f)
        rules = {r["port"]: r for r in rules_list}
        print(f"[rules load] Loaded {len(rules)} rule(s) from {RULES_FILE}: {list(rules.keys())}")
        return rules
    except Exception as e:
        print(f"[rules load] Error loading rules: {e}")
        return {}


def delete_rule(port: int):
    """Remove a rule by port and persist to disk."""
    global _rules
    print(f"[rules delete] Deleting rule for port {port}")
    _rules.pop(port, None)
    with open(RULES_FILE, "w") as f:
        json.dump(list(_rules.values()), f, indent=2)
    print(f"[rules delete] Rule deleted. Remaining rules: {list(_rules.keys())}")


def save_rule(rule: dict):
    """Insert or overwrite a rule for its port, then persist to disk."""
    global _rules
    port = rule["port"]
    is_new = port not in _rules
    _rules[port] = rule
    print(f"[rules save] {'Created new' if is_new else 'Updated'} rule for port {port}: {rule}")
    with open(RULES_FILE, "w") as f:
        json.dump(list(_rules.values()), f, indent=2)
    print(f"[rules save] Rules saved to disk. Total rules: {list(_rules.keys())}")


class _RulesFileHandler(FileSystemEventHandler):
    def __init__(self, on_change):
        self._on_change = on_change

    def on_modified(self, event):
        if not event.is_directory and Path(event.src_path).resolve() == RULES_FILE.resolve():
            print(f"[rules watcher] Detected external change to rules.json, reloading...")
            new_rules = load_rules()
            print(f"[rules watcher] Loaded {len(new_rules)} rule(s) from disk: {list(new_rules.keys())}")
            # BUG FIX: Update global _rules before calling on_change
            global _rules
            _rules = new_rules
            print(f"[rules watcher] Global _rules updated, calling on_change callback...")
            self._on_change(_rules)


def start_watcher(on_change) -> Observer:
    """
    Load rules from disk, start a watchdog observer that calls
    on_change(rules) whenever rules.json is modified externally.
    Returns the observer so the caller can stop it if needed.
    """
    global _rules
    print(f"[rules watcher] Starting watcher, loading initial rules...")
    _rules = load_rules()
    print(f"[rules watcher] Initial rules loaded: {list(_rules.keys())}")

    # Call on_change with initial rules so the audio engine gets them on startup
    print(f"[rules watcher] Calling on_change with initial rules...")
    on_change(_rules)

    observer = Observer()
    observer.schedule(_RulesFileHandler(on_change), str(RULES_FILE.parent), recursive=False)
    observer.start()
    print(f"[rules watcher] Watcher started, monitoring {RULES_FILE}")
    return observer
