# MarginLoom candidate qualification

Date: 2026-10-08. Candidate version: 0.1.0a1. This records a bounded pre-publication check, not production readiness, adoption, universal correctness, security, financial/legal suitability or a performance comparison against other tools.

## Source and independent tests

The final source suite passes **59 unittest methods** on Linux x86-64, Python 3.12.14, NetworkX 3.7 and SciPy 1.17.0. No tests are skipped in that development run. Three added admission-boundary methods cover exact file-size, ID/axis/cell and decimal mantissa/token limits; the fresh independent review ran the preceding 56-method suite itself.

Independent arithmetic qualification comprises **841 enumerated cases** (819 feasible and 22 infeasible), including all 625 signed 2x2 tables over a five-value domain, seeded rectangular/signed/non-power-ten profiles, feasible prescribed cases and exhaustive equal-total disconnected targets. A separate SciPy selected-integer/absolute-deviation MILP checks **21 moderate cases** (20 feasible and one infeasible), using exactly representable coefficients and exact rechecking of incumbent cells/objectives. See VERIFICATION.md for case counts and scope.

The fresh review found five defects: unbounded exponent construction in saved-result verification, unhandled huge JSON integer conversion, missing public-verifier row-label identity, accepted unsupported audit claims, and missing inspect bounds/targets. Each was reproduced by failing tests, repaired, and rechecked. Additional interruption tests cover every artifact move, including interruption after the audit move. No unresolved P1/P2 finding remains. None of these checks is an independent optimum certificate for an arbitrary saved report.

## Installed real-data workflow

All five preselected AirPassengers profiles are retained, using the same unmodified 144-value source file. SHA-256: `237d834127d9c6355630d8f443a7a2377b5925923010009b59809ba0b67f4fac`. Source: https://raw.githubusercontent.com/mwaskom/seaborn-data/master/flights.csv. Units/provenance: https://stat.ethz.ch/R-manual/R-devel/library/datasets/html/AirPassengers.html.

The driver converts the series into its original 12-year by 12-month table, runs an isolated installed CLI, reimports same-unit CSV values, verifies each saved report and checks the exact grand total. Aggregate absolute errors in source units:

| Quantum | Cell | Row | Column | Balanced primary |
|---:|---:|---:|---:|---:|
| 10 | 385 | 23 | 25 | 433 |
| 20 | 747 | 41 | 39 | 827 |
| 50 | 1933 | 179 | 121 | 2233 |
| 100 | 3849 | 321 | 289 | 4459 |
| 200 | 7585 | 741 | 411 | 8737 |

These match the retained competent SciPy feasibility-probe objectives. This is numerical agreement and workflow evidence, not speed superiority or product demand.

### Corrected initial expectation

The initial qualification driver inherited an incorrect expectation that prescribed nearest margins at quantum 20 would be rejected. Its first run stopped because the installed tool returned success. Recomputing exact margins independently showed that row targets, column targets and nearest grand total all sum to 40360. Prescribed mode is feasible there, with primary cell error 747 and fixed margin errors 41 + 39, total 827. The original failed expectation is retained in the local evidence log.

Quantum 10 supplies the real-data unequal-total rejection: row target sum 40360 versus column target sum 40350. The positive base 20 case, rejected base 10 case, and separate original 3x3 equal-total named-cut example are all retained. No input values were altered to obtain a preferred result and no balanced profile was excluded.

### Repeated use and measured scale

The installed driver executes 20 commands covering the five balanced profiles and their verifications, positive prescribed 20/rejected prescribed 10 and their verifications, a changed numeric source under the same saved contract and fresh destination, a signed 100x100 synthetic table and verification, and mixed 1e1000/1e-1000 values with quantum 3e-1000 and verification.

In the initial all-green installed run, the signed 10,000-cell full report command took 1.55 seconds and its separate verify took 0.78 seconds. Linux reported a cumulative child-process peak RSS of 54,932 KiB during the driver. These figures include CLI startup, file export and independent verification; RSS is the OS child-process high-water observation across the run, not a per-case bound. Later final-package measurements are retained separately in the checkpoint evidence. No universal runtime/memory or hostile-input guarantee follows.

To reproduce with your permitted local data copy:

```sh
python tools/qualify.py --executable /absolute/path/to/marginloom --airpassengers /absolute/path/to/flights.csv --output /new/evidence/directory
```

The source dataset's specific redistribution license was not established. Raw source and cell-level derived real-data reports are excluded from the distributable package and checkpoint. Aggregate evidence, source digest and reproduction driver are included. All bundled example data are original synthetic values.

## Installation and platform gates

- Wheel and sdist build, file-list inspection, clean installed CLI, and runtime NetworkX 3.7/floor 3.2 verification are recorded in the final package evidence.
- Runtime dependencies remain standard library plus NetworkX; SciPy/NumPy are development comparators only.
- Python 3.10–3.14 on Linux/macOS/Windows are configured in CI. **Remote CI is not run**; only the recorded local Linux/Python 3.12 combinations are executed here. Portable jobs install runtime dependencies only and explicitly skip the three SciPy methods; separate Linux numerical jobs install SciPy and execute those comparisons with NetworkX 3.2 and 3.7.
- HTML escaping, artifact hashes, deterministic serialization and file/CLI behavior are tested. An attempted headless Chromium layout render was blocked by the execution environment's local socket restriction, **Browser layout rendering is unverified**; no screenshot is claimed.
- The unchanged-source/contract binding, exact report-member layout, artifact tampering, objective tampering, ID order, unknown claims, named-cut shortage and ordinary interrupted states are checked. Self-consistent report replacement is not authentication, and a feasible-but-nonoptimal result can pass the intentionally limited verifier.

No repository push, package-index release, web deployment or third-party contact was performed.
