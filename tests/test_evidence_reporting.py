"""Finite execution-log parsing tests; no discovery-derived passing counts."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from summarize_evidence import passing_tests_from_log


class ExecutionLogCountTests(unittest.TestCase):
    def log(self, count=185, ending='OK'):
        word = 'test' if count == 1 else 'tests'
        return f'....\n----------------------------------------------------------------------\nRan {count} {word} in 0.123s\n\n{ending}\n'

    def test_successful_execution_supplies_count_for_lf_and_crlf(self):
        for count in (1, 185, 201):
            for newline in ('\n', '\r\n'):
                with self.subTest(count=count, newline=newline):
                    self.assertEqual(passing_tests_from_log(self.log(count).replace('\n', newline)), count)

    def test_discovery_alone_cannot_supply_a_passing_count(self):
        for text in ('185 discovered tests', '{"countTestCases":185}', 'OK\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                passing_tests_from_log(text)

    def test_incomplete_execution_is_rejected(self):
        for text in ('', '....', 'Ran 185 tests in 0.123s\n', self.log(ending='')):
            with self.subTest(text=text), self.assertRaises(ValueError):
                passing_tests_from_log(text)

    def test_failed_execution_is_not_reported_as_passing(self):
        for ending in ('FAILED (errors=1)', 'FAILED (failures=1)', 'ERROR'):
            with self.subTest(ending=ending), self.assertRaises(ValueError):
                passing_tests_from_log(self.log(ending=ending))

    def test_skips_and_expected_failures_are_not_counted_as_all_passing(self):
        for ending in ('OK (skipped=1)', 'OK (expected failures=1)', 'OK (unexpected successes=1)'):
            with self.subTest(ending=ending), self.assertRaises(ValueError):
                passing_tests_from_log(self.log(ending=ending))

    def test_multiple_suites_cannot_be_combined_into_one_count(self):
        with self.assertRaises(ValueError):
            passing_tests_from_log(self.log(16) + self.log(185))

    def test_zero_executed_tests_is_not_validation(self):
        with self.assertRaises(ValueError):
            passing_tests_from_log(self.log(0))


if __name__ == '__main__':
    unittest.main()
