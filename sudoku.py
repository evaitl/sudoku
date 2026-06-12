#!/usr/bin/env python3
import functools
import itertools
import argparse
import logging
import sys

log = logging.getLogger(__name__)

DEBUG_SECTIONS = frozenset({ "solve", "assign", "solver", "singles",
                             "unaries", "locked", "boxline", "linebox",
                             "elim","fish", "skyscraper", "kite",
                             "crane",})
_debug_sections = None


class SectionFilter(logging.Filter):
    def filter(self, record):
        if _debug_sections is None:
            return True
        return getattr(record, "section", None) in _debug_sections


def dbg(section, msg, *args):
    log.debug(msg, *args, extra={"section": section})


_solver_counts = {}
_solver_names = []


def count_solver(fn):
    """Decorator that counts how often a solver returns True."""
    name = fn.__name__
    _solver_names.append(name)
    _solver_counts[name] = 0

    @functools.wraps(fn)
    def wrapper(known, unknowns):
        if fn(known, unknowns):
            _solver_counts[name] += 1
            return True
        return False

    return wrapper


def reset_solver_counts():
    """Reset per-solver success counters to zero."""
    for name in _solver_names:
        _solver_counts[name] = 0


def solver_counts():
    """Return a copy of per-solver success counters."""
    return dict(_solver_counts)


def format_solver_counts(counts):
    """Format solver counters for display."""
    return " ".join(f"{name}={counts[name]}" for name in _solver_names)


class CSet(set):
    def __init__(self, iterable=None, idx=None):
        super().__init__(iterable)
        self.idx = idx
        self.row, self.col, self.box = get_rcb(idx)


    def _candidates_repr(self):
        if not self:
            return "{}"
        return "{" + ", ".join(str(v) for v in sorted(self)) + "}"

    def __str__(self):
        return f"CSet({self.idx}: {self._candidates_repr()})"

    def __repr__(self):
        return f"CSet({self.idx!r}, {self._candidates_repr()})"

    def __eq__(self, other):
        return self.idx == other.idx

    def __hash__(self):
        return self.idx


class Unknowns:
    """Unknown cells indexed by row, column, and box for fast unit lookup."""

    _UNITS = {"row": 0, "col": 1, "box": 2}

    def __init__(self):
        self.by_idx = {}
        self.by_unit = [[set() for _ in range(9)] for _ in range(3)]

    def add(self, cset):
        self.by_idx[cset.idx] = cset
        self.by_unit[0][cset.row].add(cset)
        self.by_unit[1][cset.col].add(cset)
        self.by_unit[2][cset.box].add(cset)

    def pop(self, idx):
        cset = self.by_idx.pop(idx)
        self.by_unit[0][cset.row].discard(cset)
        self.by_unit[1][cset.col].discard(cset)
        self.by_unit[2][cset.box].discard(cset)
        return cset

    def unit(self, attr, n):
        """Return the set of unknown CSets in row, col, or box n."""
        return self.by_unit[self._UNITS[attr]][n]

    def row(self, r):
        return self.by_unit[0][r]

    def col(self, c):
        return self.by_unit[1][c]

    def box(self, b):
        return self.by_unit[2][b]

    def peers(self, row, col, box):
        """Unknown CSets sharing a row, column, or box."""
        return self.row(row) | self.col(col) | self.box(box)

    def linked(self, cset):
        """Unknown CSets that see cset (same row, column, or box), excluding cset."""
        return self.peers(cset.row, cset.col, cset.box) - {cset}

    def __len__(self):
        return len(self.by_idx)

    def __iter__(self):
        return iter(self.by_idx.values())

    def values(self):
        return self.by_idx.values()


def box_format(known):
    """Format a grid as nine rows of digits and dots."""
    return '\n'.join(
        ''.join(str(known[j]) if known[j] else '.' for j in range(i, i + 9))
        for i in range(0, 81, 9)
    )

def get_rcb(idx):
    """Return row, column, and box indices for a cell index (0-80)."""
    r = idx // 9
    c = idx % 9
    b = c // 3 + r // 3 * 3
    return r, c, b


def add_known(known, unknowns, idx, value):
    """Assign a value to a cell and remove it from peer candidates."""
    row, col, box = get_rcb(idx)
    unknowns.pop(idx)
    known[idx] = value
    dbg("assign", "known[%d] = %d", idx, value)
    for u in unknowns.peers(row, col, box):
        if value in u:
            u -= {value}
            if len(u) == 0:
                print(f'error at {u.idx}: {known}\n{unknowns.by_idx}\n')
            assert len(u)


def elim_values(vi, gi):
    """Remove values from candidate sets. Return True if any candidate changed."""
    ret = False
    try:
        gl = list(gi)
    except TypeError:
        gl = [gi]
    try:
        vl = list(vi)
    except TypeError:
        vl = [vi]
    for v in vl:
        for u in gl:
            if v in u:
                ret = True
                u.discard(v)
                dbg("elim", "removed %d from %s", v, u)
                assert len(u)
    return ret


@count_solver
def find_singles(known, unknowns):
    """Assign cells with only one remaining candidate. Return True if one was found."""
    for u in unknowns:
        if len(u) == 1:
            dbg("singles", "found single %s", u)
            add_known(known, unknowns, u.idx, next(iter(u)))
            return True
    return False


@count_solver
def find_unaries(known, unknowns):
    """Assign cells that alone hold a value in their row, column, or box."""
    for attr in ("row", "col", "box"):
        for unit_idx in range(9):
            cells = unknowns.unit(attr, unit_idx)
            if len(cells) < 2:
                continue
            for digit in range(1, 10):
                holder = None
                for u in cells:
                    if digit not in u:
                        continue
                    if holder is not None:
                        holder = None
                        break
                    holder = u
                if holder is not None:
                    dbg(
                        "unaries",
                        "found unary %s %d=%d at %d",
                        attr, unit_idx, digit, holder.idx,
                    )
                    add_known(known, unknowns, holder.idx, digit)
                    return True
    return False


@count_solver
def find_locked(_known, unknowns):
    """Naked pairs, triples, and quads in rows, columns, or boxes.

    When N cells in a unit share exactly N candidates, remove those
    candidates from the other cells in the unit.
    """
    for attr in ("row", "col", "box"):
        for unit in range(9):
            cells = list(unknowns.unit(attr, unit))
            for group_size in range(2, min(5, len(cells))):
                for group in itertools.combinations(cells, group_size):
                    values = set.union(*group)
                    if len(values) != group_size:
                        continue
                    others = [u for u in cells if u not in group]
                    if elim_values(values, others):
                        dbg("locked", "%s %d size %d cells %s values %s",
                            attr, unit, group_size, [u.idx for u in group], values)
                        return True
    return False


@count_solver
def find_boxline(_known, unknowns):
    """Box/line reduction (locked candidates type 1).

    When a digit appears in only one row or column within a box, remove it
    from that row or column in the other boxes.
    """
    for u in unknowns:
        for v in u:
            if not any(u2.row != u.row and v in u2 for u2 in unknowns.box(u.box)):
                if elim_values(v, [u2 for u2 in unknowns.row(u.row) if u2.box != u.box]):
                    dbg("boxline", "row %d value %d in box %d", u.row, v, u.box)
                    return True
            if not any(u2.col != u.col and v in u2 for u2 in unknowns.box(u.box)):
                if elim_values(v, [u2 for u2 in unknowns.col(u.col) if u2.box != u.box]):
                    dbg("boxline", "col %d value %d in box %d", u.col, v, u.box)
                    return True
    return False


@count_solver
def find_linebox(_known, unknowns):
    """Row/column claiming (locked candidates type 2).

    When a digit appears in only one box along a row or column, remove it
    from the other rows or columns of that box.
    """
    for u in unknowns:
        for v in u:
            if not any(u2.box != u.box and v in u2 for u2 in unknowns.row(u.row)):
                if elim_values(v, [u2 for u2 in unknowns.box(u.box) if u2.row != u.row]):
                    dbg("linebox", "row %d value %d in box %d", u.row, v, u.box)
                    return True
            if not any(u2.box != u.box and v in u2 for u2 in unknowns.col(u.col)):
                if elim_values(v, [u2 for u2 in unknowns.box(u.box) if u2.col != u.col]):
                    dbg("linebox", "col %d value %d in box %d", u.col, v, u.box)
                    return True
    return False


@count_solver
def find_fish(_known, unknowns):
    """xwing, swordfish, etcetera

    A 2x2 is xwing. A 3x3 is swordfish. No idea what 4 or more are
    called. We could actually do 1x1 here, but that should be picked
    up earlier.
    """
    row_cells = [unknowns.row(r) for r in range(9)]
    active_rows = tuple(r for r in range(9) if row_cells[r])
    if len(active_rows) < 2:
        return False

    row_digit_cols = [[set() for _ in range(10)] for _ in range(9)]
    for r in range(9):
        for u in row_cells[r]:
            for digit in u:
                row_digit_cols[r][digit].add(u.col)

    for fish_size in range(2, 9):
        for rows in itertools.combinations(active_rows, fish_size):
            rows_set = frozenset(rows)
            for digit in range(1, 10):
                col_set = set()
                for row in rows:
                    cols = row_digit_cols[row][digit]
                    if not cols:
                        break
                    col_set |= cols
                else:
                    if len(col_set) != fish_size:
                        continue
                    remove_set = [
                        u for col in col_set
                        for u in unknowns.col(col)
                        if u.row not in rows_set and digit in u
                    ]
                    if elim_values(digit, remove_set):
                        dbg(
                            "fish",
                            "fish: fish_size=%d digit=%d rows=%s col_set=%s",
                            fish_size, digit, rows, col_set,
                        )
                        return True
    return False


@count_solver
def find_skyscrapers(_known, unknowns):
    """Skyscrapers

    https://sudoku.coach/en/learn/skyscraper
    """
    def value_pair(attr, unit, v):
        """Return the two unknowns with v in row/col unit, or None."""
        cells = [u for u in unknowns.unit(attr, unit) if v in u]
        return cells if len(cells) == 2 else None

    def strong_in(attr, u, v):
        """True when u's row/col contains exactly two candidates for v."""
        return sum(1 for o in unknowns.unit(attr, getattr(u, attr)) if v in o) == 2

    def other_link(link_attr, u, v):
        """Other unknowns sharing u's row/col strong link for v."""
        return [o for o in unknowns.unit(link_attr, getattr(u, link_attr))
                if o.idx != u.idx and v in o]

    for base, link in (("row", "col"), ("col", "row")):
        for unit in range(9):
            for v in range(1, 10):
                pair = value_pair(base, unit, v)
                if not pair or not all(strong_in(link, u, v) for u in pair):
                    continue
                for s1 in other_link(link, pair[0], v):
                    for s2 in other_link(link, pair[1], v):
                        if getattr(s1, base) == getattr(s2, base):
                            continue
                        intersection = (unknowns.linked(s1) & unknowns.linked(s2)) - set(pair)
                        if elim_values(v, intersection):
                            dbg(
                                "skyscraper",
                                "skyscraper: v=%d pair=%s s1=%s s2=%s",
                                v, pair, s1, s2,
                            )
                            return True
    return False



@count_solver
def find_kites(_known, unknowns):
    """Two-string kites.

    https://sudoku.coach/en/learn/two-string-kite

    A row strong link for a digit links to a column strong link in the
    same box through a box-corner cell. Eliminate that digit from the
    cell where the row-far column meets the column-far row.
    """
    def try_elimination(row_near, row_far, box_corner, col_far, digit):
        targets = unknowns.col(row_far.col) & unknowns.row(col_far.row)
        if elim_values(digit, targets):
            dbg(
                "kite",
                "kite: digit=%d row_near=%s row_far=%s box_corner=%s col_far=%s",
                digit, row_near, row_far, box_corner, col_far,
            )
            return True
        return False

    for row in range(9):
        for digit in range(1, 10):
            row_holders = [u for u in unknowns.row(row) if digit in u]
            if len(row_holders) != 2:
                continue
            for row_near, row_far in (
                (row_holders[0], row_holders[1]),
                (row_holders[1], row_holders[0]),
            ):
                if row_near.box == row_far.box:
                    continue
                for box_corner in unknowns.box(row_near.box) - {row_near}:
                    if digit not in box_corner:
                        continue
                    col_holders = [u for u in unknowns.col(box_corner.col) if digit in u]
                    if len(col_holders) != 2:
                        continue
                    for col_far in col_holders:
                        if col_far is box_corner or col_far.box == box_corner.box:
                            continue
                        if try_elimination(
                            row_near, row_far, box_corner, col_far, digit
                        ):
                            return True
    return False

@count_solver
def find_crane(_known, unknowns):
    """Cranes (strong-weak-strong chain).

    https://sudoku.coach/en/learn/crane

    end_a and end_d are the outer endpoints of a strong-weak-strong chain for
    digit v. Eliminate v from unknown cells that see both endpoints.
    """
    def digit_holders(cells, digit):
        return [cell for cell in cells if digit in cell]

    def strong_link(cells, left, right, digit):
        holders = digit_holders(cells, digit)
        return len(holders) == 2 and left in holders and right in holders

    def weak_box_link(mid_b, mid_c, digit):
        if mid_b.box != mid_c.box or digit not in mid_b or digit not in mid_c:
            return False
        if mid_b.row == mid_c.row:
            return len(digit_holders(unknowns.row(mid_b.row), digit)) > 2
        if mid_b.col == mid_c.col:
            return len(digit_holders(unknowns.col(mid_b.col), digit)) > 2
        return True

    def try_elimination(end_a, end_d, chain, digit):
        targets = {
            cell for cell in unknowns.linked(end_a) & unknowns.linked(end_d)
            if digit in cell
        } - chain
        if elim_values(digit, targets):
            dbg(
                "crane",
                "crane: digit=%d end_a=%s end_d=%s targets=%s",
                digit, end_a, end_d, targets,
            )
            return True
        return False

    for end_a in unknowns.values():
        if len(end_a) != 2:
            continue
        for mid_b in unknowns.linked(end_a):
            if len(mid_b) != 2 or len(end_a & mid_b) != 2:
                continue
            for mid_c in unknowns.linked(mid_b) - {end_a}:
                if len(mid_c) != 2 or len(mid_b & mid_c) != 1:
                    continue
                digit = next(iter(mid_b & mid_c))
                if not any(
                    strong_link(unknowns.unit(unit, getattr(end_a, unit)), end_a, mid_b, digit)
                    for unit in ("row", "col")
                ):
                    continue
                if not weak_box_link(mid_b, mid_c, digit):
                    continue
                for end_d in unknowns.linked(mid_c) - {end_a, mid_b}:
                    if digit not in end_d:
                        continue
                    if end_d not in unknowns.linked(end_a):
                        continue
                    if not any(
                        strong_link(unknowns.unit(unit, getattr(mid_c, unit)), mid_c, end_d, digit)
                        for unit in ("row", "col", "box")
                    ):
                        continue
                    chain = {end_a, mid_b, mid_c, end_d}
                    if try_elimination(end_a, end_d, chain, digit):
                        return True
    return False


SOLVERS = (
    find_singles,
    find_unaries,
    find_locked,
    find_boxline,
    find_linebox,
    find_fish,
    find_skyscrapers,
    find_kites,
    find_crane,
)


def parse_puzzle(puzzle):
    """Parse an 81-character puzzle string into a list of cell values (0 for empty)."""
    line = puzzle.strip()
    if len(line) != 81:
        raise ValueError(f"expected 81 characters, got {len(line)}")
    known = []
    for i, ch in enumerate(line):
        if ch in ".*":
            known.append(0)
        elif ch in "123456789":
            known.append(int(ch))
        else:
            raise ValueError(f"invalid character {ch!r} at position {i}")
    return known


def _check_no_duplicates(values, label):
    seen = set()
    for v in values:
        if not v:
            continue
        if v in seen:
            raise ValueError(f"conflict: {v} appears twice in {label}")
        seen.add(v)


def validate_puzzle(known):
    """Raise ValueError if initial clues conflict within a row, column, or box."""
    for r in range(9):
        _check_no_duplicates(
            (known[r * 9 + c] for c in range(9)), f"row {r}"
        )

    for c in range(9):
        _check_no_duplicates(
            (known[r * 9 + c] for r in range(9)), f"column {c}"
        )

    for b in range(9):
        br, bc = b // 3 * 3, b % 3 * 3
        _check_no_duplicates(
            (known[(br + dr) * 9 + bc + dc] for dr in range(3) for dc in range(3)),
            f"box {b}",
        )


def create_unknowns(known):
    """Build candidate sets for empty cells, applying initial clue constraints."""
    unknowns = Unknowns()
    for i in range(81):
        unknowns.add(CSet(range(1, 10), i))
    for idx, v in enumerate(known):
        if v:
            add_known(known, unknowns, idx, v)

    return unknowns


def format_known(known):
    """Serialize a grid as an 81-character string (dots for empty cells)."""
    return "".join(str(v) if v else "." for v in known)


def run_solvers(solvers, known, unknowns):
    """Run solvers in order until one makes progress. Return True if a solver succeeded."""
    for s in solvers:
        dbg("solver", "calling %s", s.__name__)
        if s(known, unknowns):
            assert all(len(u) > 0 for u in unknowns)
            return True
    return False


def solve(puzzle):
    """Solve a puzzle using logical deduction.

    Return (solved, grid) where solved is True when every cell is filled.
    """
    reset_solver_counts()
    known = parse_puzzle(puzzle)
    validate_puzzle(known)
    unknowns = create_unknowns(known)
    assert all(len(u) > 0 for u in unknowns)
    dbg("solve", "solving:\n%s", box_format(known))
    while len(unknowns) and run_solvers(SOLVERS, known, unknowns):
        if not all(len(u) > 0 for u in unknowns):
            sys.stderr.write(f'Internal error with line\n{puzzle}\n{format_known(known)}\n')
            break
    solved = len(unknowns) == 0
    dbg("solve", "result %s, %d unknowns remaining:\n%s",
        "solved" if solved else "unsolved", len(unknowns), box_format(known))
    return (solved, format_known(known))


def main():
    parser = argparse.ArgumentParser(description="Solve sudoku puzzles from a file.")
    parser.add_argument(
        "input_file", help="file with one puzzle per line (81 chars; . or * for empty)"
    )
    parser.add_argument(
        "output_file", nargs="?", help="optional file to write solutions"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="enable debug logging on stderr"
    )
    parser.add_argument(
        "--debug-section", action="append", metavar="SECTION",
        choices=sorted(DEBUG_SECTIONS),
        help="limit debug output to SECTION (repeatable; implies -d)",
    )
    args = parser.parse_args()

    global _debug_sections
    if args.debug_section:
        _debug_sections = set(args.debug_section)
    if args.debug or args.debug_section:
        handler = logging.StreamHandler(sys.stderr)
        handler.addFilter(SectionFilter())
        handler.setFormatter(logging.Formatter("[%(section)s] %(message)s"))
        logging.basicConfig(level=logging.DEBUG, handlers=[handler], force=True)

    results = []
    batch_solver_counts = {name: 0 for name in _solver_names}
    with open(args.input_file, encoding="utf-8") as f:
        passes,fails=0,0
        for line in f:
            line = line.strip()
            if not line:
                continue

            r=solve(line)
            puzzle_counts = solver_counts()
            counts = format_solver_counts(puzzle_counts)
            for name, count in puzzle_counts.items():
                batch_solver_counts[name] += count
            if not r[0]:
                fails+=1
                results.append(f'failed:\ni={line}\no={r[1]}\nc={counts}')
            else:
                passes+=1
                results.append(f'passed:\ni={line}\no={r[1]}\nc={counts}')

    results.append(f'{passes=} {fails=}')
    results.append(format_solver_counts(batch_solver_counts))
    output = "\n".join(results)
    if output:
        output += "\n"
    if args.output_file:
        with open(args.output_file, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        sys.stdout.write(output)

    if fails:
        sys.exit(1)


if __name__ == "__main__":
    main()
