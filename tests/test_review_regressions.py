"""Regression cases discovered by the fresh independent project review."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from marginloom.contracts import Contract
from marginloom.model import Table
from marginloom.reporting import write_report
from marginloom.solve import solve, inspect_table
from marginloom.verify import verify_report, verify_result
import marginloom.reporting as reporting
import marginloom.verify as verifier


class IndependentReviewRegressions(unittest.TestCase):
    def test_huge_json_number_is_clean_invalid_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = path / 'source.json'
            source.write_text('{"schema_version":1,"row_label":"id","rows":["x"],'
                              '"columns":["a"],"values":[[' + '1' * 5000 + ']]}', encoding='utf-8')
            contract = path / 'contract.json'
            contract.write_text(json.dumps({'schema_version': 1, 'mode': 'balanced',
                                            'quantum': '1', 'row_label': 'id'}), encoding='utf-8')
            for command in ['inspect', 'round']:
                args = [sys.executable, '-m', 'marginloom', command, str(source), '--contract', str(contract)]
                if command == 'round':
                    args += ['--out', str(path / 'report')]
                run = subprocess.run(args, capture_output=True, text=True)
                with self.subTest(command=command):
                    self.assertEqual(run.returncode, 2, run.stderr)
                    self.assertNotIn('Traceback', run.stderr)
                    self.assertEqual(json.loads(run.stderr)['status'], 'invalid_input')
            self.assertFalse((path / 'report').exists())

    def test_verifier_rejects_mismatched_contract_row_label(self):
        table = Table(['x'], ['a'], [['.3']], 'id')
        contract = Contract.from_dict({'schema_version': 1, 'mode': 'balanced', 'quantum': '1', 'row_label': 'id'})
        result = solve(table, contract).to_dict()
        mismatched = Contract.from_dict({**contract.to_dict(), 'row_label': 'other_label'})
        result['contract'] = mismatched.to_dict()
        checked = verify_result(table, mismatched, result)
        self.assertFalse(checked.valid, 'An incompatible table/contract pair must not be verified')

    def test_unbounded_report_exponent_rejected_before_fraction(self):
        table = Table(['x'], ['a'], [['.3']], 'id')
        contract = Contract.from_dict({'schema_version': 1, 'mode': 'balanced', 'quantum': '1', 'row_label': 'id'})
        original = solve(table, contract).to_dict()
        fraction = verifier.Fraction
        # Intercept only the dangerous token; never compute its huge power of ten.
        for token in ['1e1000000000', '1e-1000000000']:
            reached_fraction = []

            def guarded_fraction(value, *args, **kwargs):
                if value == token:
                    reached_fraction.append(value)
                    raise ValueError('test guard stopped an unbounded expansion')
                return fraction(value, *args, **kwargs)

            result = copy.deepcopy(original)
            result['selected'][0][0] = token
            with self.subTest(token=token), patch.object(verifier, 'Fraction', side_effect=guarded_fraction):
                self.assertTrue(verify_result(table, contract, original).valid, "The interception must preserve ordinary verification")
                checked = verify_result(table, contract, result)
                self.assertFalse(checked.valid)
                self.assertEqual(reached_fraction, [], 'Out-of-policy exponents must be rejected before Fraction')

    def test_each_interrupted_publication_step_stays_incomplete(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = path / 'source.csv'
            source.write_text('id,a,b\nx,.3,.3\n', encoding='utf-8')
            contract = path / 'contract.json'
            contract.write_text(json.dumps({'schema_version': 1, 'mode': 'balanced',
                                            'quantum': '1', 'row_label': 'id'}), encoding='utf-8')
            publish = reporting._publish_file
            for moved_count in range(1, 5):
                calls = []

                def interrupted_publish(src, dest):
                    publish(src, dest)
                    calls.append(dest)
                    if len(calls) == moved_count:
                        raise KeyboardInterrupt()

                destination = path / f'out-{moved_count}'
                with self.subTest(moved_count=moved_count), patch.object(reporting, '_publish_file', side_effect=interrupted_publish):
                    result = write_report(source, contract, destination)
                    self.assertEqual(result.status, 'incomplete')
                    self.assertTrue((destination / 'INCOMPLETE').exists())
                    self.assertFalse(verify_report(source, contract, destination).valid)
                    self.assertEqual(len(calls), moved_count)

    def test_verifier_rejects_unsupported_optimality_assertions(self):
        table = Table(['x'], ['a'], [['.3']], 'id')
        contract = Contract.from_dict({'schema_version': 1, 'mode': 'balanced', 'quantum': '1', 'row_label': 'id'})
        original = solve(table, contract).to_dict()
        for section in ['top-level', 'backend']:
            result = copy.deepcopy(original)
            if section == 'top-level':
                result['optimality_proven'] = True
            else:
                result['backend']['optimality_proven'] = True
            with self.subTest(section=section):
                self.assertFalse(verify_result(table, contract, result).valid,
                                 'An unknown certification claim must not pass schema-1 verification')

    def test_inspect_exposes_bounds_and_prescribed_targets(self):
        table = Table(['x'], ['a', 'b'], [['.3', '.3']], 'id')
        balanced = Contract.from_dict({'schema_version': 1, 'mode': 'balanced', 'quantum': '1', 'row_label': 'id'})
        prescribed = Contract.from_dict({**balanced.to_dict(), 'mode': 'prescribed',
                                        'row_targets': {'x': '2'}, 'column_targets': {'a': '1', 'b': '1'}})
        for contract in [balanced, prescribed]:
            inspected = inspect_table(table, contract)
            with self.subTest(mode=contract.mode):
                self.assertEqual(inspected['status'], 'feasible')
                for group in ['rows', 'columns']:
                    for margin in inspected[group]:
                        self.assertIn('lower', margin, 'inspect must expose its exact admissible margin bounds')
                        self.assertIn('upper', margin)
                        if contract.mode == 'prescribed':
                            targets = contract.row_targets if group == 'rows' else contract.column_targets
                            self.assertEqual(margin.get('target'), targets[margin['id']])

    def test_saved_metadata_rejects_unknown_claims(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            source = path / 'source.csv'
            source.write_text('id,a\nx,.3\n', encoding='utf-8')
            for mode in ['balanced', 'prescribed']:
                data = {'schema_version': 1, 'mode': mode, 'quantum': '1', 'row_label': 'id'}
                if mode == 'prescribed':
                    data.update(row_targets={'x': '2'}, column_targets={'a': '2'})
                contract = path / f'{mode}.json'
                contract.write_text(json.dumps(data), encoding='utf-8')
                destination = path / mode
                write_report(source, contract, destination)
                metadata = destination / ('audit.json' if mode == 'balanced' else 'diagnosis.json')
                record = json.loads(metadata.read_text(encoding='utf-8'))
                record['unsupported_certification_claim'] = True
                metadata.write_text(json.dumps(record), encoding='utf-8')
                with self.subTest(mode=mode):
                    self.assertFalse(verify_report(source, contract, destination).valid)
