"""Owned finite request-behavior tests. No browser or native event claims.

Only edit() is extracted by AST; runner imports, servers, browser launch and
result writers are never executed. Values and operations are modeled, not trust.
"""
import ast
import json
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DRIVERS = {'native': 'run_native.py', 'transaction': 'run_transactions.py',
           'typed': 'run_typed_transactions.py'}


def edit_function(driver):
    tree = ast.parse((ROOT / 'scripts' / DRIVERS[driver]).read_text(encoding='utf-8'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'edit')
    namespace = {'Any': object}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<owned scalar edit>', 'exec'), namespace)
    return namespace['edit'], function


def option(value, label=None, blocked=False):
    return dict(value=value, label=value if label is None else label, blocked=blocked)


class Options:
    def __init__(self, page): self.page = page
    def evaluate_all(self, source):
        self.page.probes.append(source)
        # Model both scalar option values and option-property descriptors.
        if 'label:' in source or 'blocked:' in source:
            return [dict(item) for item in self.page.options]
        return [item['value'] for item in self.page.options]


class Keyboard:
    def __init__(self, page): self.page = page
    def press(self, key):
        self.page.calls.append(('keyboard', key))
        if not self.page.fail_operation:
            matches = [o for o in self.page.options if o['label'][:1].lower() == key.lower()]
            if len(matches) == 1: self.page.value = matches[0]['value']


class Page:
    def __init__(self, kind='text', value='seed', options=None, *, enabled=True,
                 readonly=False, multiple=False, count=1, maximum=None,
                 fail_operation=False, probe_error=None):
        self.kind, self.value = kind, value
        self.options = options if options is not None else [option('A'), option('B'), option('C')]
        self.enabled, self.readonly, self.multiple, self.targets = enabled, readonly, multiple, count
        self.maximum, self.fail_operation, self.probe_error = maximum, fail_operation, probe_error
        self.calls, self.probes = [], []
        self.selected_all = False
        self.keyboard = Keyboard(self)

    def locator(self, selector):
        if selector == 'option': return Options(self)
        self.calls.append(('locator', selector))
        return self

    def count(self): return self.targets
    def is_enabled(self): return self.enabled
    def is_checked(self): return self.value
    def input_value(self): return self.value
    def get_attribute(self, name):
        if name == 'readonly': return '' if self.readonly else None
        if name == 'maxlength': return self.maximum
        raise AssertionError('unreviewed attribute: ' + name)

    def evaluate(self, source, argument=None):
        if self.probe_error is not None and ('readOnly' in source or 'control' in source or 'el.tagName' in source):
            raise self.probe_error
        if 'readOnly' in source:
            return dict(readOnly=self.readonly, multiple=self.multiple)
        if 'control' in source or 'el.tagName' in source: return self.kind
        if 'edit-blocked' in source: self.calls.append(('blocked', argument))
        elif 'edit-absent' in source: self.calls.append(('absent', argument))
        elif 'beginEdit' in source:
            self.calls.append(('begin', argument)); return 37
        elif 'completeEdit' in source: self.calls.append(('complete', argument))
        else: raise AssertionError('unreviewed observation: ' + source)

    def click(self):
        self.calls.append(('click', None))
        if self.kind == 'checkbox' and not self.fail_operation: self.value = not self.value
    def check(self):
        self.calls.append(('check', None))
        if not self.fail_operation: self.value = True
    def uncheck(self):
        self.calls.append(('uncheck', None))
        if not self.fail_operation: self.value = False
    def focus(self): self.calls.append(('focus', None))
    def press(self, key):
        self.calls.append(('press', key))
        if self.fail_operation: return
        if key == 'ControlOrMeta+A': self.selected_all = True
        elif key == 'Backspace':
            self.value = '' if self.selected_all else self.value[:-1]
        elif key == 'Home': self.value = self.options[0]['value']
        elif key == 'ArrowDown':
            index = [o['value'] for o in self.options].index(self.value)
            self.value = self.options[min(index + 1, len(self.options) - 1)]['value']
        elif key != 'Enter': raise AssertionError('unreviewed key: ' + key)
    def press_sequentially(self, value):
        self.calls.append(('type', value))
        # Empty typing produces no modeled edit, even after select-all.
        if value and not self.fail_operation:
            self.value = value if self.selected_all else self.value + value
            self.selected_all = False


class EditRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.drivers = {name: edit_function(name)[0] for name in DRIVERS}

    def edit(self, driver, page, value):
        if driver == 'native':
            kind = 'select' if page.kind == 'select-one' else page.kind
            self.drivers[driver](page, dict(id='a', kind=kind, edit=value))
        else: self.drivers[driver](page, 'a', value)

    def reject(self, driver, page, value, message=None):
        with self.assertRaisesRegex((RuntimeError, ValueError), message or '.'):
            self.edit(driver, page, value)
        self.assertFalse(any(name in ('begin', 'complete', 'click', 'check', 'uncheck',
                                     'focus', 'press', 'type', 'keyboard') for name, _ in page.calls))

    def reached(self, driver, page, value):
        self.edit(driver, page, value)
        self.assertEqual(type(page.value), type(value))
        self.assertEqual(page.value, value)
        self.assertEqual(page.calls[-1], ('complete', 37))
        self.assertEqual(sum(name == 'begin' for name, _ in page.calls), 1)

    def test_nonempty_to_empty_text_uses_explicit_deletion(self):
        for driver in DRIVERS:
            for kind in ('text', 'textarea', 'email'):
                with self.subTest(driver=driver, kind=kind):
                    page = Page(kind)
                    self.reached(driver, page, '')
                    self.assertEqual(page.calls[-4:], [('click', None), ('press', 'ControlOrMeta+A'),
                                                      ('press', 'Backspace'), ('complete', 37)])
                    self.assertFalse(any(name == 'type' for name, _ in page.calls))

    def test_empty_to_nonempty_and_replacement_reach_exact_text(self):
        for driver in DRIVERS:
            for before, requested in (('', 'toy'), ('seed', 'toy'), ('seed', 'two words'), ('seed', '汉字')):
                with self.subTest(driver=driver, before=before, requested=requested):
                    self.reached(driver, Page(value=before), requested)

    def test_unchanged_text_is_rejected_before_action(self):
        for driver in DRIVERS:
            for value in ('', 'toy'):
                self.reject(driver, Page(value=value), value, 'No-op')

    def test_wrong_text_types_are_not_coerced(self):
        for driver in DRIVERS:
            for value in (True, False, 0, None, [], {}): self.reject(driver, Page(), value, '[Ss]tring')

    def test_control_characters_are_rejected_before_action(self):
        for driver in DRIVERS:
            for value in ('a\nb', 'a\rb', 'a\tb', '\x00', '\x7f'):
                self.reject(driver, Page(), value, '[Cc]ontrol characters')

    def test_email_edge_spaces_are_rejected_before_action(self):
        for driver in DRIVERS:
            for value in (' a@example.test', 'a@example.test '):
                self.reject(driver, Page('email'), value, 'whitespace')

    def test_maxlength_uses_utf16_units_and_allows_boundary(self):
        for driver in DRIVERS:
            self.reject(driver, Page(maximum='2'), 'toy', 'maxlength')
            self.reject(driver, Page(maximum='1'), '😀', 'maxlength')
            self.reached(driver, Page(maximum='2'), '😀')
            self.reached(driver, Page(maximum='0'), '')

    def test_checkbox_requests_in_both_directions(self):
        for driver in ('native', 'typed'):
            for before, value in ((False, True), (True, False)):
                page = Page('checkbox', before)
                self.reached(driver, page, value)
                expected = 'click' if driver == 'native' else 'check' if value else 'uncheck'
                self.assertEqual(page.calls[-2], (expected, None))

    def test_checkbox_noops_are_not_toggled_or_started(self):
        for driver in ('native', 'typed'):
            for value in (False, True): self.reject(driver, Page('checkbox', value), value, 'No-op')

    def test_checkbox_requests_require_boolean_not_truthiness(self):
        for driver in ('native', 'typed'):
            for value in (0, 1, 'true', 'false', None):
                self.reject(driver, Page('checkbox', False), value, 'Boolean')

    def test_native_select_reaches_first_middle_and_last_requested_option(self):
        for before, value, downs in (('B', 'A', 0), ('A', 'B', 1), ('A', 'C', 2), ('C', 'B', 1)):
            page = Page('select-one', before)
            self.reached('native', page, value)
            keys = [v for name, v in page.calls if name == 'press']
            self.assertEqual(keys, ['Home'] + ['ArrowDown'] * downs + ['Enter'])

    def test_native_select_can_request_an_empty_option_value(self):
        self.reached('native', Page('select-one', 'B', [option(''), option('B')]), '')

    def test_typed_select_uses_requested_option_label_not_value_initial(self):
        options = [option('v1', 'Basic'), option('v2', 'Pro'), option('v3', 'Enterprise')]
        for before, value, key in (('v1', 'v2', 'p'), ('v2', 'v1', 'b'), ('v1', 'v3', 'e')):
            page = Page('select-one', before, options)
            self.reached('typed', page, value)
            self.assertEqual(page.calls[-2], ('keyboard', key))

    def test_typed_select_empty_value_with_unique_label_is_supported(self):
        self.reached('typed', Page('select-one', 'B', [option('', 'Empty'), option('B', 'Basic')]), '')

    def test_select_noops_are_rejected_before_action(self):
        for driver in ('native', 'typed'):
            self.reject(driver, Page('select-one', 'B'), 'B', 'No-op')

    def test_unknown_duplicate_or_wrong_typed_option_is_rejected_before_action(self):
        for driver in ('native', 'typed'):
            self.reject(driver, Page('select-one', 'A'), 'missing', '[Uu]nknown')
            self.reject(driver, Page('select-one', 'A', [option('A'), option('B'), option('B')]), 'B', 'ambiguous')
            for value in (1, True, None, []): self.reject(driver, Page('select-one', 'A'), value, '[Ss]tring')

    def test_disabled_hidden_or_grouped_option_profiles_are_rejected(self):
        for driver in ('native', 'typed'):
            for blocked_index in (0, 1):
                options = [option('A'), option('B')]; options[blocked_index]['blocked'] = True
                self.reject(driver, Page('select-one', 'A', options), 'B', '[Oo]ptions')

    def test_typed_typeahead_ambiguity_and_unsupported_keys_are_rejected(self):
        for label in ('Beta', '', 'Élite', '!Pro'):
            options = [option('A', 'Basic'), option('B', label)]
            self.reject('typed', Page('select-one', 'A', options), 'B', 'unique ASCII')

    def test_unsupported_control_families_are_rejected_before_action(self):
        for driver in DRIVERS:
            for kind in ('select-multiple', 'radio', 'file', 'number', 'button', 'password'):
                self.reject(driver, Page(kind), 'toy', '[Oo]utside')
        self.reject('transaction', Page('checkbox', False), True, '[Oo]utside')
        self.reject('transaction', Page('select-one', 'A'), 'B', '[Oo]utside')
        self.reject('native', Page('select-one', 'A', multiple=True), 'B', 'multiple select')

    def test_disabled_and_readonly_controls_do_not_start_actions(self):
        for driver in DRIVERS:
            for kwargs in (dict(enabled=False), dict(readonly=True)):
                page = Page(**kwargs); self.edit(driver, page, 'toy')
                self.assertEqual(page.calls[-1], ('blocked', 'a'))
                self.assertFalse(any(name == 'begin' for name, _ in page.calls))

    def test_target_count_handling_is_preserved(self):
        for driver in DRIVERS:
            self.reject(driver, Page(count=2), 'toy')
            if driver == 'native':
                page = Page(count=0); self.edit(driver, page, 'toy')
                self.assertEqual(page.calls[-1], ('absent', 'a'))
            else: self.reject(driver, Page(count=0), 'toy')

    def test_probe_failures_do_not_start_actions(self):
        for driver in DRIVERS:
            self.reject(driver, Page(probe_error=RuntimeError('owned probe failure')), 'toy', 'owned probe')

    def test_failed_native_operations_do_not_complete(self):
        cases = [('native', 'text', 'seed', ''), ('transaction', 'text', 'seed', ''),
                 ('typed', 'text', 'seed', ''), ('native', 'checkbox', False, True),
                 ('typed', 'checkbox', True, False), ('native', 'select-one', 'A', 'B'),
                 ('typed', 'select-one', 'A', 'B')]
        for driver, kind, before, value in cases:
            page = Page(kind, before, fail_operation=True)
            with self.assertRaisesRegex(RuntimeError, 'did not reach'):
                self.edit(driver, page, value)
            self.assertTrue(any(name == 'begin' for name, _ in page.calls))
            self.assertFalse(any(name == 'complete' for name, _ in page.calls))

    def test_current_native_fixture_operations_are_retained(self):
        for filename in ('multi/cases.json', 'native/historical-cases.json'):
            cases = json.loads((ROOT / 'fixtures' / filename).read_text(encoding='utf-8'))
            for case in cases:
                for field in case['fields']:
                    page = Page('select-one' if field['kind']=='select' else field['kind'],
                                field['initial'], [option('A'), option('B')])
                    self.reached('native', page, field['edit'])
                    operations = page.calls[2:-1]
                    if field['kind']=='checkbox': expected = [('click', None)]
                    elif field['kind']=='select':
                        expected = [('focus', None), ('press', 'Home'), ('press', 'ArrowDown'), ('press', 'Enter')]
                    else: expected = [('click', None), ('press', 'ControlOrMeta+A'), ('type', field['edit'])]
                    self.assertEqual(operations, expected, case['id'])

    def test_current_transaction_fixture_operations_are_retained(self):
        for fid, value in (('a','toy-a1'), ('b','toy-b1'), ('a','toy-a2'), ('b','toy-b2')):
            page = Page(); self.drivers['transaction'](page, fid, value)
            self.assertEqual(page.value, value)
            self.assertEqual(page.calls[2:], [('click', None), ('press', 'ControlOrMeta+A'),
                                            ('type', value), ('complete', 37)])
        options = [option('basic', 'Basic'), option('pro', 'Pro'), option('enterprise', 'Enterprise')]
        for kind, before, value, operation in (
                ('text','seed-name','toy-name1',('type','toy-name1')),
                ('text','toy-name1','toy-name2',('type','toy-name2')),
                ('checkbox',False,True,('check',None)), ('checkbox',True,False,('uncheck',None)),
                ('select-one','basic','pro',('keyboard','p')),
                ('select-one','basic','enterprise',('keyboard','e'))):
            page = Page(kind, before, options); self.reached('typed', page, value)
            self.assertEqual(page.calls[-2], operation)

    def test_option_snapshot_callbacks_detect_blocked_profiles(self):
        # Execute only these read-only JS callbacks on plain owned objects.
        for driver in ('native', 'typed'):
            _, function = edit_function(driver)
            source = next(n.value for n in ast.walk(function) if isinstance(n, ast.Constant)
                          and isinstance(n.value, str) and 'nodes.map' in n.value)
            program = """
const probe = eval('(' + SOURCE + ')');
const base = {value:'B',label:'  Pro  ',disabled:false,hidden:false,
              parentElement:{tagName:'SELECT'},style:{display:'block',visibility:'visible'}};
globalThis.getComputedStyle = node => node.style;
const nodes = [base,{...base,disabled:true},{...base,hidden:true},
  {...base,parentElement:{tagName:'OPTGROUP'}},
  {...base,style:{display:'none',visibility:'visible'}},
  {...base,style:{display:'block',visibility:'hidden'}}];
console.log(JSON.stringify(probe(nodes)));
""".replace('SOURCE', json.dumps(source))
            output = json.loads(subprocess.check_output(['node','--input-type=module','-e',program], timeout=10))
            self.assertEqual([o['blocked'] for o in output], [False, True, True, True, True, True])
            if driver == 'typed': self.assertEqual(output[0]['label'], 'Pro')


if __name__ == '__main__': unittest.main()
