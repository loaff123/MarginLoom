# Technical verification summary

Candidate: MarginLoom 0.1.0a1. Checked on 2026-10-08. Scope: exact-decimal two-dimensional rounding and its CSV/JSON/report workflow. This is bounded engineering evidence, not a universal correctness proof, an audit of hostile-input security, or a guarantee of privacy, financial or legal suitability.

## Results

- **59 source tests passed**, with no skips, on Linux x86-64, Python 3.12.14, NetworkX 3.7 and SciPy 1.17.0.
- The **NetworkX 3.2 dependency floor passed all 59 tests** using an installed package and an independent SciPy-enabled test interpreter.
- Clean wheel and sdist installations each ran 59 test methods: **56 passed and 3 skipped**. The three skipped SciPy methods are explicit because those runtime-only environments intentionally contain no SciPy.
- **841 independently enumerated input/contract cases** passed: 819 feasible and 22 infeasible. They include every signed 2x2 matrix over a selected five-value domain, rectangular examples, negative values, non-power-ten quantum values, prescribed targets and equal-total obstructions.
- **21 independently formulated SciPy MILP cases** passed: 20 feasible and one infeasible. Coefficients were exactly representable and returned choices/objectives were checked with exact arithmetic.
- **20 installed-CLI workflow commands** passed, retaining all five real-data rounding profiles, prescribed success and rejection, updated source under a saved contract, a 10,000-cell signed synthetic table and extreme admitted exponents.

## Independence and claim boundaries

The enumeration oracle uses Fraction arithmetic and enumerates adjacent cell choices directly. It does not reuse the product's decimal codec, graph construction, lower-bound transformation, marginal costs or objective accounting. The SciPy comparator uses selected integer cell variables and absolute-deviation constraints rather than the product's flow formulation.

The saved-report verifier independently checks numeric feasibility, objective accounting, identifiers, CSV consistency, exact artifact membership and hashes. It does not call an optimizer and does not prove an arbitrary saved table is globally optimal. A deliberately non-optimal but feasible table passes only the explicitly limited feasibility/arithmetic scope. Digests bind bytes, not authenticity.

## Regression closure

Five reproducible defects were repaired and covered by regression tests before this candidate:

1. Bound a report's explicit exponent before constructing Fraction, while preserving supported source exponents and expanded generated decimals.
2. Convert oversized malformed JSON integer parsing into clean invalid-input output instead of an uncaught traceback.
3. Reject a direct verifier call whose table and contract row-label identifiers disagree.
4. Reject unknown schema fields, including unsupported certification assertions in success/backend or infeasibility metadata.
5. Include exact effective lower/upper margin bounds and explicit prescribed targets in inspect output.

No unresolved high-priority or important finding remains from that review. Additional tests interrupt publication after each artifact move, including the final audit move; all remain marked INCOMPLETE and fail verification. This establishes the documented ordinary catchable-interruption behavior, not asynchronous multi-file atomicity or crash durability.

## Reproduce

Install from the supplied wheel or source directory, then run:

```sh
python -m unittest discover -s tests -v
```

Install SciPy in the test environment to execute the optional independent MILP tests rather than skip them. The project itself requires only the standard library and NetworkX. The real-data driver, source digest, measurements and licensing exclusions are documented in QUALIFICATION.md.

## Unexecuted checks

Remote CI is configured for Linux, macOS and Windows on Python 3.10–3.14, but those remote jobs have not run. Only the documented local Linux/Python 3.12 combinations are executed. Browser layout rendering was unavailable in this environment; escaped HTML content, deterministic serialization and artifact verification were tested. There is no claim of a verified screenshot, cross-platform execution, public release, production readiness or adoption.
