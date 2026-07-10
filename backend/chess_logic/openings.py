import json
from functools import lru_cache
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "openings.json"


@lru_cache(maxsize=1)
def get_openings() -> list[dict]:
    if not DATA_PATH.exists():
        return []
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def find_opening(opening_id: str) -> dict | None:
    return next((item for item in get_openings() if item["id"] == opening_id), None)


def search_openings(query: str = "", limit: int = 30) -> list[dict]:
    words = query.casefold().split()
    matches = []
    for item in get_openings():
        haystack = f'{item["eco"]} {item["name"]}'.casefold()
        if all(word in haystack for word in words):
            matches.append(item)
    normalized = query.strip().casefold()
    matches.sort(key=lambda item: (
        0 if item["name"].casefold() == normalized else
        1 if item["name"].casefold().startswith(normalized) else 2,
        len(item["name"]), item["eco"], item["name"],
    ))
    return matches[:limit]


def resolve_opening(value: str) -> dict | None:
    normalized = value.strip().casefold()
    if not normalized:
        return None
    exact = next((item for item in get_openings() if item["id"].casefold() == normalized), None)
    if exact:
        return exact
    exact = next((item for item in get_openings() if item["name"].casefold() == normalized), None)
    if exact:
        return exact
    matches = search_openings(value, limit=2)
    return matches[0] if len(matches) == 1 else None
