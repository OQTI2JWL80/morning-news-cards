"""Check actual deploy contents, not the private workspace or environment."""
import gzip
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from newsbrief.storage import validate_edition


def check(root):
    root = Path(root)
    index = json.loads((root / "data/index.json").read_text(encoding="utf-8"))
    if not index["editions"] or len(index["editions"]) > 30:
        raise ValueError("Invalid archive length")
    count = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in (".html", ".css", ".js", ".json", ".svg", ".webmanifest") and path.name != ".nojekyll":
            raise ValueError(f"Unexpected public file: {path.name}")
        raw = path.read_bytes()
        if re.search(rb"AIza[0-9A-Za-z_-]{25,}|github_pat_[0-9A-Za-z_]+|gh[pousr]_[0-9A-Za-z]{20,}", raw):
            raise ValueError("Possible credential in public build")
        if path.parent.name == "data" and path.name != "index.json":
            validate_edition(json.loads(raw))
            count += 1
    if count != len(index["editions"]):
        raise ValueError("Archive index does not match files")
    initial = [root / p for p in ["index.html", "styles.css", "app.js", "favicon.svg", "manifest.webmanifest", "data/index.json", f"data/{index['latest']}.json"]]
    size = sum(len(gzip.compress(p.read_bytes())) for p in initial)
    if size > 500 * 1024:
        raise ValueError("Initial load exceeds 500KB gzip target")
    print(f"Public build OK: {count} editions, initial gzip estimate {size / 1024:.1f} KB")


if __name__ == "__main__":
    check(sys.argv[1] if len(sys.argv) > 1 else "build")

