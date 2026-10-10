"""Dependency-free checks for public docs/JSON; never inspect local/private data."""
from pathlib import Path
import json
import re
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]


def unique_members(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"Duplicate JSON member: {key}")
        value[key] = item
    return value


def main():
    documents = sorted((ROOT / "docs").rglob("*.md"))
    documents += sorted(ROOT.glob("*.md"))
    documents += sorted((ROOT / ".github").glob("*.md"))
    documents += sorted((ROOT / "experiments").glob("*/README.md"))
    errors = []
    links = 0
    for path in documents:
        text = path.read_text(encoding="utf-8")
        if text.count("```") % 2:
            errors.append(f"{path.relative_to(ROOT)}: unmatched code fence")
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if urlparse(target).scheme or target.startswith("#"):
                continue
            local = (path.parent / unquote(target.split("#")[0])).resolve()
            if not local.is_relative_to(ROOT) or not local.exists():
                errors.append(f"{path.relative_to(ROOT)}: missing/escaped link {target}")
            links += 1
    json_files = sorted((ROOT / "docs").rglob("*.json"))
    for path in json_files:
        try:
            json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_members)
        except (ValueError, UnicodeError) as error:
            errors.append(f"{path.relative_to(ROOT)}: {error}")
    print(json.dumps({"documents": len(documents), "localLinks": links,
                      "jsonFiles": len(json_files), "errors": errors}, indent=2))
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
