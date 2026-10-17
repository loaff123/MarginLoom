# MarginLoom v1 design

## Intent and scope

Build a portable Python file-to-file reporting workflow for rounding a labeled two-dimensional decimal table while keeping cell values and margins coherent. Ordinary reporting is the primary use. This is not a financial ledger, privacy/disclosure-control tool, statistical validity guarantee, or a new optimization algorithm.

The implementation is qualified by independent enumeration, an independently formulated SciPy MILP, strict file and API tests, and installed real-data workflows. See QUALIFICATION.md and VERIFICATION.md for evidence and remaining limits.

## Options and decision

1. **Chosen:** standard-library exact decimal codec and workflow, NetworkX integer lower-bounded min-cost flow, separately implemented Fraction arithmetic verifier. This keeps the runtime portable and concentrates engineering on contracts, diagnosis and evidence.
2. SciPy MILP is a competent independent comparator, but using floating-point model construction would require much narrower exactness limits or extra certification; keep SciPy development-only.
3. A handwritten optimizer would increase algorithm risk without a product benefit. No custom solver.

Runtime: Python >=3.10, NetworkX >=3.2,<4. No native solver/ABI pins. Test current compatible releases and a dependency-floor job; test Linux/macOS/Windows when CI is authorized, never label an unrun matrix as passed.

## Input and contract schema

Input CSV is UTF-8 (optional BOM), RFC-style comma-delimited CSV, with a header and at least one row and one numeric column. `row_label` names exactly one header column; all remaining columns are numeric and their order is preserved. Empty/duplicate headers, duplicate/empty row IDs, extra/missing fields, blanks and nonfinite numeric tokens are errors. No locale inference, aggregation, missing-value imputation, formulas or float conversion. JSON duplicate keys and unknown schema keys are rejected.

Input JSON shape:

```json
{"schema_version":1,"row_label":"year","rows":["1949"],"columns":["Jan","Feb"],"values":[["112","118"]]}
```

IDs are nonempty strings, distinct within each axis; row_label must not equal a numeric-column ID. IDs are retained verbatim, including Unicode and quoted newlines; NUL is rejected. JSON cells must be strings, never JSON numbers. CSV whitespace around numeric tokens is rejected rather than silently normalized.

Balanced contract:

```json
{"schema_version":1,"mode":"balanced","quantum":"20","row_label":"year","nonnegative":false}
```

Prescribed contract adds `row_targets` and `column_targets`, JSON objects with exactly the input IDs as keys and decimal strings as values. These objects are forbidden in balanced mode. Required keys are schema_version, mode, quantum and row_label; nonnegative defaults to false. Empty table dimensions are invalid. Targets with malformed syntax, wrong IDs or non-lattice values are invalid input; unequal target grand totals, unattainable individual targets and a deficient flow cut are distinct proven-infeasible diagnoses. `schema_version` is integer 1, not boolean. Quantum must be positive. Prescribed targets must be exact quantum multiples; signed targets are allowed. `nonnegative=true` rejects negative source values, not clips them.

Decimal grammar is `[+-]?(digits(.digits*)?|.digits)([eE][+-]?digits)?`, ASCII digits only, at least one digit. Normalize signed zero. Parser returns integer coefficient and decimal exponent directly; no binary float or Decimal context operations. Practical limits exercised in qualification: 16 MiB per source/contract file, 10,000 cells, 1,000 IDs per axis, 128 mantissa digits/token, absolute explicit exponent <=1,000, 256 characters/token and 1,024 characters/ID. These bound normal work and are not process memory, latency or hostile-input security guarantees. In particular 1e1000 and 1e-1000 are admitted together. A common decimal exponent produces exact integer source amounts A and quantum Q.

## Separate rounding contracts

For every cell set b=floor(A/Q), remainder r=A-Qb, selected units b+y, y in {0,1} if r>0 and y=0 otherwise. Negative values use mathematical floor, so -1.25 at quantum 0.1 can produce -1.3 or -1.2. Exact multiples remain fixed.

Balanced: row and column sums lie at their source's exact floor/ceiling quantum multiples; grand total is exact nearest-even of the source grand total in quantum units. Minimize absolute cell error + absolute row error + absolute column error in original units. Report all three components and the primary objective separately.

Prescribed: require every target, exact target-ID agreement, equal row/column grand totals, and attainable cell-floor/cell-ceiling bounds. Targets may differ from nearest source margins. Minimize cell error only; row and column error are reported fixed constants. No implicit relaxation, repaired targets or automatic mode switch.

## Integer flow and sufficient obstruction

Graph nodes in fixed insertion order: source, rows in input order, columns in input order, sink. Edges: source->row, fractional row->column cells, column->sink. All capacities/demands/costs are integers and finite. Source and sink demands are -K and K, where K is required grand total units less the sum of cell floors. Row/column lower and upper residual bounds come from the selected contract. Bounds differ by at most one in balanced mode and are equal in prescribed mode.

For edge lower l and upper u, transformed capacity is u-l; transformed demand at its tail increases by l and at its head decreases by l. Cell marginal error cost is Q-2r. A flexible balanced row or column has the analogous Q-2r_margin cost. Fixed edges have zero variable cost. Constants are restored by direct arithmetic from the chosen table, not trusted flow cost accounting.

Before optimization, validate syntax, target lattice, ID agreement, equal totals and individual bounds. Next perform a max-flow feasibility check with super-source to negative-demand nodes and positive-demand nodes to super-sink. A deficient cut gives a named node subset S of the transformed network. Report row IDs, column IDs, inclusion of source/sink, required=-sum(demand(S)), available=sum(capacities crossing S outward), shortage=required-available>0. Include crossing arcs and transformed demands for explanation; the verifier recomputes them from original inputs. This is one sufficient obstruction, not a unique or minimum-cardinality diagnosis. The witness applies to balanced too, though balanced feasibility is expected mathematically.

Run NetworkX network_simplex only after feasibility. Unexpected backend exceptions produce ERROR, never INFEASIBLE. KeyboardInterrupt produces INCOMPLETE at the CLI boundary. We claim the backend's exact integer optimum for the declared primary objective, subject to testing. Fixed input and backend version use fixed insertion order and no randomness. Tied outputs may differ across backend versions; no lexicographic or canonical-optimum guarantee.

## API and modules

`Table(row_ids, column_ids, values, row_label)` stores ordered string IDs and decimal-string cells. `Contract.from_dict(data)` validates the contract. `solve(table, contract) -> Result` returns status `optimal`, `infeasible`, `error`, or `incomplete`, structured diagnostics, selected decimal strings if optimal, objective components, and backend provenance. Input errors raise `InputError` (not solver infeasibility). `inspect_table(table, contract)` returns exact source margins/bounds, targets, independent-nearest disagreements and feasibility diagnostics without minimizing cost.

Result/audit numeric fields use original-unit decimal strings. `objective` has `cells`, `rows`, `columns`, `total_error`, and `primary`; `total_error` always adds all three, while `primary` follows the selected contract. `selected` is an ordered string matrix. `margins` has `rows`, `columns`, and `grand`, each recording source, lower, upper, nearest, selected and delta. A diagnosis has `kind`, `message`, and kind-specific exact fields; cut amounts are integer residual quantum units and explicitly labeled as such.

Modules: `decimal_codec.py` integer parsing/formatting; `table_io.py` strict source handling; `contracts.py` contract validation; `model.py` table/result dataclasses and limits; `flow.py` bounded graph/feasibility/optimization; `solve.py` orchestration and exact result accounting; `verify.py` independent Fraction arithmetic and cut verification; `reporting.py` CSV/JSON/HTML rendering and non-clobber output transaction; `cli.py` argument/error/status handling. The verifier must not import flow, solve or decimal_codec, and must not call an optimizer. It may reuse structural input loading but independently checks all numeric semantics.

## CLI, outputs and evidence

Commands:

- `marginloom round input.csv --contract contract.json --out report-dir`
- `marginloom inspect input.csv --contract contract.json` (machine-readable JSON to stdout)
- `marginloom verify input.csv --contract contract.json --report report-dir`

`.json` inputs use the JSON schema; otherwise parse CSV. API remains usable without files. CLI exits: 0 success/verified, 2 invalid input/usage, 3 proven infeasible, 4 verification failure, 1 execution/I/O/backend error, 130 interrupted. Diagnostics are structured and also identify useful labels in the HTML. No tracebacks for ordinary user errors.

Optimal directory contains rounded.csv, margins.csv, audit.json and report.html. Audit schema 1 contains raw input and contract SHA-256, exact copied IDs and selected values, source and chosen margins, cell/margin checks, exact decimal objective components, contract and backend/version/tie policy, artifact SHA-256, and `verification_scope: feasibility_and_arithmetic_not_optimality`. Digests bind identity, not authenticity. No wall-clock timestamp in core outputs; repeated same-version executions can be byte-compared. CSV numbers are canonical fixed-point original-unit decimals; zeros normalize to 0 and unnecessary fractional trailing zeros disappear. All CSV fields use csv.writer. HTML is standalone, has no scripts/external resources and escapes every untrusted string. It explains changes from independently nearest cells/margins and the selected contract.

Infeasible output contains diagnosis.json and report.html, never rounded.csv or successful audit.json. Input/backend errors and interruption have no successful report. `inspect` can return the diagnosis before reserving output.

Reserve the destination with exclusive directory creation; an existing path is always an error and is never clobbered. Create an INCOMPLETE marker, write into a private child staging directory, run the independent verifier on the staged success artifacts, then move artifact files into the reserved directory, publishing audit.json last and deleting the INCOMPLETE marker last. Verifiers reject any report with the marker. Best-effort exception/interruption cleanup preserves an explicit incomplete state; uncatchable process death may leave staging/partial files. No claim of asynchronous multi-file atomicity, crash durability or adversarial filesystem safety. Never delete a destination that existed before the operation.

## Independent verification and qualification

Verifier recomputes Fraction values, quantum multiples, mathematical bounds, nearest-even grand total, prescribed targets, all objective components, source/contract and artifact hashes, selected IDs/order, rounded.csv and margins.csv agreement and every audit claim. A feasible non-optimal replacement must be labeled feasible only; the verifier is not an optimality certificate. Infeasibility witnesses are recomputed without a solver. Self-consistent tampering is not authenticity detection.

Test-first unit suites cover decimal grammar/bounds, negative half ties, 0.05 quantum, >2^53, +/-1000 exponents, zero/integral/rectangular tables, lower-bound transformation, target errors and named cut, escaping, strict JSON, repeated runs, failpoints and tampering. A separate small enumerator with Fraction is the optimum/infeasibility oracle, including signed prescribed cases. A separately modeled SciPy MILP compares moderate integer-safe cases. Five retained AirPassengers profiles must run through an isolated installed CLI and reimport. Repeat updated source under one saved contract; reject prescribed targets then rerun with explicitly selected balanced contract.

Measure representative scale; document actual hardware/Python/backend, elapsed time and peak process memory where available without universal claims. Clean wheel/sdist install and offline synthetic example are release gates. CI matrix configuration is not CI execution evidence. Independent whole-project review and regression closure are recorded in VERIFICATION.md.

## Distribution and publication boundaries

All product examples are original synthetic data. Keep competitor code and real downloaded source data outside package and release archives until redistribution terms are verified. The seaborn-data repository warns that example data have varying sources; absence of a specific data license is not permission. Cite source URL/digest and record local real-data qualification, but do not bundle raw AirPassengers values or derived rounded tables absent a confirmed applicable license. NetworkX is an ordinary declared dependency, not vendored. Include project license and third-party notices. This is a pre-publication candidate. No public release, production-readiness or adoption claim follows from this qualification.

## Qualification correction accepted during implementation

The earlier probe brief suggested a prescribed-nearest rejection at AirPassengers quantum20. The installed workflow disproved that assumption: independently recomputed row, column and grand totals all equal40360, and prescribed mode is feasible (cell objective747, total error827). All five balanced profiles remain retained unchanged. Use quantum20 as the positive prescribed case, quantum10 as real unequal-total rejection (40360 versus40350), and the original3x3 case for a named equal-total cut. The failed initial qualification-driver expectation is documented in QUALIFICATION.md; no source values were changed or profiles excluded.
