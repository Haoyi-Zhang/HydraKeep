import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from analyze_phase_grid import typed_payload_equal


class ReceiptTypeTests(unittest.TestCase):
    def test_body_receipt_boolean_is_not_number(self):
        self.assertFalse(typed_payload_equal({'a': True, 'b': 'B'}, {'a': 1, 'b': 'B'}))
        self.assertFalse(typed_payload_equal({'a': False}, {'a': 0}))
        self.assertTrue(typed_payload_equal({'a': True, 'b': 'B'}, {'b': 'B', 'a': True}))
