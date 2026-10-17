"""Original exhaustive Fraction oracle; intentionally no producer math imports.

Only public Table/Contract/solve/verify entry points are used. Candidate matrices
are enumerated directly, without a graph or the solver's marginal-cost formula.
"""
from fractions import Fraction
from itertools import product
import random
import unittest

from marginloom.contracts import Contract
from marginloom.model import Table
from marginloom.solve import solve
from marginloom.verify import verify_diagnosis, verify_result


def decimal(value):
    value = Fraction(value)
    denominator = value.denominator
    places = 0
    while 10 ** places % denominator:
        places += 1
        if places > 2000:
            raise AssertionError("fixture must be a terminating decimal")
    sign = '-' if value < 0 else ''
    digits = str(abs(value.numerator) * (10 ** places // denominator))
    if not places:
        return sign + digits
    digits = digits.zfill(places + 1)
    return sign + (digits[:-places] + '.' + digits[-places:]).rstrip('0').rstrip('.')


def bounds(value):
    return value.__floor__(), value.__ceil__()


def nearest_even(value):
    # Enumerate the one/two adjacent integers and choose distance then evenness.
    return min(set(bounds(value)), key=lambda x: (abs(value - x), abs(x % 2)))


def fixture(values, quantum, row_targets=None, column_targets=None):
    rows = [f'row {i}' for i in range(len(values))]
    columns = [f'column {j}' for j in range(len(values[0]))]
    table = Table(rows, columns, [[decimal(v) for v in row] for row in values], 'id')
    data = {'schema_version': 1, 'mode': 'balanced', 'quantum': decimal(quantum), 'row_label': 'id'}
    if row_targets is not None:
        data.update(mode='prescribed', row_targets=dict(zip(rows, map(decimal, row_targets))),
                    column_targets=dict(zip(columns, map(decimal, column_targets))))
    return table, Contract.from_dict(data)


def candidate_units(values, quantum):
    m, n = len(values), len(values[0])
    choices = [sorted(set(bounds(v / quantum))) for row in values for v in row]
    for flat in product(*choices):
        yield [flat[i * n:(i + 1) * n] for i in range(m)]


def arithmetic(values, quantum, chosen):
    m, n = len(values), len(values[0])
    rows = [sum(row) for row in chosen]
    columns = [sum(chosen[i][j] for i in range(m)) for j in range(n)]
    original_rows = [sum(row) for row in values]
    original_columns = [sum(values[i][j] for i in range(m)) for j in range(n)]
    cell_error = sum(abs(chosen[i][j] - values[i][j]) for i in range(m) for j in range(n))
    row_error = sum(abs(a - b) for a, b in zip(rows, original_rows))
    column_error = sum(abs(a - b) for a, b in zip(columns, original_columns))
    return rows, columns, {'cells': cell_error, 'rows': row_error, 'columns': column_error,
                           'total_error': cell_error + row_error + column_error}


def admissible(values, quantum, chosen, row_targets=None, column_targets=None):
    rows, columns, _ = arithmetic(values, quantum, chosen)
    for i, row in enumerate(chosen):
        for j, value in enumerate(row):
            if value / quantum not in set(bounds(values[i][j] / quantum)):
                return False
    if row_targets is not None:
        return rows == list(row_targets) and columns == list(column_targets)
    source_rows = [sum(row) for row in values]
    source_columns = [sum(row[j] for row in values) for j in range(len(values[0]))]
    return (all(x / quantum in set(bounds(s / quantum)) for x, s in zip(rows, source_rows))
            and all(x / quantum in set(bounds(s / quantum)) for x, s in zip(columns, source_columns))
            and sum(rows) == nearest_even(sum(source_rows) / quantum) * quantum)


def exhaustive_optimum(values, quantum, row_targets=None, column_targets=None):
    best = None
    for units in candidate_units(values, quantum):
        chosen = [[u * quantum for u in row] for row in units]
        if not admissible(values, quantum, chosen, row_targets, column_targets):
            continue
        _, _, objective = arithmetic(values, quantum, chosen)
        primary = objective['total_error' if row_targets is None else 'cells']
        if best is None or primary < best:
            best = primary
    return best


class IndependentEnumerationTests(unittest.TestCase):
    def assert_matches(self, values, quantum, row_targets=None, column_targets=None):
        values = [[Fraction(v) for v in row] for row in values]
        quantum = Fraction(quantum)
        table, contract = fixture(values, quantum, row_targets, column_targets)
        expected = exhaustive_optimum(values, quantum, row_targets, column_targets)
        result = solve(table, contract)
        if expected is None:
            self.assertEqual(result.status, 'infeasible', result.to_dict())
            diagnosis = verify_diagnosis(table, contract, result.data['diagnosis'])
            self.assertTrue(diagnosis.valid, diagnosis.errors)
        else:
            self.assertEqual(result.status, 'optimal', result.to_dict())
            chosen = [[Fraction(v) for v in row] for row in result.data['selected']]
            self.assertTrue(admissible(values, quantum, chosen, row_targets, column_targets))
            _, _, computed = arithmetic(values, quantum, chosen)
            computed['primary'] = computed['total_error' if row_targets is None else 'cells']
            self.assertEqual({k: Fraction(v) for k, v in result.data['objective'].items()}, computed)
            self.assertEqual(computed['primary'], expected)
            verification = verify_result(table, contract, result.to_dict())
            self.assertTrue(verification.valid, verification.errors)

    def test_exhaustive_signed_two_by_two(self):
        # All 625 matrices, including fixed cells, cancellation and negative floors.
        values = [Fraction(x, 20) for x in (-6, -1, 0, 1, 4)]
        for flat in product(values, repeat=4):
            with self.subTest(flat=flat):
                self.assert_matches([flat[:2], flat[2:]], Fraction(3, 20))

    def test_random_rectangular_balanced_arbitrary_quanta(self):
        rng = random.Random(58341)
        quanta = [Fraction(3, 100), Fraction(7, 20), Fraction(5, 4), Fraction(3, 8), Fraction(7, 2)]
        shapes = [(1, 1), (1, 5), (5, 1), (2, 3), (3, 2), (3, 3)]
        for case in range(90):
            m, n = shapes[case % len(shapes)]
            values = [[Fraction(rng.randrange(-40, 41), 20) for _ in range(n)] for _ in range(m)]
            with self.subTest(case=case, shape=(m, n), quantum=quanta[case % len(quanta)]):
                self.assert_matches(values, quanta[case % len(quanta)])

    def test_prescribed_signed_feasible_targets(self):
        rng = random.Random(146902)
        for case in range(80):
            m, n = [(2, 3), (3, 2), (3, 3), (1, 5)][case % 4]
            quantum = [Fraction(3, 20), Fraction(3, 4), Fraction(7, 2)][case % 3]
            values = [[Fraction(rng.randrange(-30, 31), 20) for _ in range(n)] for _ in range(m)]
            units = [[rng.choice(sorted(set(bounds(v / quantum)))) for v in row] for row in values]
            rt = [sum(row) * quantum for row in units]
            ct = [sum(units[i][j] for i in range(m)) * quantum for j in range(n)]
            with self.subTest(case=case):
                self.assert_matches(values, quantum, rt, ct)

    def test_prescribed_equal_total_feasible_and_infeasible(self):
        # Disconnected fractional support; every target pair has equal grand totals.
        # Integer offsets make this a signed case, not just the positive example.
        values = [[Fraction(-7, 10), Fraction(-7, 10), Fraction(-1)],
                  [Fraction(2), Fraction(2), Fraction(23, 10)],
                  [Fraction(-2), Fraction(-2), Fraction(-17, 10)]]
        quantum = Fraction(1)
        row_base = [-3, 6, -6]
        column_base = [-1, -1, -1]
        feasible = infeasible = 0
        for r_increment in product(range(3), range(2), range(2)):
            for c_increment in product(range(2), range(2), range(3)):
                if sum(r_increment) != sum(c_increment):
                    continue
                rt = [Fraction(x + y) for x, y in zip(row_base, r_increment)]
                ct = [Fraction(x + y) for x, y in zip(column_base, c_increment)]
                if exhaustive_optimum(values, quantum, rt, ct) is None:
                    infeasible += 1
                else:
                    feasible += 1
                with self.subTest(rows=rt, columns=ct):
                    self.assert_matches(values, quantum, rt, ct)
        self.assertGreater(feasible, 0)
        self.assertGreater(infeasible, 0)

    def test_negative_half_ties_large_exact_integer_and_zero(self):
        for value in ['-2.5', '-1.5', '-0.5', '0.5', '1.5', '2.5']:
            self.assert_matches([[Fraction(value)]], Fraction(1))
        self.assert_matches([[Fraction('9007199254740993.075'), Fraction('-9007199254740993.025')],
                             [Fraction('0'), Fraction('-.05')]], Fraction('.15'))
        self.assert_matches([[Fraction(0), Fraction(0)]], Fraction('.35'))

    def test_prescribed_mismatch_and_individual_bounds_are_infeasible(self):
        self.assert_matches([[Fraction('-.7'), Fraction('.2')]], Fraction('.5'),
                            [Fraction(0)], [Fraction('-.5'), Fraction(0)])
        self.assert_matches([[Fraction('-.7'), Fraction('.2')]], Fraction('.5'),
                            [Fraction(2)], [Fraction(1), Fraction(1)])
