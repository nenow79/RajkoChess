import unittest

from chess_logic.chesscom import (
    ARCHIVE_URL_PREFIX,
    MAX_ARCHIVES_TO_SCAN,
    _recent_safe_archive_urls,
)


class ChessComImportTests(unittest.TestCase):
    def test_only_recent_chesscom_archives_are_scanned(self):
        archives = [
            f"{ARCHIVE_URL_PREFIX}player/games/2025/{month:02d}"
            for month in range(1, MAX_ARCHIVES_TO_SCAN + 5)
        ]

        selected = _recent_safe_archive_urls(archives)

        self.assertEqual(len(selected), MAX_ARCHIVES_TO_SCAN)
        self.assertEqual(selected[0], archives[-1])
        self.assertEqual(selected[-1], archives[-MAX_ARCHIVES_TO_SCAN])

    def test_foreign_and_malformed_archive_urls_are_rejected(self):
        valid = f"{ARCHIVE_URL_PREFIX}player/games/2026/08"
        selected = _recent_safe_archive_urls(
            [
                "https://example.com/internal",
                "http://api.chess.com/pub/player/player/games/2026/08",
                None,
                valid,
            ]
        )

        self.assertEqual(selected, [valid])


if __name__ == "__main__":
    unittest.main()
