# Provenance and redistribution boundaries

MarginLoom source, synthetic examples and independently authored tests are offered under the accompanying MIT license. No competitor source code is incorporated.

## Runtime

NetworkX is a declared, separately installed runtime dependency (BSD-3-Clause). It is not vendored. See https://networkx.org/documentation/stable/developer/license.html and the license in its installed distribution. Python's standard library is supplied by the Python installation.

## Development comparators

SciPy (BSD-3-Clause) and NumPy (BSD-3-Clause) are optional development/test comparators, not runtime dependencies and not bundled. See https://scipy.org/about/ and https://numpy.org/doc/stable/license.html. Their independent numerical formulation is test code authored for this project.

## External real-data qualification

The retained real-data workflow uses the 144-value AirPassengers series (international airline passengers, monthly 1949–1960, in thousands), downloaded for the prior research probe from https://raw.githubusercontent.com/mwaskom/seaborn-data/master/flights.csv. R dataset documentation: https://stat.ethz.ch/R-manual/R-devel/library/datasets/html/AirPassengers.html. The seaborn-data repository describes data originating from multiple sources and does not establish a dataset-specific redistribution license for this file. Public availability alone is not a license.

Accordingly, the distributable source, wheel, sdist and checkpoint exclude that raw dataset and its rounded cell-level exports. Local qualification evidence records its SHA-256, aggregate metrics and reproducible commands. To rerun, supply your own permitted local copy to tools/qualify.py; the script makes no download automatically. The original reporting transformation is an example, not evidence of adoption or a request by the dataset owners.

Inspected GPL-licensed cuadramelo competitor R source and executed CtrlRound/iteround comparison packages from the research probe remain outside the product and archive. This project does not claim an incumbent correctness, speed or applicability defeat.
