# Sudoku Solver

A Python Sudoku solver that applies human-style logical techniques first,
with guess-and-backtrack as a final fallback. It reads puzzles from a
file, applies a sequence of solving techniques, and reports whether each
puzzle was solved.

## Features

- Batch processing of puzzles from a text file (one puzzle per line)
- Parallel batch solving with one worker thread per CPU core
- Candidate-set tracking with constraint propagation
- Multiple solving techniques, applied in order until progress stops:
  - Singles (naked singles)
  - Unaries (hidden singles)
  - Locked candidates (naked pairs, triples, and quads)
  - Hidden subsets (hidden pairs and triples)
  - Box/line reduction (locked candidates type 1)
  - Row/column claiming (locked candidates type 2)
  - Fish patterns (X-Wing, Swordfish, and larger)
  - Skyscrapers
  - Kites (two-string kite / turbot fish)
  - XY-wing
  - Crane (strong-weak-strong chains)
  - Simple coloring (two-color strong-link chains)
  - Guess (MRV selection with propagation and backtracking)
- Optional debug logging with per-section filters
- Input validation for conflicting clues

## Requirements

- Python 3.6+

No third-party dependencies.

## Usage

```bash
./sudoku.py puzzles.txt
./sudoku.py puzzles.txt solutions.txt
./sudoku.py puzzles.txt -d
./sudoku.py puzzles.txt --debug-section fish --debug-section skyscraper
```

### Input format

Each non-empty line is one puzzle as 81 characters in row-major order:

- Digits `1`–`9` are given clues
- `.`, `*`, or any non-digit marks an empty cell

Example:

```text
.................1.....2.3......3.2...1.4......5....6..3......4.7..8...962...7...
```

### Output format

For each puzzle, the solver prints a result block in the order puzzles
finish (not necessarily the order they appear in the input file):

```text
passed:
i=<input puzzle>
o=<solved grid>
c=<per-solver success counts>
```

or:

```text
failed:
i=<input puzzle>
o=<partial grid>
c=<per-solver success counts>
```

The `c=` line lists how many times each solver made progress on that
puzzle, for example `find_singles=43 find_unaries=21 find_fish=0`.

After all puzzles, three summary lines are printed:

```text
passes=N fails=M
find_singles=418 find_unaries=222 ...
find_singles=0.001s find_unaries=0.003s ...
```

The first line counts solved and unsolved puzzles. The second line totals
solver success counts across the whole batch. The third line totals
elapsed seconds spent in each solver across the whole batch.

When an output file is given, results are written there instead of stdout.

### Debug sections

Use `--debug-section` to limit logging to one or more sections:

`solve`, `assign`, `solver`, `singles`, `unaries`, `locked`, `hidden`,
`boxline`, `linebox`, `elim`, `fish`, `skyscraper`, `kite`, `xywing`,
`crane`, `coloring`, `guess`

## Example

```bash
$ echo '.................1.....2.3......3.2...1.4......5....6..3......4.7..8...962...7...' > example.txt
$ ./sudoku.py example.txt
passed:
i=.................1.....2.3......3.2...1.4......5....6..3......4.7..8...962...7...
o=953168742862734951417952836746893125281645397395271468138529674574386219629417583
c=find_singles=43 find_unaries=21 find_locked=5 find_hidden=0 find_boxline=0 find_linebox=0 find_fish=0 find_skyscrapers=0 find_kites=0 find_xywing=0 find_crane=0 find_coloring=0 find_guess=0
passes=1 fails=0
find_singles=43 find_unaries=21 find_locked=5 find_hidden=0 find_boxline=0 find_linebox=0 find_fish=0 find_skyscrapers=0 find_kites=0 find_xywing=0 find_crane=0 find_coloring=0 find_guess=0
find_singles=0.000s find_unaries=0.000s find_locked=0.000s find_hidden=0.000s find_boxline=0.000s find_linebox=0.000s find_fish=0.000s find_skyscrapers=0.000s find_kites=0.000s find_xywing=0.000s find_crane=0.000s find_coloring=0.000s find_guess=0.000s
```

### Parallel batch solving

Batch runs use one solver thread per CPU core. The main thread feeds
puzzles from the input file into a shared work queue; each worker pulls
the next puzzle as it finishes the previous one. Per-solver statistics
are kept in thread-local storage during solving and merged into the
batch totals printed at the end.

### Test Set

A 2012 paper showed that the minimum number of poles for a proper
sudoku is 17. In 2022 all 49,159 were found and
published. [This](https://tinyurl.com/26nntcdy) file of minimal clued
sudokus is the test set for this sudoku solver program.

All 49,158 17-clue puzzles in the test set solve. Most finish with
logic alone; the hardest few need the final guess/backtrack step.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE)
for details.
