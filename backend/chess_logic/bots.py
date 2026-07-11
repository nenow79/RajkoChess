import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

STYLE_KEYS = ("aggression", "tacticality", "risk", "materialism", "simplification")

SEED_BOTS = [
    {
        "name": "Spokojny Stefan", "description": "Cierpliwy początkujący, który lubi solidne ustawienia.",
        "avatar": "🛡️", "target_elo": 900,
        "style": {"aggression": 20, "tacticality": 25, "risk": 15, "materialism": 60, "simplification": 75},
        "opening_queries": {"white": ["London System"], "black": ["Scandinavian Defense"]},
    },
    {
        "name": "Taktyczny Tadeusz", "description": "Napastnik szukający inicjatywy, szachów i kombinacji.",
        "avatar": "⚡", "target_elo": 1500,
        "style": {"aggression": 85, "tacticality": 90, "risk": 75, "materialism": 45, "simplification": 20},
        "opening_queries": {"white": ["Italian Game"], "black": ["Sicilian Defense"]},
    },
    {
        "name": "Profesor Nimzo", "description": "Silny gracz pozycyjny, naciska małymi przewagami.",
        "avatar": "🎓", "target_elo": 2200,
        "style": {"aggression": 45, "tacticality": 65, "risk": 25, "materialism": 55, "simplification": 60},
        "opening_queries": {"white": ["Queen's Gambit"], "black": ["Nimzo-Indian Defense"]},
    },
]

DEFAULT_PHRASES = {
    "greeting": "Powodzenia! Zagrajmy dobrą partię.",
    "advantage": "Teraz robi się ciekawie.",
    "setback": "To skomplikowana pozycja — gramy dalej.",
    "draw_offer": "Rozważmy spokojnie ten remis.",
    "victory": "Dziękuję za partię.",
    "defeat": "Dobra gra — następnym razem spróbuję inaczej.",
}


class BotStore:
    def __init__(self, path: str | None = None):
        default = Path(__file__).resolve().parent.parent / "data" / "bots.sqlite3"
        self.path = Path(path or os.getenv("BOT_DB_PATH", str(default)))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self._init_db()

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def _init_db(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS bots (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL,
                avatar TEXT NOT NULL, target_elo INTEGER NOT NULL,
                style_json TEXT NOT NULL, openings_json TEXT NOT NULL,
                phrases_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )""")
            db.execute("PRAGMA user_version=1")
            count = db.execute("SELECT COUNT(*) FROM bots").fetchone()[0]
        if count == 0:
            for seed in SEED_BOTS:
                self.create(self._seed_profile(seed))

    def _seed_profile(self, seed):
        from chess_logic.openings import search_openings
        openings = []
        for color, queries in seed["opening_queries"].items():
            for query in queries:
                matches = search_openings(query, 1)
                if matches:
                    openings.append({"opening_id": matches[0]["id"], "color": color, "weight": 100})
        base = {key: value for key, value in seed.items() if key != "opening_queries"}
        return {**base, "openings": openings, "phrases": DEFAULT_PHRASES}

    @staticmethod
    def validate(profile: dict) -> dict:
        result = {
            "name": str(profile.get("name", "")).strip()[:80],
            "description": str(profile.get("description", "")).strip()[:1000],
            "avatar": str(profile.get("avatar", "🤖")).strip()[:8] or "🤖",
            "target_elo": min(2800, max(800, int(profile.get("target_elo", 1400)))),
            "style": {key: min(100, max(0, int((profile.get("style") or {}).get(key, 50)))) for key in STYLE_KEYS},
            "openings": [],
            "phrases": {},
        }
        if not result["name"] or not result["description"]:
            raise ValueError("Nazwa i opis bota są wymagane")
        from chess_logic.openings import find_opening
        for entry in profile.get("openings") or []:
            opening_id = str(entry.get("opening_id", ""))
            color = entry.get("color")
            if find_opening(opening_id) and color in ("white", "black"):
                result["openings"].append({
                    "opening_id": opening_id, "color": color,
                    "weight": min(100, max(1, int(entry.get("weight", 50)))),
                })
        supplied_phrases = profile.get("phrases") or {}
        result["phrases"] = {key: str(supplied_phrases.get(key, value)).strip()[:240] or value for key, value in DEFAULT_PHRASES.items()}
        return result

    def list(self):
        with self._connect() as db:
            rows = db.execute("SELECT * FROM bots ORDER BY created_at").fetchall()
        return [self._row(row) for row in rows]

    def get(self, bot_id):
        with self._connect() as db:
            row = db.execute("SELECT * FROM bots WHERE id=?", (bot_id,)).fetchone()
        return self._row(row) if row else None

    def create(self, profile):
        clean = self.validate(profile)
        now = datetime.now(timezone.utc).isoformat()
        bot_id = str(uuid.uuid4())
        with self.lock, self._connect() as db:
            db.execute("INSERT INTO bots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (
                bot_id, clean["name"], clean["description"], clean["avatar"], clean["target_elo"],
                json.dumps(clean["style"]), json.dumps(clean["openings"]), json.dumps(clean["phrases"]), now, now,
            ))
        return self.get(bot_id)

    def update(self, bot_id, profile):
        if not self.get(bot_id):
            return None
        clean = self.validate(profile)
        now = datetime.now(timezone.utc).isoformat()
        with self.lock, self._connect() as db:
            db.execute("""UPDATE bots SET name=?,description=?,avatar=?,target_elo=?,style_json=?,
                openings_json=?,phrases_json=?,updated_at=? WHERE id=?""", (
                clean["name"], clean["description"], clean["avatar"], clean["target_elo"],
                json.dumps(clean["style"]), json.dumps(clean["openings"]), json.dumps(clean["phrases"]), now, bot_id,
            ))
        return self.get(bot_id)

    def delete(self, bot_id):
        with self.lock, self._connect() as db:
            cursor = db.execute("DELETE FROM bots WHERE id=?", (bot_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _row(row):
        from chess_logic.openings import find_opening
        openings = json.loads(row["openings_json"])
        for entry in openings:
            opening = find_opening(entry["opening_id"])
            if opening:
                entry["name"] = opening["name"]
                entry["eco"] = opening["eco"]
        return {
            "id": row["id"], "name": row["name"], "description": row["description"],
            "avatar": row["avatar"], "target_elo": row["target_elo"],
            "style": json.loads(row["style_json"]), "openings": openings,
            "phrases": json.loads(row["phrases_json"]), "created_at": row["created_at"], "updated_at": row["updated_at"],
        }
