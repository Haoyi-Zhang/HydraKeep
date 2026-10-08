#!/usr/bin/env python3
"""Check the actual browser exports of the shipped runtimes without networking."""
from __future__ import annotations
import json, os, pathlib
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parents[1]
def main() -> None:
    out = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'), headless=True, args=['--no-sandbox'])
        out['chromium'] = browser.version
        for name, expected in [('react', '19.1.1'), ('vue', '3.5.13')]:
            page = browser.new_page()
            try:
                page.set_content('<!doctype html><main>Runtime export check</main>')
                source = ROOT / f'vendor/{name}-{expected}.production.js'
                page.add_script_tag(content=source.read_text())
                value = page.evaluate('React.version' if name == 'react' else 'Vue.version')
                if value != expected:
                    raise RuntimeError(f'{name} exported {value!r}, expected {expected!r}')
                out[name] = {'expected': expected, 'observed': value, 'source_bytes': source.stat().st_size}
            finally:
                page.close()
        browser.close()
    (ROOT / 'results/runtime-versions.json').write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
if __name__ == '__main__':
    main()
