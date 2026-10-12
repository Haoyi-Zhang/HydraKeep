"""Execute only the native driver's edit function against finite locator doubles."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class Page:
    def __init__(self, *, count=1, enabled=True, read_only=False, multiple=False, error=None):
        self.targets = count
        self.enabled = enabled
        self.read_only = read_only
        self.multiple = multiple
        self.error = error
        self.calls = []

    def locator(self, selector):
        self.calls.append(('locator', selector))
        return self

    def count(self):
        return self.targets

    def is_enabled(self):
        return self.enabled

    def evaluate(self, source, argument=None):
        if 'readOnly' in source:
            self.calls.append(('availability', None))
            if self.error is not None:
                raise self.error
            return dict(readOnly=self.read_only, multiple=self.multiple)
        if 'edit-blocked' in source:
            self.calls.append(('blocked', argument))
        elif 'edit-absent' in source:
            self.calls.append(('absent', argument))
        elif 'beginEdit' in source:
            self.calls.append(('begin', argument))
            return 37
        elif 'completeEdit' in source:
            self.calls.append(('complete', argument))
        else:
            raise AssertionError('unrecognized driver observation')

    def click(self):
        self.calls.append(('click', None))

    def focus(self):
        self.calls.append(('focus', None))

    def press(self, key):
        self.calls.append(('press', key))

    def press_sequentially(self, value):
        self.calls.append(('type', value))


class NativeEditDriverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Do not import Playwright or execute the browser/output-writing module.
        tree = ast.parse((ROOT / 'scripts/run_native.py').read_text())
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == 'edit')
        namespace = {}
        exec(compile(ast.Module(body=[function], type_ignores=[]),
                     '<native scalar edit function>', 'exec'), namespace)
        cls.edit = staticmethod(namespace['edit'])

    def field(self, kind='text'):
        value = {'checkbox': True, 'select': 'B'}.get(kind, 'toy')
        return dict(id='a', kind=kind, edit=value)

    def test_readonly_text_controls_are_blocked_before_action_start(self):
        for kind in ('text', 'textarea', 'email'):
            with self.subTest(kind=kind):
                page = Page(read_only=True)
                self.edit(page, self.field(kind))
                self.assertEqual([name for name, _ in page.calls],
                                 ['locator', 'availability', 'blocked'])
                self.assertEqual(page.calls[-1], ('blocked', 'a'))

    def test_disabled_scalar_controls_do_not_start_or_probe_an_edit(self):
        for kind in ('text', 'textarea', 'email', 'checkbox', 'select'):
            with self.subTest(kind=kind):
                page = Page(enabled=False, read_only=True)
                self.edit(page, self.field(kind))
                self.assertEqual([name for name, _ in page.calls], ['locator', 'blocked'])

    def test_writable_text_controls_keep_native_action_and_completion_order(self):
        for kind in ('text', 'textarea', 'email'):
            with self.subTest(kind=kind):
                page = Page()
                self.edit(page, self.field(kind))
                self.assertEqual([name for name, _ in page.calls],
                                 ['locator', 'availability', 'begin', 'click', 'press', 'type', 'complete'])
                self.assertEqual(page.calls[-3:],
                                 [('press', 'ControlOrMeta+A'), ('type', 'toy'), ('complete', 37)])

    def test_writable_checkbox_and_single_select_keep_their_action_paths(self):
        page = Page()
        self.edit(page, self.field('checkbox'))
        self.assertEqual([name for name, _ in page.calls],
                         ['locator', 'availability', 'begin', 'click', 'complete'])
        page = Page()
        self.edit(page, self.field('select'))
        self.assertEqual(page.calls[2:], [('begin', self.field('select')), ('focus', None),
                                         ('press', 'Home'), ('press', 'ArrowDown'),
                                         ('press', 'Enter'), ('complete', 37)])

    def test_readonly_on_nontext_controls_is_unsupported_not_a_blocked_edit(self):
        for kind in ('checkbox', 'select'):
            with self.subTest(kind=kind):
                page = Page(read_only=True)
                with self.assertRaisesRegex(RuntimeError, 'readonly applicability'):
                    self.edit(page, self.field(kind))
                self.assertEqual([name for name, _ in page.calls], ['locator', 'availability'])

    def test_multiple_select_is_rejected_before_action_start(self):
        page = Page(multiple=True)
        with self.assertRaisesRegex(RuntimeError, 'multiple select'):
            self.edit(page, self.field('select'))
        self.assertEqual([name for name, _ in page.calls], ['locator', 'availability'])

    def test_other_control_families_are_not_silently_typed_as_text(self):
        for kind in ('file', 'radio', 'number', 'select-multiple'):
            with self.subTest(kind=kind):
                page = Page()
                with self.assertRaisesRegex(RuntimeError, 'outside the native scalar profile'):
                    self.edit(page, self.field(kind))
                self.assertEqual([name for name, _ in page.calls], ['locator'])

    def test_absent_and_ambiguous_targets_keep_existing_behavior(self):
        page = Page(count=0)
        self.edit(page, self.field())
        self.assertEqual(page.calls[-1], ('absent', 'a'))
        page = Page(count=2)
        with self.assertRaisesRegex(RuntimeError, 'ambiguous target'):
            self.edit(page, self.field())
        self.assertEqual([name for name, _ in page.calls], ['locator'])

    def test_availability_probe_exception_propagates(self):
        error = RuntimeError('owned probe failure')
        page = Page(error=error)
        with self.assertRaises(RuntimeError) as raised:
            self.edit(page, self.field())
        self.assertIs(raised.exception, error)
        self.assertEqual([name for name, _ in page.calls], ['locator', 'availability'])


if __name__ == '__main__':
    unittest.main()
