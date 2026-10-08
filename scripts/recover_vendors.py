#!/usr/bin/env python3
"""Recover exactly the already-installed runtime sections used in this study.
This performs no network access. Default paths describe the measured environment;
pass --react-bundle and --vue-bundle in a different installation.
"""
import pathlib,argparse
ROOT=pathlib.Path(__file__).resolve().parents[1]
a=argparse.ArgumentParser()
a.add_argument('--react-bundle',type=pathlib.Path,default=pathlib.Path('/opt/pyvenv/lib/python3.13/site-packages/playwright/driver/package/lib/vite/traceViewer/assets/defaultSettingsView-BEpdCv1S.js'))
a.add_argument('--vue-bundle',type=pathlib.Path,default=pathlib.Path('/opt/pyvenv/lib/python3.13/site-packages/trame_client/module/vue3-www/vue.global.js'))
v=a.parse_args();s=v.react_bundle.read_text()
for marker in ['var Yf={exports:{}}','const gt=L1(H);','var Pf={exports:{}}','const Mb=new Map']:
    if s.count(marker)!=1:raise SystemExit('Unexpected source layout; refusing approximate extraction: '+marker)
out=s[s.index('var Yf={exports:{}}'):s.index('const gt=L1(H);')]+s[s.index('var Pf={exports:{}}'):s.index('const Mb=new Map')]
out+='\nglobalThis.React=H;globalThis.ReactDOM=s2;globalThis.ReactDOMBase=X1();\n'
vue=v.vue_bundle.read_text()
if 'vue v3.5.13' not in vue:raise SystemExit('Expected Vue 3.5.13 source header')
(ROOT/'vendor/react-19.1.1.production.js').write_text(out)
(ROOT/'vendor/vue-3.5.13.production.js').write_text(vue)
print('Recovered runtime library sections. Run the browser smoke test to validate exports.')
