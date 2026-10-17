"""Independent MILP with selected integers and absolute-deviation epigraphs.

No producer codec, graph, flow costs, accounting or enumeration helper is used.
All model coefficients are small exact integers representable in binary64.
"""
from fractions import Fraction
from math import lcm
import random
import unittest

from marginloom.contracts import Contract
from marginloom.model import Table
from marginloom.solve import solve

try:
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
except ImportError:
    np = None


def fraction_text(value):
    """Fixtures use denominators dividing 1,000,000, so this is exact."""
    value = Fraction(value)
    scaled = value * 1_000_000
    assert scaled.denominator == 1
    number = int(scaled)
    sign = '-' if number < 0 else ''
    whole, decimal = divmod(abs(number), 1_000_000)
    return (f'{sign}{whole}.{decimal:06d}').rstrip('0').rstrip('.')


def direct_milp(values, quantum, row_targets=None, column_targets=None):
    m, n = len(values), len(values[0])
    size = m * n
    scale = lcm(quantum.denominator, *(v.denominator for row in values for v in row))
    q = int(quantum * scale)
    original = [int(v * scale) for row in values for v in row]
    row_source = [sum(original[i*n:(i+1)*n]) for i in range(m)]
    col_source = [sum(original[i*n+j] for i in range(m)) for j in range(n)]
    balanced = row_targets is None
    count = 2 * size + (m + n if balanced else 0)
    cost = np.zeros(count)
    cost[size:] = 1
    lower = np.zeros(count)
    upper = np.full(count, np.inf)
    for k, value in enumerate(original):
        unit_value = Fraction(value, q)
        lower[k], upper[k] = unit_value.__floor__(), unit_value.__ceil__()
    integrality = np.zeros(count)
    integrality[:size] = 1
    rows, lb, ub = [], [], []

    def constraint(terms, lo=-np.inf, hi=np.inf):
        a = np.zeros(count)
        for idx, coefficient in terms:
            a[idx] = coefficient
        rows.append(a)
        lb.append(lo)
        ub.append(hi)

    def absolute(indices, source, deviation):
        constraint([(k, q) for k in indices] + [(deviation, -1)], hi=source)
        constraint([(k, -q) for k in indices] + [(deviation, -1)], hi=-source)

    for k, source in enumerate(original):
        absolute([k], source, size + k)
    for i, source in enumerate(row_source):
        indices = list(range(i*n, (i+1)*n))
        if balanced:
            a = Fraction(source, q)
            lo, hi = a.__floor__(), a.__ceil__()
            absolute(indices, source, 2*size + i)
        else:
            lo = hi = int(row_targets[i] / quantum)
        constraint([(k, 1) for k in indices], lo, hi)
    for j, source in enumerate(col_source):
        indices = [i*n+j for i in range(m)]
        if balanced:
            a = Fraction(source, q)
            lo, hi = a.__floor__(), a.__ceil__()
            absolute(indices, source, 2*size + m+j)
        else:
            lo = hi = int(column_targets[j] / quantum)
        constraint([(k, 1) for k in indices], lo, hi)
    if balanced:
        # Fraction.__round__ implements exact nearest-even independently.
        grand = round(Fraction(sum(original), q))
        constraint([(k, 1) for k in range(size)], grand, grand)
    result = milp(cost, integrality=integrality, bounds=Bounds(lower, upper),
                  constraints=LinearConstraint(np.array(rows), np.array(lb), np.array(ub)),
                  options={'time_limit': 30, 'mip_rel_gap': 0.0})
    if result.status == 2:
        return None
    if result.status != 0:
        raise AssertionError(f'MILP did not certify its optimum: {result.message}')
    units = [int(round(x)) for x in result.x[:size]]
    assert max(abs(x - y) for x, y in zip(result.x[:size], units)) < 1e-7
    # Recompute the returned integer incumbent's objective without floating math.
    cell_error = sum(abs(q*u-a) for u, a in zip(units, original))
    row_error = sum(abs(q*sum(units[i*n:(i+1)*n])-a) for i, a in enumerate(row_source))
    col_error = sum(abs(q*sum(units[i*n+j] for i in range(m))-a) for j, a in enumerate(col_source))
    score = cell_error + (row_error + col_error if balanced else 0)
    assert abs(result.fun - score) < 1e-7
    return Fraction(score, scale)


@unittest.skipIf(np is None, 'SciPy is not installed; independent MILP comparator not run')
class IndependentScipyComparisonTests(unittest.TestCase):
    def assert_matches(self, values, quantum, row_targets=None, column_targets=None):
        rows = [f'r{i}' for i in range(len(values))]
        columns = [f'c{j}' for j in range(len(values[0]))]
        table = Table(rows, columns, [[fraction_text(v) for v in row] for row in values], 'id')
        data = {'schema_version': 1, 'mode': 'balanced', 'quantum': fraction_text(quantum), 'row_label': 'id'}
        if row_targets is not None:
            data.update(mode='prescribed', row_targets=dict(zip(rows, map(fraction_text, row_targets))),
                        column_targets=dict(zip(columns, map(fraction_text, column_targets))))
        expected = direct_milp(values, quantum, row_targets, column_targets)
        result = solve(table, Contract.from_dict(data))
        if expected is None:
            self.assertEqual(result.status, 'infeasible', result.to_dict())
            return
        self.assertEqual(result.status, 'optimal', result.to_dict())
        chosen = [[Fraction(v) for v in row] for row in result.data['selected']]
        m, n = len(values), len(values[0])
        row_values = [sum(row) for row in chosen]
        col_values = [sum(chosen[i][j] for i in range(m)) for j in range(n)]
        for i in range(m):
            for j in range(n):
                unit = chosen[i][j] / quantum
                source_unit = values[i][j] / quantum
                self.assertEqual(unit.denominator, 1)
                self.assertTrue(source_unit.__floor__() <= unit <= source_unit.__ceil__())
        if row_targets is None:
            for v, s in zip(row_values, map(sum, values)):
                self.assertTrue((s/quantum).__floor__() <= v/quantum <= (s/quantum).__ceil__())
            for j, v in enumerate(col_values):
                s = sum(values[i][j] for i in range(m)) / quantum
                self.assertTrue(s.__floor__() <= v/quantum <= s.__ceil__())
            self.assertEqual(sum(row_values), round(sum(map(sum, values))/quantum)*quantum)
        else:
            self.assertEqual(row_values, row_targets)
            self.assertEqual(col_values, column_targets)
        ce = sum(abs(chosen[i][j]-values[i][j]) for i in range(m) for j in range(n))
        re = sum(abs(x-sum(row)) for x, row in zip(row_values, values))
        co = sum(abs(col_values[j]-sum(values[i][j] for i in range(m))) for j in range(n))
        primary = ce + re + co if row_targets is None else ce
        self.assertEqual(primary, expected)
        self.assertEqual(Fraction(result.data['objective']['primary']), expected)
        self.assertEqual({k: Fraction(v) for k, v in result.data['objective'].items()},
                         {'cells': ce, 'rows': re, 'columns': co, 'total_error': ce+re+co, 'primary': primary})

    def test_moderate_signed_balanced(self):
        rng = random.Random(775903)
        for case in range(12):
            m, n = [(4, 7), (8, 9), (12, 10)][case % 3]
            values = [[Fraction(rng.randrange(-400, 401), 8) for _ in range(n)] for _ in range(m)]
            quantum = [Fraction(3, 4), Fraction(5, 4), Fraction(3, 8), Fraction(5, 2)][case % 4]
            with self.subTest(case=case, shape=(m, n)):
                self.assert_matches(values, quantum)

    def test_moderate_signed_prescribed(self):
        rng = random.Random(77303)
        for case in range(8):
            m, n = [(5, 8), (8, 7)][case % 2]
            values = [[Fraction(rng.randrange(-80, 81), 8) for _ in range(n)] for _ in range(m)]
            quantum = [Fraction(3, 4), Fraction(5, 4)][case % 2]
            units = [[rng.choice([(v/quantum).__floor__(), (v/quantum).__ceil__()]) for v in row] for row in values]
            rt = [sum(row)*quantum for row in units]
            ct = [sum(units[i][j] for i in range(m))*quantum for j in range(n)]
            with self.subTest(case=case):
                self.assert_matches(values, quantum, rt, ct)

    def test_disconnected_equal_total_is_infeasible(self):
        values = [[Fraction('-0.75'), Fraction('-0.75'), Fraction(-1)],
                  [Fraction(2), Fraction(2), Fraction('2.25')],
                  [Fraction(-2), Fraction(-2), Fraction('-1.75')]]
        self.assert_matches(values, Fraction(1), [Fraction(-2), Fraction(6), Fraction(-6)],
                            [Fraction(-1), Fraction(-1), Fraction(0)])
