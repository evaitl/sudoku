# Sudoku Solver

A Python Sudoku solver that uses logical deduction instead of
brute-force guessing. It reads puzzles from a file, applies a sequence
of human-style solving techniques, and reports whether each puzzle was
solved.

## Features

- Batch processing of puzzles from a text file (one puzzle per line)
- Candidate-set tracking with constraint propagation
- Multiple solving techniques, applied in order until progress stops:
  - Singles (naked singles)
  - Unaries (hidden singles)
  - Locked candidates (naked pairs, triples, and quads)
  - Box/line reduction (locked candidates type 1)
  - Row/column claiming (locked candidates type 2)
  - Fish patterns (X-Wing, Swordfish, and larger)
  - Skyscrapers
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

For each puzzle, the solver prints:

```text
passed:
i=<input puzzle>
o=<solved grid>
```

or:

```text
failed:
i=<input puzzle>
o=<partial grid>
```

The final line summarizes results: `passes=N fails=M`.

When an output file is given, results are written there instead of stdout.

### Debug sections

Use `--debug-section` to limit logging to one or more sections:

`solve`, `assign`, `solver`, `singles`, `unaries`, `locked`, `boxline`, `linebox`, `elim`, `fish`, `skyscraper`

## Example

```bash
$ echo '.................1.....2.3......3.2...1.4......5....6..3......4.7..8...962...7...' > example.txt
$ ./sudoku.py example.txt
passed:
i=.................1.....2.3......3.2...1.4......5....6..3......4.7..8...962...7...
o=953168742862734951417952836746893125281645397395271468138529674574386219629417583
passes=1 fails=0
```
### Test Set

A 2012 paper showed that the minimum number of poles for a proper
sudoku is 17. In 2022 all 49,159 were found and
published. [This](https://tinyurl.com/26nntcdy) file of minimal clued
sudokus is the test set for this sudoku solver program.

Right now, this thing solves all but 4 of the 49,158 17-pole sudokus
with no guessing or backtracking. For those last 4, I'm doing a
guess/backtracking.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE)
for details.
