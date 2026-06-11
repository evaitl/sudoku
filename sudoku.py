#!/usr/bin/env python3
import itertools
import argparse
import logging
import sys

log = logging.getLogger(__name__)

DEBUG_SECTIONS = frozenset({ "solve", "assign", "solver", "singles",
                             "unaries", "locked", "boxex", "rcex", "elim","fish",
                             "skyscraper" })
_debug_sections = None


class SectionFilter(logging.Filter):
    def filter(self, record):
        if _debug_sections is None:
            return True
        return getattr(record, "section", None) in _debug_sections


def dbg(section, msg, *args):
    log.debug(msg, *args, extra={"section": section})


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

def box_format(known):
    """Format a grid as nine rows of digits and dots."""
    return '\n'.join(''.join(str(known[j]) if known[j] else '.' for j in range(i, i+9)) for i in range(0,81,9))

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
    for u in [u for u in unknowns.values() if (u.row == row or u.col == col or u.box == box) and value in u]:
        u -= {value}
        if len(u)==0:
            print(f'error at {u.idx}: {known}\n{unknowns}\n')
        assert len(u)

def find_singles(known, unknowns):
    """Assign cells with only one remaining candidate. Return True if one was found."""
    for u in unknowns.values():
        if len(u) == 1:
            dbg("singles", "found single %s", u)
            add_known(known, unknowns, u.idx, next(iter(u)))
            return True
    return False


def peer_candidates(unknowns, u, attr):
    """Union of candidates from other unknowns in u's row, col, or box."""
    mine = getattr(u, attr)
    return set().union(*(o for o in unknowns.values()
                         if getattr(o, attr) == mine and o.idx != u.idx))


def unit_unknowns(unknowns, u, attr):
    """Unknown cells sharing u's row, col, or box."""
    mine = getattr(u, attr)
    return [o for o in unknowns.values() if getattr(o, attr) == mine]


def find_unaries(known, unknowns):
    """Assign cells that alone hold a value in their row, column, or box."""
    for u in unknowns.values():
        for attr in ("row", "col", "box"):
            if len(unit_unknowns(unknowns, u, attr)) < 2:
                continue
            s = peer_candidates(unknowns, u, attr)
            for v in u:
                if v not in s:
                    dbg("unaries", "found unary %s %d=%d at %d",
                        attr, getattr(u, attr), v, u.idx)
                    add_known(known, unknowns, u.idx, v)
                    return True
    return False


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


def find_rcex(known, unknowns):
    """Row/column claiming (locked candidates type 2).

    When a digit appears in only one box along a row or column, remove it
    from the other rows or columns of that box.
    """
    for u in unknowns.values():
        for v in u:
            if not any( 1 for u2 in unknowns.values() if u2.box !=
                        u.box and u.row == u2.row and v in u2 ):
                if elim_values(v, [u2 for u2 in unknowns.values() if u2.box ==
                                   u.box and u2.row != u.row] ):
                    dbg("rcex", "row %d value %d in box %d", u.row, v, u.box)
                    return True
            if not any(1 for u2 in unknowns.values() if u2.box !=
                       u.box and u.col == u2.col and v in u2 ):
                if elim_values(v, [ u2 for u2 in unknowns.values() if
                                    u2.box == u.box and u2.col !=
                                    u.col ], ):
                    dbg("rcex", "col %d value %d in box %d", u.col, v, u.box)
                    return True
    return False

        

def find_boxex(known, unknowns):
    """Box/line reduction (locked candidates type 1).

    When a digit appears in only one row or column within a box, remove it
    from that row or column in the other boxes.
    """
    for u in unknowns.values():
        for v in u:
            if not any( 1 for u2 in unknowns.values()
                        if u2.box == u.box and
                        u2.row != u.row and
                        v in u2 ):
                if elim_values(v, [ u2 for u2 in unknowns.values() if
                                    u2.box != u.box and u2.row ==
                                    u.row ]):
                    dbg("boxex", "row %d value %d in box %d", u.row, v, u.box)
                    return True
            if not any(1 for u2 in unknowns.values() if u2.box ==
                       u.box and u2.col != u.col and v in u2):
                if elim_values(v, [ u2 for u2 in unknowns.values() if
                                    u2.box != u.box and u2.col ==
                                    u.col ] ):
                    dbg("boxex", "col %d value %d in box %d", u.col, v, u.box)
                    return True
    return False

def linked_set(cs, unknowns):
    """Return a set of all candidate sets that are linked to cs
    """
    return {u for u in unknowns.values() if u.row==cs.row or u.col==cs.col or u.box==cs.box} - {cs}

def find_skyscrapers(known,unknowns):
    """

    https://sudoku.coach/en/learn/skyscraper
    """
    for row in range(9):
        for v in range(1,10):
            pair=[u for u in unknowns.values() if u.row==row and v in u]
            if len(pair)!=2:
                continue
            if sum(1 for u in unknowns.values() if u.col==pair[0].col and v in u)!=2:
                continue
            if sum(1 for u in unknowns.values() if u.col==pair[1].col and v in u)!=2:
                continue
            for s1 in [u for u in unknowns.values()
                       if u.idx != pair[0].idx and u.col==pair[0].col and v in u]:
                for s2 in [u for u in unknowns.values()
                           if u.idx != pair[1].idx and u.col == pair[1].col and v in u]:
                    if s1.row==s2.row:
                        continue                    
                    intersection = (linked_set(s1,unknowns) & linked_set(s2,unknowns))-set(pair)
                    if elim_values(v,intersection):
                        dbg("skyscraper",f'skyscraper: {v=} {pair=} {s1=} {s2=}')
                        return True
    for col in range(9):
        for v in range(1,10):
            pair=[u for u in unknowns.values() if u.col==col and v in u]
            if len(pair)!=2:
                continue
            if sum(1 for u in unknowns.values() if u.row==pair[0].row and v in u)!=2:
                continue
            if sum(1 for u in unknowns.values() if u.row==pair[1].row and v in u)!=2:
                continue
            for s1 in [u for u in unknowns.values()
                       if u.idx != pair[0].idx and u.row==pair[0].row and v in u]:
                for s2 in [u for u in unknowns.values()
                           if u.idx != pair[1].idx and u.row == pair[1].row and v in u]:
                    if s1.col==s2.col:
                        continue                    
                    intersection = (linked_set(s1,unknowns) & linked_set(s2,unknowns))-set(pair)
                    if elim_values(v,intersection):
                        dbg("skyscraper",f'skyscraper: {v=} {pair=} {s1=} {s2=}')
                        return True
    return False

def find_fish(known,unknowns):
    """xwing, swordfish, etcetera


    A 2x2 is xwing. A 3x3 is swordfish. No idea what 4 or more are
    called. We could actually do 1x1 here, but that should be picked
    up earlier.

    """
    for fish_size in range(2,9):
        for rows in itertools.combinations(range(9),fish_size):
            row_sets=[[u for u in unknowns.values() if u.row==row] for row in rows]
            for v in range(1,10):
                # A row must be nonempty for set.union to work. v must be in each row. 
                if not all(r for r in row_sets) or not all(v in set.union(*r) for r in row_sets):
                    continue
                col_set=set(u.col for r in row_sets for u in r if v in u)
                # The set of columns of csets containing v must be fish_size
                if len(col_set)!=fish_size:
                    continue
                remove_set=[u for u in unknowns.values() if (not u.row in rows) and u.col in col_set]
                if elim_values(v, remove_set):
                    dbg("fish", f'fish: {fish_size=} {v=} {rows=} {col_set=}')
                    return True
    # Swapping row/cols won't actually find anything else.             
    return False

def find_locked(known, unknowns):
    """Naked pairs, triples, and quads in rows, columns, or boxes.

    When N cells in a unit share exactly N candidates, remove those
    candidates from the other cells in the unit.
    """
    for r in range(9):
        rs = [u for u in unknowns.values() if u.row == r]
        for group_size in range(2, min(5,len(rs))):
            for group in itertools.combinations(rs, group_size):
                sug = set.union(*group)
                if len(sug) == group_size:
                    # Found a locked set. Eliminate elements from everthing else in row.
                    if elim_values( [v for v in sug],
                                    [ u for u in
                                      unknowns.values() if u.row == r
                                      and (not u in group)]):
                        dbg("locked", "row %d size %d cells %s values %s",
                            r, group_size, [u.idx for u in group], sug)
                        return True
    for c in range(9):
        cs = [u for u in unknowns.values() if u.col == c]
        for group_size in range(2, min(5,len(cs))):
            for group in itertools.combinations(cs, group_size):
                sug = set.union(*group)
                if len(sug) == group_size:
                    # Found a group. Eliminate group elements from everthing else in col.
                    if elim_values(
                        [v for v in sug],
                        [
                            u
                            for u in unknowns.values()
                            if u.col == c and (not u in group)
                        ],
                    ):
                        dbg("locked", "col %d size %d cells %s values %s",
                            c, group_size, [u.idx for u in group], sug)
                        return True
    for b in range(9):
        bs = [u for u in unknowns.values() if u.box == b]
        for group_size in range(2, min(5,len(bs))):
            for group in itertools.combinations(bs, group_size):
                sug = set.union(*group)
                if len(sug) == group_size:
                    # Found a group. Eliminate group elements from everthing else in box.
                    if elim_values( [v for v in sug],
                                    [ u for u in
                                      unknowns.values() if u.box == b and
                                      (not u in group) ], ):
                        dbg("locked", "box %d size %d cells %s values %s",
                            b, group_size, [u.idx for u in group], sug)
                        return True
    return False


def parse_puzzle(puzzle):
    """Parse an 81-character puzzle string into a list of cell values (0 for empty)."""
    line = puzzle.strip()
    if len(line) != 81:
        raise ValueError(f"expected 81 characters, got {len(line)}")
    return [int(ch) if ch.isdigit() else 0 for ch in line]


def validate_puzzle(known):
    """Raise ValueError if initial clues conflict within a row, column, or box."""
    for r in range(9):
        seen = set()
        for c in range(9):
            v = known[r * 9 + c]
            if not v:
                continue
            if v in seen:
                raise ValueError(f"conflict: {v} appears twice in row {r}")
            seen.add(v)

    for c in range(9):
        seen = set()
        for r in range(9):
            v = known[r * 9 + c]
            if not v:
                continue
            if v in seen:
                raise ValueError(f"conflict: {v} appears twice in column {c}")
            seen.add(v)

    for b in range(9):
        br, bc = b // 3 * 3, b % 3 * 3
        seen = set()
        for dr in range(3):
            for dc in range(3):
                v = known[(br + dr) * 9 + bc + dc]
                if not v:
                    continue
                if v in seen:
                    raise ValueError(f"conflict: {v} appears twice in box {b}")
                seen.add(v)


def create_unknowns(known):
    """Build candidate sets for empty cells, applying initial clue constraints."""
    unknowns = {i: CSet(range(1, 10), i) for i in range(81)}
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
            assert all(len(u) > 0 for u in unknowns.values())
            return True
    return False


def solve(puzzle):
    """Solve a puzzle using logical deduction.

    Return (solved, grid) where solved is True when every cell is filled.
    """
    solvers = (
        find_singles,
        find_unaries,
        find_locked,
        find_boxex,
        find_rcex,
        find_fish,
        find_skyscrapers,
    )
    known = parse_puzzle(puzzle)
    validate_puzzle(known)
    unknowns = create_unknowns(known)
    assert all(len(u) > 0 for u in unknowns.values())
    dbg("solve", "solving:\n%s", box_format(known))
    while len(unknowns) and run_solvers(solvers, known, unknowns):
        if not all(len(u) > 0 for u in unknowns.values()):
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
    with open(args.input_file) as f:
        passes,fails=0,0
        for line in f:
            line = line.strip()
            if not line:
                continue

            r=solve(line)
            if not r[0]:
                fails+=1
                results.append(f'failed:\ni={line}\no={r[1]}')
            else:
                passes+=1
                results.append(f'passed:\ni={line}\no={r[1]}')

    results.append(f'{passes=} {fails=}')
    output = "\n".join(results)
    if output:
        output += "\n"
    if args.output_file:
        with open(args.output_file, "w") as f:
            f.write(output)
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    main()
