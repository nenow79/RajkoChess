import unittest
import uuid
from datetime import timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from chess_logic.history import (
    list_owned_games,
    parse_game_source,
    parse_played_at,
    persist_imported_game,
)
from db.models import Game, GameSource


class HistoryServiceTests(unittest.IsolatedAsyncioTestCase):
    def test_source_and_played_at_are_normalized(self):
        self.assertEqual(parse_game_source({"id": "abc"}), GameSource.CHESSCOM)
        self.assertEqual(parse_game_source({"source": "bot"}), GameSource.BOT)
        self.assertEqual(parse_game_source({"source": "unknown"}), GameSource.PGN)
        self.assertIsNone(parse_played_at("not-a-date"))

        played_at = parse_played_at("2026-08-15T12:30:00Z")
        assert played_at is not None
        self.assertEqual(played_at.tzinfo, timezone.utc)

    async def test_chesscom_import_updates_existing_game(self):
        owner_id = uuid.uuid4()
        existing = Game(
            owner_id=owner_id,
            source=GameSource.CHESSCOM,
            external_id="archive-game-1",
            pgn="old",
            metadata_json={},
        )
        db = SimpleNamespace(
            scalar=AsyncMock(return_value=existing),
            add=Mock(),
            flush=AsyncMock(),
        )

        result = await persist_imported_game(
            db,  # type: ignore[arg-type]
            user=SimpleNamespace(id=owner_id),  # type: ignore[arg-type]
            pgn="new-pgn",
            metadata={
                "id": "archive-game-1",
                "source": "chesscom",
                "opponent": "Tester",
            },
        )

        self.assertIs(result, existing)
        self.assertEqual(existing.pgn, "new-pgn")
        self.assertEqual(existing.metadata_json["opponent"], "Tester")
        db.add.assert_not_called()
        db.flush.assert_awaited_once()

    async def test_local_import_creates_a_new_owned_game(self):
        owner_id = uuid.uuid4()
        db = SimpleNamespace(
            scalar=AsyncMock(),
            add=Mock(),
            flush=AsyncMock(),
        )

        result = await persist_imported_game(
            db,  # type: ignore[arg-type]
            user=SimpleNamespace(id=owner_id),  # type: ignore[arg-type]
            pgn="1. e4 e5",
            metadata={"source": "pgn"},
        )

        self.assertEqual(result.owner_id, owner_id)
        self.assertEqual(result.source, GameSource.PGN)
        db.scalar.assert_not_awaited()
        db.add.assert_called_once_with(result)
        db.flush.assert_awaited_once()

    async def test_history_can_be_filtered_to_bot_games_in_database_query(self):
        owner_id = uuid.uuid4()
        db = SimpleNamespace(scalars=AsyncMock(return_value=[]))

        result = await list_owned_games(
            db,  # type: ignore[arg-type]
            user=SimpleNamespace(id=owner_id),  # type: ignore[arg-type]
            limit=10,
            offset=0,
            source=GameSource.BOT,
        )

        self.assertEqual(result, [])
        statement = db.scalars.await_args.args[0]
        self.assertIn("games.owner_id", str(statement))
        self.assertIn("games.source", str(statement))


if __name__ == "__main__":
    unittest.main()
