# MarginLoom

Exact-decimal, two-dimensional rounding for ordinary reporting. Turn a labeled CSV or JSON table into coherent rounded cells, row totals, column totals and a grand total, with a readable report and a separately checked arithmetic trail.

MarginLoom is a workflow around the established integer min-cost-flow algorithm in NetworkX. It is not a new optimizer. SciPy MILP can solve the same numerical problem; this package supplies exact file semantics, explicit contracts, named infeasibility explanations and auditable outputs.

## Install and run

Python 3.10 or newer; runtime dependencies are the standard library and NetworkX 3.2 or newer, below 4. This is an unpublished candidate: install a supplied local wheel or source directory, not a presumed package-index release.

```sh
python -m pip install ./marginloom-0.1.0a1-py3-none-any.whl
marginloom inspect examples/table.csv --contract examples/balanced.json
marginloom round examples/table.csv --contract examples/balanced.json --out report-1
marginloom verify examples/table.csv --contract examples/balanced.json --report report-1
```

Open `report-1/report.html` locally. `rounded.csv` retains original numeric units. `margins.csv` reconciles original, allowed, nearest and selected totals. `audit.json` binds input/contract bytes and the three output artifacts by SHA-256 and records every cell, margin and objective component. The audit never hashes itself. Hashes identify bytes; they do not prove authenticity.

All bundled examples are original synthetic data. The example quantities are illustrative reporting values, not observed participants or a ledger. Reuse the saved contract with an updated source and a **new** output directory. Existing output paths are always refused.

## Choose a contract explicitly

Balanced:

```json
{"schema_version":1,"mode":"balanced","quantum":"0.05","row_label":"category"}
```

Each cell, row sum and column sum becomes its exact floor or ceiling quantum multiple. The grand total uses nearest-even rounding. The primary objective minimizes the sum of absolute cell, row and column changes in original units; its components are reported separately. This display objective is a declared choice, not a universal scientific policy.

Prescribed:

```json
{"schema_version":1,"mode":"prescribed","quantum":"1","row_label":"category","row_targets":{"Workshops":"24","Talks":"22","Tours":"17"},"column_targets":{"Online":"24","In person":"28","Partner":"11"}}
```

Every row/column target must be present, an exact quantum multiple and attainable using cell floor/ceiling choices. Target grand totals must agree. Equal totals alone do not guarantee feasibility. Prescribed mode minimizes cell error; margin errors are reported fixed constants. It never repairs targets or switches to balanced mode. Inspect the diagnosis, then explicitly choose revised targets or a balanced contract and a fresh output directory.

For a flow obstruction, the report names a row/column node set, its required residual flow, available outgoing capacity and positive shortage. The numbers are integer quantum increments. This proves one obstruction; it is not necessarily a unique or smallest explanation.

## Exact inputs

CSV: UTF-8 (optional BOM), one header, exactly one column named by `row_label`, and at least one data row and numeric column. That label column can appear anywhere. IDs must be unique within each axis and nonempty. CSV quoted commas/newlines and Unicode IDs are supported. No blanks, duplicate labels, ragged rows, NUL, unpaired Unicode surrogates, locale inference or automatic imputation.

JSON:

```json
{"schema_version":1,"row_label":"category","rows":["Workshops"],"columns":["Online","In person"],"values":[["12.45","8.35"]]}
```

Numeric cells, quantum and targets are **decimal strings**, never JSON numbers. Duplicate JSON keys and unknown schema keys are errors. Optional `nonnegative: true` rejects negative source values, never clips them.

Supported numeric text includes `-1.25`, `.05`, `1.`, and scientific notation such as `1e1000`. Whitespace, NaN/Infinity, commas, underscores, Unicode digits and binary floats are rejected. Negative values use mathematical floor: -1.25 at quantum 0.1 may become -1.3 or -1.2. Exact multiples remain fixed, and signed zero normalizes to `0`.

Practical limits: 16 MiB per source/contract file, 10,000 cells, 1,000 IDs per axis, 1,024 characters per ID, 256 characters per source decimal, 128 mantissa digits, and explicit exponents from -1,000 through +1,000. These are ordinary operational limits, not hard memory, latency or hostile-input guarantees. Expanded fixed-point report values can be longer than source-token limits; the report verifier supports those generated values. Keep compact original source values for re-rounding extreme-exponent data.

## Verification and ties

`verify` independently recomputes values with Python Fraction arithmetic. It checks floor/ceiling bounds, quantum multiples, row/column contracts, grand total, objective components, IDs/order, exact expected report members, CSV agreement and all recorded hashes. It does not call the optimizer. It can also check a saved infeasibility cut without a solver.

A verification success means **feasibility and arithmetic checked**, not an independent optimality proof. The audit's `status: optimal` is the integer-flow backend's outcome. Small exhaustive enumeration and independent SciPy comparisons qualify that optimizer separately. A self-consistently replaced feasible non-optimal table can pass feasibility verification; a forged complete report is not authenticated by its own hashes.

Node/edge insertion order is fixed and no randomness is used. Identical inputs with the same backend version are tested for repeatability. Tied solutions may differ across backend versions; no lexicographic or universal canonical optimum is promised.

## Python API

```python
from marginloom.model import Table
from marginloom.contracts import Contract
from marginloom.solve import solve
from marginloom.verify import verify_result

table = Table(["one"], ["a", "b"], [["-1.25", "2.15"]], "id")
contract = Contract.from_dict({"schema_version": 1, "mode": "balanced", "quantum": "0.1", "row_label": "id"})
result = solve(table, contract)
if result.status == "optimal":
    assert verify_result(table, contract, result.to_dict()).valid
    print(result.data["selected"])
```

Input-schema errors raise `InputError`. Results have status `optimal`, `infeasible`, `error` or `incomplete`; backend failure is never evidence of infeasibility. `inspect_table` checks exact source margins and feasibility without minimizing the objective.

## Output lifecycle and exits

A new output directory is reserved exclusively, marked `INCOMPLETE`, and staged internally. Successful artifacts are verified before publication; metadata is moved last and the marker removed last. Ordinary handled failures/interruption leave the marker; `verify` refuses such reports. A killed process may leave partial or staging files. This is best-effort interruption handling, not multi-file atomicity, crash durability or protection against an adversarial filesystem.

Infeasible runs contain `diagnosis.json` and `report.html`, never a rounded table. Invalid input, backend failure or interruption never produces a valid successful report. No source file is modified and no input content is executed. CSV labels remain verbatim: spreadsheet applications may interpret formula-like labels, so import labels as text.

Exit codes: 0 success or verified; 2 invalid input/usage; 3 proven infeasible; 4 verification failure; 1 execution/I/O/backend error; 130 interrupted.

## Boundaries and development

Not a financial ledger, accuracy recovery, privacy/disclosure control, apportionment-law compliance or decision system about people. No hierarchical/linked tables, missing cells, more than two dimensions, per-cell locks, weighted objectives or stochastic rounding in this version.

Run `python -m unittest discover -s tests -v`. SciPy is optional for normal development but required for the recorded qualification comparator. See `docs/QUALIFICATION.md` for measured checks and unrun platform gates, and `THIRD_PARTY.md` for provenance boundaries. No public release or adoption is implied.
