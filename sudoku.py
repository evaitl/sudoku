#!/usr/bin/env python3
import itertools
import argparse
import sys


class CSet(set):
    def __init__(self, iterable=None, idx=None):
        super().__init__(iterable)
        self.idx = idx
        self.row, self.col, self.box = get_rcb(idx)

    def __str__(self):
        return f"CSet({self.idx}: {super().__str__() if super().__str__() else '[]'})"

    def __repr__(self):
        return f"CSet({self.idx}: {super().__repr__() if super().__repr__() else '[]'})"

    def __eq__(self, other):
        return self.idx == other.idx

    def __hash__(self):
        return self.idx


def get_rcb(idx):
    r = idx // 9
    c = idx % 9
    b = c // 3 + r // 3 * 3
    return r, c, b


def add_known(known, unknowns, idx, value):
    """Found one

    Subtract value from r,c,m possible sets. Set known.
    """
    print(f'add_known {idx=} {value=}')
    row, col, box = get_rcb(idx)
    for u in {
        u for u in unknowns.values() if (u.row == row or u.col == col or u.box == box)
    }:
        u -= {value}
    unknowns.pop(idx, None)
    known[idx] = value
    print(f'known={format_known(known)}')

def find_singles(known, unknowns):
    """If a candidate has a single value, add as known."""
    for u in unknowns.values():
#        print(f'find singles {u=} {len(u)=}')
        if len(u) == 1:
            add_known(known, unknowns, u.idx, next(iter(u)))
            return True
    return False


def find_unaries(known, unknowns):
    """If only one candidate of a box, row, or col has a particular
    value, set known[idx] to v.

    """
    for u in unknowns.values():
        s = set.union(*(u2 for u2 in unknowns.values() if u2.row ==
                       u.row and u2.idx != u.idx ))
        #print(f'{u=} {s=}')
        for v in u:
            if not v in s:
                add_known(known, unknowns, u.idx, v)
                return True
        s = set.union(*( u2 for u2 in unknowns.values() if u2.col ==
                       u.col and u2.idx != u.idx ))
        for v in u:
            if not v in s:
                add_known(known, unknowns, u.idx, v)
                return True
        s = set.union(*( u2 for u2 in unknowns.values() if u2.box ==
                       u.box and u2.idx != u.idx ))
        for v in u:
            if not v in s:
                add_known(known, unknowns, u.idx, v)
                return True


def elim_values(vi, gi):
    """Eliminate values in vi from candidates in gi

    vi or gi can be either single values or iterators.
    """
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
        for g in gl:
            if v in g:
                ret = True
                print(f'removing {v=} from {g=}')
                g.discard(v)
    return ret


def find_rcex(known, unknowns):
    """If a value occurs in a single box of a row, then we can eliminate
    that value from other rows of the same box.

    .11......
    .1....1..
    1......1.
    =>
    .11......
    ......1..
    .......1.

    """
    for u in unknowns.values():
        for v in u:
            if not any( 1 for u2 in unknowns.values() if u2.box !=
                        u.box and u.row == u2.row and u2.contains(v) ):
                if elim_values(v, [u2 for u2 in unknowns if u2.box ==
                                   u.box and u2.row != u.row] ):
                    return True
            if not any(1 for u2 in unknowns.values() if u2.box !=
                       u.box and u.col == u2.col and u2.contains(v) ):
                if elim_values(v, [ u2 for u2 in unknowns.values() if
                                    u2.box == u.box and u2.col !=
                                    u.col ], ):
                    return True
    return False


def find_boxex(known, unknowns):
    """If a value occurs in a single row of a box, then we can
    elimiate that value from the same row of the other boxes.

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
                    return True
            if not any(1 for u2 in unknowns.values() if u2.box ==
                       u.box and u2.col != u.col and v in u2):
                if elim_values(v, [ u2 for u2 in unknowns.values() if
                                    u2.box != u.box and u2.col ==
                                    u.col ] ):
                    return True
    return False


def find_locked(known, unknowns):
    """Find locked tuples (2,3,4,.. up to candidates-1). If they are
    in a row, eliminate the values from other candidates of the row,
    etc.

    """
    for r in range(9):
        rs = [u for u in unknowns.values() if u.row == r]
        for group_size in range(2, len(rs)):
            for group in itertools.combinations(rs, group_size):
                #print(f'{rs=} {group_size=} {group=}')
                sug = set.union(*group)
                if len(sug) == group_size:
                    # Found a locked set. Eliminate elements from everthing else in row.
                    if elim_values( [v for v in sug],
                                    [ u for u in
                                      unknowns.values() if u.row == r
                                      and (not u in group)]):
                        return True
    for c in range(9):
        cs = [u for u in unknowns.values() if u.col == c]
        for group_size in range(2, len(cs)):
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
                        return True
    for b in range(9):
        bs = [u for u in unknowns.values() if u.box == r]
        for group_size in range(2, len(bs)):
            for group in itertools.combinations(bs, group_size):
                sug = set.union(*group)
                if len(sug) == group_size:
                    # Found a group. Eliminate group elements from everthing else in box.
                    if elim_values(
                        [v for v in sug],
                        [
                            u
                            for u in unknowns.values()
                            if u.box == b and (not s in group)
                        ],
                    ):
                        return True
    return False


def parse_puzzle(puzzle):
    """Parse a puzzle line into known grid

    Args:
       puzzle (string): 81 char string of digits and dots

    Returns:
       known (list of 81 ints):
    """
    line = puzzle.strip()
    if len(line) != 81:
        raise ValueError(f"expected 81 characters, got {len(line)}")
    return [int(ch) if ch.isdigit() else 0 for ch in line]


def create_unknowns(known):
    unknowns = {i: CSet(range(1, 10), i) for i in range(81)}
    for idx, v in enumerate(known):
        if v:
            add_known(known, unknowns, idx, v)

    return unknowns


def format_known(known):
    return "".join(str(v) if v else "." for v in known)


def run_solvers(solvers, known, unknown):
    for s in solvers:
        print(f'calling solver {s.__name__}')
        if s(known, unknown):
            return True
    return False


def solve(puzzle):
    """Try to solve the puzzle

    Args:
       puzzle (string): String of 81 chars

    Returns:
       (bool, string): True if solved, false if not. Final puzzle.
    """
    solvers = (
        find_singles,
        find_unaries,
        find_locked,
        find_boxex,
        find_rcex,
    )
    known = parse_puzzle(puzzle)
    unknowns = create_unknowns(known)
    assert all(len(u) > 0 for u in unknowns.values())
    while len(unknowns) and run_solvers(solvers, known, unknowns):
        assert all(len(u) > 0 for u in unknowns.values())
        pass
    return (len(unknowns) == 0, format_known(known))


def main():
    parser = argparse.ArgumentParser(description="Solve sudoku puzzles from a file.")
    parser.add_argument(
        "input_file", help="file with one puzzle per line (81 chars; . or * for empty)"
    )
    parser.add_argument(
        "output_file", nargs="?", help="optional file to write solutions"
    )
    args = parser.parse_args()

    results = []
    with open(args.input_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            results.append(format_puzzle(solve_puzzle(parse_puzzle(line))))

    output = "\n".join(results)
    if output:
        output += "\n"
    if args.output_file:
        with open(args.output_file, "w") as f:
            f.write(output)
    else:
        sys.stdout.write(output)


if __name__ == "__main__":
    kt = (
        "3..4.9..."
        "1....8..."
        "9...1..2."
        "...3....."
        "23...1.85"
        "..59....."
        "........."
        ".79...3.."
        "..8..2..6"
    )
    print(f"{kt=}")
    ks = solve(kt)
    print(f"{ks=}")
#    main()
