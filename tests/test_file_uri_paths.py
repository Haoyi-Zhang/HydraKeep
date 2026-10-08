"""Exercise the native server's exact base expression without launching it."""
import json
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class FileURIPathTests(unittest.TestCase):
    def base_path(self, module_uri, *, windows=None):
        source = (ROOT / 'src' / 'native-server.mjs').read_text()
        self.assertIn("import {fileURLToPath} from 'node:url'", source)
        declaration = re.search(r'^const base=(.+);$', source, re.MULTILINE)
        self.assertIsNotNone(declaration)
        expression = declaration.group(1).replace('import.meta.url', 'moduleURI')
        code = ("import nodePath from 'node:path';import {fileURLToPath as convert} from 'node:url';"
                'const moduleURI=' + json.dumps(module_uri) + ';'
                'const windows=' + json.dumps(windows) + ';'
                'const path=windows===null?nodePath:windows?nodePath.win32:nodePath.posix;'
                'const fileURLToPath=uri=>convert(uri,windows===null?undefined:{windows});'
                'console.log(JSON.stringify(' + expression + '));')
        return json.loads(subprocess.check_output(
            ['node', '--input-type=module', '-e', code], cwd=ROOT, timeout=10))

    def test_current_unicode_space_project_resolves_fixture_base(self):
        module = ROOT / 'src' / 'native-server.mjs'
        resolved = pathlib.Path(self.base_path(module.as_uri()))
        self.assertEqual(resolved, ROOT)
        self.assertTrue((resolved / 'fixtures' / 'multi' / 'cases.json').is_file())
        self.assertTrue((resolved / 'fixtures' / 'native' / 'historical-cases.json').is_file())

    def test_windows_drive_unicode_spaces_and_drive_root(self):
        for folder in (pathlib.PureWindowsPath('D:/space name/内部'),
                       pathlib.PureWindowsPath('C:/'), pathlib.PureWindowsPath('D:/')):
            with self.subTest(folder=str(folder)):
                uri = (folder / 'src' / 'native-server.mjs').as_uri()
                resolved = pathlib.PureWindowsPath(self.base_path(uri, windows=True))
                self.assertEqual(resolved, folder)

    def test_posix_unicode_space_percent_and_fragment_characters(self):
        folder = pathlib.PurePosixPath('/tmp/space name/内部/%hash#')
        uri = (folder / 'src' / 'native-server.mjs').as_uri()
        self.assertEqual(pathlib.PurePosixPath(self.base_path(uri, windows=False)), folder)

    def test_as_uri_preserves_standard_file_uri_layout(self):
        self.assertEqual(pathlib.PureWindowsPath('D:/').as_uri(), 'file:///D:/')
        self.assertEqual(pathlib.PureWindowsPath('D:/space name/内部').as_uri(),
                         'file:///D:/space%20name/%E5%86%85%E9%83%A8')
        self.assertEqual(pathlib.PurePosixPath('/space name/内部').as_uri(),
                         'file:///space%20name/%E5%86%85%E9%83%A8')


if __name__ == '__main__':
    unittest.main()
