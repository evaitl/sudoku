#!/usr/bin/env python3
import unittest
from pathlib import Path

import sudoku

ROOT = Path(__file__).resolve().parent


def load_puzzles(filename):
    path = ROOT / filename
    with path.open() as f:
        return [line.strip() for line in f if line.strip()]


def is_valid_solution(grid):
    if len(grid) != 81 or not grid.isdigit():
        return False

    digits = [int(ch) for ch in grid]
    for i in range(9):
        row = digits[i * 9 : (i + 1) * 9]
        if sorted(row) != list(range(1, 10)):
            return False

    for col in range(9):
        column = [digits[row * 9 + col] for row in range(9)]
        if sorted(column) != list(range(1, 10)):
            return False

    for box in range(9):
        br, bc = box // 3 * 3, box % 3 * 3
        cells = [
            digits[(br + dr) * 9 + bc + dc]
            for dr in range(3)
            for dc in range(3)
        ]
        if sorted(cells) != list(range(1, 10)):
            return False

    return True


class TestShortPuzzles(unittest.TestCase):
    def test_all_puzzles_solve(self):
        puzzles = load_puzzles("short.txt")
        self.assertEqual(len(puzzles), 10)

        for puzzle in puzzles:
            with self.subTest(puzzle=puzzle):
                solved, result = sudoku.solve(puzzle)
                self.assertTrue(solved)
                self.assertNotIn(".", result)
                self.assertTrue(is_valid_solution(result))


class TestShortHardPuzzles(unittest.TestCase):
    EXPECTED_SOLUTIONS = {
        "..2.1...3..3.....11.892374.874.9213..951...7..167......213.9487.872413.9439.78.12": (
            "742815693953467821168923745874592136395186274216734958621359487587241369439678512"
        ),
        ".....1...........11.8923.4.873.14.292153..47.4967.21.3.49238.1..8714.932321...8.4": (
            "962471358734865291158923647873614529215389476496752183649238715587146932321597864"
        ),
        "..1..............1..21.3..4....31.2.....56.1.16.27.......31.54.5137.4...489562137": (
            "631947285894625371752183694945831726327456918168279453276318549513794862489562137"
        ),
    }

    def test_solver_handles_hard_set(self):
        puzzles = load_puzzles("short_hard.txt")
        self.assertEqual(len(puzzles), 10)

        passes = 0
        fails = 0
        for puzzle in puzzles:
            solved, result = sudoku.solve(puzzle)
            if solved:
                passes += 1
            else:
                fails += 1

            with self.subTest(puzzle=puzzle):
                if puzzle in self.EXPECTED_SOLUTIONS:
                    self.assertTrue(solved)
                    self.assertEqual(result, self.EXPECTED_SOLUTIONS[puzzle])
                    self.assertTrue(is_valid_solution(result))
                else:
                    self.assertFalse(solved)
                    self.assertIn(".", result)

        self.assertEqual(passes, len(self.EXPECTED_SOLUTIONS))
        self.assertEqual(fails, len(puzzles) - len(self.EXPECTED_SOLUTIONS))


class TestParseAndValidate(unittest.TestCase):
    def test_parse_puzzle_accepts_dots(self):
        puzzle = "." * 80 + "1"
        self.assertEqual(sudoku.parse_puzzle(puzzle), [0] * 80 + [1])

    def test_parse_puzzle_accepts_asterisks(self):
        puzzle = "*" * 80 + "1"
        self.assertEqual(sudoku.parse_puzzle(puzzle), [0] * 80 + [1])

    def test_parse_puzzle_rejects_invalid_characters(self):
        puzzle = "." * 40 + "x" + "." * 40
        with self.assertRaisesRegex(ValueError, "invalid character 'x' at position 40"):
            sudoku.parse_puzzle(puzzle)

    def test_validate_puzzle_rejects_duplicate_in_row(self):
        puzzle = "1" + "." * 80
        known = sudoku.parse_puzzle(puzzle)
        known[1] = 1
        with self.assertRaises(ValueError):
            sudoku.validate_puzzle(known)


if __name__ == "__main__":
    unittest.main()
