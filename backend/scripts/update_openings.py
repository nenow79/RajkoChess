#!/usr/bin/env python3
"""Build data/openings.json from the a.tsv..e.tsv files of lichess-org/chess-openings."""
import csv
import hashlib
import json
import sys
from io import StringIO
from pathlib import Path

import chess.pgn


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp")
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).parents[1] / "data" / "openings.json"
    records = []
    for volume in "abcde":
        with (source / f"{volume}.tsv").open(encoding="utf-8", newline="") as source_file:
            for row in csv.DictReader(source_file, delimiter="\t"):
                game = chess.pgn.read_game(StringIO(row["pgn"]))
                if not game:
                    continue
                board = game.board()
                moves = []
                for move in game.mainline_moves():
                    moves.append(move.uci())
                    board.push(move)
                stable_id = hashlib.sha1(f'{row["eco"]}:{row["name"]}:{row["pgn"]}'.encode()).hexdigest()[:12]
                records.append({"id": stable_id, "eco": row["eco"], "name": row["name"], "pgn": row["pgn"], "uci": moves})
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(records, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {len(records)} openings to {target}")


if __name__ == "__main__":
    main()
