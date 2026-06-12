#!/usr/bin/env python3
import multiprocessing as mp
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import sudoku

ROOT = Path(__file__).resolve().parent
SOLVE_TIMEOUT = 1.0


def _solve_worker(puzzle, conn):
    try:
        conn.send(sudoku.solve(puzzle))
    except Exception as exc:
        conn.send(exc)


def solve_with_timeout(puzzle, timeout=SOLVE_TIMEOUT):
    """Solve a puzzle, failing if it takes longer than timeout seconds."""
    ctx = mp.get_context("spawn")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_solve_worker, args=(puzzle, child_conn))
    proc.start()
    child_conn.close()
    proc.join(timeout)
    if proc.is_alive():
        proc.terminate()
        proc.join()
        raise TimeoutError(f"solving exceeded {timeout:g} second(s)")
    if parent_conn.poll():
        result = parent_conn.recv()
        if isinstance(result, Exception):
            raise result
        return result
    raise RuntimeError("solver exited without returning a result")


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
                solved, result = solve_with_timeout(puzzle)
                self.assertTrue(solved)
                self.assertNotIn(".", result)
                self.assertTrue(is_valid_solution(result))


class TestShortHardPuzzles(unittest.TestCase):
    EXPECTED_SOLUTIONS = {
        "........8.....8..18....2.34...78561.61729438558.31674....853496348629157965...823": (
            "154937268236548971879162534493785612617294385582316749721853496348629157965471823"
        ),
        ".....1........5..16158.234.82165.4.3543..861.967314..875.1.3...39.5.61..186.4..35": (
            "438961752279435861615872349821657493543298617967314528754123986392586174186749235"
        ),
        "..2.1...3..3.....11.892374.874.9213..951...7..167......213.9487.872413.9439.78.12": (
            "742815693953467821168923745874592136395186274216734958621359487587241369439678512"
        ),
        ".....1...........11.8723.4.813.74.2.2753..41.4961.27.3.41238.97.8794.132329.178.4": (
            "762491358934865271158723649813674925275389416496152783641238597587946132329517864"
        ),
        ".....1...........11.8923.4.873.14.292153..47.4967.21.3.49238.1..8714.932321...8.4": (
            "962471358734865291158923647873614529215389476496752183649238715587146932321597864"
        ),
        ".3......2.2..3...1.714.283.1.72483..24956371838....42.8.2..41.34.3.21.8771.38.2.4": (
            "938157642524836971671492835167248359249563718385719426852974163493621587716385294"
        ),
        "..1..............1..21.3..4....31.2.....56.1.16.27.......31.54.5137.4...489562137": (
            "631947285894625371752183694945831726327456918168279453276318549513794862489562137"
        ),
        "5....1........5..11.26.35.4.613.945292..54163453216789..549.21621956.34.64.132..5": (
            "584921637396745821172683594861379452927854163453216789735498216219567348648132975"
        ),
        ".....1........5..1.126.35.46.13.945229..54163534216789...49.21612956.34.46.132..5": (
            "853941627946725831712683594681379452297854163534216789375498216129567348468132975"
        ),
        ".....1...........11.2..3..4623...157891735462475612.....4197286786324915219856743": (
            "348571629967248531152963874623489157891735462475612398534197286786324915219856743"
        ),
    }

    def test_solver_handles_hard_set(self):
        puzzles = load_puzzles("short_hard.txt")
        self.assertEqual(len(puzzles), 10)

        for puzzle in puzzles:
            solved, result = solve_with_timeout(puzzle)
            with self.subTest(puzzle=puzzle):
                self.assertTrue(solved)
                self.assertEqual(result, self.EXPECTED_SOLUTIONS[puzzle])
                self.assertTrue(is_valid_solution(result))


SOLVERS_BEFORE_KITES = (
    sudoku.find_singles,
    sudoku.find_unaries,
    sudoku.find_locked,
    sudoku.find_boxline,
    sudoku.find_linebox,
    sudoku.find_fish,
    sudoku.find_skyscrapers,
)

SOLVERS_BEFORE_XYWINGS = SOLVERS_BEFORE_KITES + (sudoku.find_xywing,)


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


class TestFindXywing(unittest.TestCase):
    def test_find_xywing_eliminates_from_wing_overlap(self):
        """Synthetic XY-wing: pivot 1/3, wings 1/5 and 3/5, target sees both."""
        unknowns = sudoku.Unknowns()
        specs = {
            0: {1, 3},     # pivot (0,0)
            5: {1, 5},     # wing XZ (0,5)
            45: {3, 5},    # wing YZ (5,0)
            50: {5, 7},    # overlap target (5,5) sees both wings
        }
        for idx, cands in specs.items():
            unknowns.add(sudoku.CSet(cands, idx))

        target = unknowns.by_idx[50]
        self.assertIn(5, target)

        self.assertTrue(sudoku.find_xywing([0] * 81, unknowns))
        self.assertNotIn(5, target)

    def test_find_xywing_rejects_wings_that_see_each_other(self):
        """Wings in the same box cannot form an XY-wing."""
        unknowns = sudoku.Unknowns()
        specs = {
            0: {1, 3},
            1: {1, 5},
            2: {3, 5},
            11: {5, 7},
        }
        for idx, cands in specs.items():
            unknowns.add(sudoku.CSet(cands, idx))

        self.assertFalse(sudoku.find_xywing([0] * 81, unknowns))


class TestFindColoring(unittest.TestCase):
    COLORING_PUZZLE = (
        "........8.....8..18....2.34...78561.61729438558.31674....853496348629157965...823"
    )
    COLORING_TARGET_IDX = 3

    def test_find_coloring_eliminates_from_odd_chain_endpoints(self):
        """Real puzzle where an odd chain removes 1 from a witness cell."""
        known = sudoku.parse_puzzle(self.COLORING_PUZZLE)
        unknowns = sudoku.create_unknowns(known)
        run_solvers_to_fixpoint(SOLVERS_BEFORE_XYWINGS, known, unknowns)
        target = unknowns.by_idx[self.COLORING_TARGET_IDX]

        self.assertIn(1, target)
        self.assertTrue(sudoku.find_coloring(known, unknowns))
        self.assertTrue(sudoku.find_coloring(known, unknowns))
        self.assertNotIn(1, target)

    def test_find_coloring_needs_odd_chain_length(self):
        """A two-node bilocal strong link is too short to eliminate."""
        unknowns = sudoku.Unknowns()
        specs = {
            0: {5, 1},
            1: {5, 2},
        }
        for idx, cands in specs.items():
            unknowns.add(sudoku.CSet(cands, idx))

        self.assertFalse(sudoku.find_coloring([0] * 81, unknowns))


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
        good = load_puzzles("short.txt")[0]
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=ROOT, delete=False, suffix=".txt"
        ) as handle:
            handle.write(f"{good}\n{'.' * 81}\n")
            fail_file = Path(handle.name).name
        try:
            result = self.run_cli(fail_file)
        finally:
            (ROOT / fail_file).unlink(missing_ok=True)
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
