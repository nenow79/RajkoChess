import unittest

from chess_logic.openings import identify_opening


class OpeningIdentificationTests(unittest.TestCase):
    def test_longest_matching_catalog_line_is_selected(self):
        opening = identify_opening(
            ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6", "b5a4"]
        )

        self.assertIsNotNone(opening)
        assert opening is not None
        self.assertTrue(opening["name"].startswith("Ruy Lopez"))

    def test_unknown_sequence_has_no_catalog_match(self):
        self.assertIsNone(identify_opening(["a1a8"]))


if __name__ == "__main__":
    unittest.main()
