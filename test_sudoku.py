#!/usr/bin/env python3
import subprocess
import sys
import unittest
from pathlib import Path

import sudoku

ROOT = Path(__file__).resolve().parent


def load_puzzles(filename):
    path = ROOT / filename
    with path.open(encoding="utf-8") as f:
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
        ".....1........5..16158.234.82165.4.3543..861.967314..875.1.3...39.5.61..186.4..35": (
            "438961752279435861615872349821657493543298617967314528754123986392586174186749235"
        ),
        ".....1...........11.8723.4.813.74.2.2753..41.4961.27.3.41238.97.8794.132329.178.4": (
            "762491358934865271158723649813674925275389416496152783641238597587946132329517864"
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


SOLVERS_BEFORE_KITES = (
    sudoku.find_singles,
    sudoku.find_unaries,
    sudoku.find_locked,
    sudoku.find_boxline,
    sudoku.find_linebox,
    sudoku.find_fish,
    sudoku.find_skyscrapers,
)

SOLVERS_BEFORE_CRANES = SOLVERS_BEFORE_KITES + (sudoku.find_kites,)


def run_solvers_to_fixpoint(solvers, known, unknowns):
    while sudoku.run_solvers(solvers, known, unknowns):
        pass


class TestFindKites(unittest.TestCase):
    KITE_PUZZLE = (
        ".....1........5..16158.234.82165.4.3543..861.967314..875.1.3...39.5.61..186.4..35"
    )
    KITE_TARGET_IDX = 34
    KITE_ROW_NEAR_IDX = 67

    def _prepare_for_kites(self):
        known = sudoku.parse_puzzle(self.KITE_PUZZLE)
        unknowns = sudoku.create_unknowns(known)
        run_solvers_to_fixpoint(SOLVERS_BEFORE_KITES, known, unknowns)
        return known, unknowns

    def test_find_kites_eliminates_at_row_col_intersection(self):
        known, unknowns = self._prepare_for_kites()
        target = unknowns.by_idx[self.KITE_TARGET_IDX]
        self.assertEqual(set(target), {7, 9})

        self.assertTrue(sudoku.find_kites(known, unknowns))
        self.assertEqual(set(target), {9})

    def test_find_kites_accepts_row_strong_link_without_naked_pair(self):
        known, unknowns = self._prepare_for_kites()
        row_near = unknowns.by_idx[self.KITE_ROW_NEAR_IDX]
        row_near.add(2)
        self.assertEqual(set(row_near), {2, 7, 8})

        target = unknowns.by_idx[self.KITE_TARGET_IDX]
        self.assertTrue(sudoku.find_kites(known, unknowns))
        self.assertEqual(set(target), {9})


class TestFindCrane(unittest.TestCase):
    CRANE_PUZZLE = (
        ".....1...........11.8923.4.873.14.292153..47.4967.21.3.49238.1..8714.932321...8.4"
    )
    CRANE_TARGET_IDXS = (4, 13)
    CRANE_END_A_IDX = 49
    CRANE_END_D_IDX = 40

    def test_find_crane_eliminates_on_short_hard_puzzle_5(self):
        """Real puzzle where crane fires on the initial candidate grid."""
        known = sudoku.parse_puzzle(self.CRANE_PUZZLE)
        unknowns = sudoku.create_unknowns(known)
        targets = [unknowns.by_idx[i] for i in self.CRANE_TARGET_IDXS]
        end_a = unknowns.by_idx[self.CRANE_END_A_IDX]
        end_d = unknowns.by_idx[self.CRANE_END_D_IDX]

        for target in targets:
            self.assertIn(8, target)
        self.assertIn(8, end_a)
        self.assertIn(8, end_d)

        self.assertTrue(sudoku.find_crane(known, unknowns))

        for target in targets:
            self.assertNotIn(8, target)
        self.assertIn(8, end_a)
        self.assertIn(8, end_d)

    def test_find_crane_eliminates_from_endpoint_overlap_not_end_d(self):
        """Synthetic strong-weak-strong chain for digit 8."""
        unknowns = sudoku.Unknowns()
        specs = {
            0: {8, 1},    # end_a (0,0)
            2: {8, 1},    # mid_b (0,2) row strong link with end_a
            18: {8, 2},   # mid_c (2,0) weak box link with mid_b
            20: {8, 2},   # end_d (2,2) row strong link with mid_c
            11: {8, 3},   # overlap target sees end_a and end_d
        }
        for idx, cands in specs.items():
            unknowns.add(sudoku.CSet(cands, idx))

        end_d = unknowns.by_idx[20]
        target = unknowns.by_idx[11]
        self.assertIn(8, end_d)
        self.assertIn(8, target)

        self.assertTrue(sudoku.find_crane([0] * 81, unknowns))
        self.assertIn(8, end_d)
        self.assertNotIn(8, target)

    def test_find_crane_rejects_invalid_column_tail(self):
        """Column with three holders is not a strong link for the tail."""
        known = sudoku.parse_puzzle(
            "........8.....8..18....2.34...78561.61729438558.31674....853496348629157965...823"
        )
        unknowns = sudoku.create_unknowns(known)
        run_solvers_to_fixpoint(SOLVERS_BEFORE_CRANES, known, unknowns)
        self.assertFalse(sudoku.find_crane(known, unknowns))


class TestCliExitCode(unittest.TestCase):
    SUDOKU = ROOT / "sudoku.py"

    def run_cli(self, input_file):
        return subprocess.run(
            [sys.executable, str(self.SUDOKU), str(ROOT / input_file)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_exits_zero_when_all_puzzles_solve(self):
        result = self.run_cli("short.txt")
        self.assertEqual(result.returncode, 0)

    def test_exits_one_when_any_puzzle_fails(self):
        result = self.run_cli("short_hard.txt")
        self.assertEqual(result.returncode, 1)


class TestParseAndValidate(unittest.TestCase):
    def test_parse_puzzle_accepts_dots(self):
        puzzle = "." * 80 + "1"
        self.assertEqual(sudoku.parse_puzzle(puzzle), [0] * 80 + [1])

    def test_parse_puzzle_accepts_asterisks(self):
        puzzle = "*" * 80 + "1"
        self.assertEqual(sudoku.parse_puzzle(puzzle), [0] * 80 + [1])

    def test_parse_puzzle_rejects_wrong_length(self):
        with self.assertRaisesRegex(ValueError, "expected 81 characters, got 80"):
            sudoku.parse_puzzle("." * 80)

    def test_parse_puzzle_rejects_invalid_characters(self):
        puzzle = "." * 40 + "x" + "." * 40
        with self.assertRaisesRegex(ValueError, "invalid character 'x' at position 40"):
            sudoku.parse_puzzle(puzzle)

    def test_validate_puzzle_rejects_duplicate_in_row(self):
        puzzle = "1" + "." * 80
        known = sudoku.parse_puzzle(puzzle)
        known[1] = 1
        with self.assertRaisesRegex(ValueError, "conflict: 1 appears twice in row 0"):
            sudoku.validate_puzzle(known)

    def test_validate_puzzle_rejects_duplicate_in_column(self):
        puzzle = "1" + "." * 80
        known = sudoku.parse_puzzle(puzzle)
        known[9] = 1
        with self.assertRaisesRegex(ValueError, "conflict: 1 appears twice in column 0"):
            sudoku.validate_puzzle(known)

    def test_validate_puzzle_rejects_duplicate_in_box(self):
        puzzle = "1" + "." * 80
        known = sudoku.parse_puzzle(puzzle)
        known[10] = 1
        with self.assertRaisesRegex(ValueError, "conflict: 1 appears twice in box 0"):
            sudoku.validate_puzzle(known)


if __name__ == "__main__":
    unittest.main()
