"""A real Chromium pilot; only localhost traffic and authored toy strings."""
import json, subprocess, time, urllib.request, pathlib
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=subprocess.Popen(['node','src/server.mjs'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:
    for _ in range(50):
        try: urllib.request.urlopen('http://127.0.0.1:8765/health',timeout=1);break
        except Exception:time.sleep(.1)
    with sync_playwright() as pw:
        b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=b.new_page()
        page.set_content('<div id=unrelated></div><div id=root></div>');page.evaluate('window.CFG={id:"R01",kind:"text",design:"controlled",initial:"seed"};window.RUN="pilot";window.OBSERVATION_ONLY=true');page.add_script_tag(content=(ROOT/'src/observer.js').read_text())
        page.add_script_tag(content=(ROOT/'vendor/react-19.1.1.production.js').read_text());page.add_script_tag(content=(ROOT/'src/react-adapter.js').read_text())
        page.evaluate('adapter.mount(CFG,true)')
        html=page.locator('#root').inner_html()
        (ROOT/'fixtures/rendered.json').write_text(json.dumps({'R01':{'html':html,'origin':'ReactDOM.createRoot browser prerender'}}))
        page.close();page=b.new_page();page.set_content('<div id=unrelated></div><div id=root>'+html+'</div>');page.evaluate('window.CFG={id:"R01",kind:"text",design:"controlled",initial:"seed"};window.RUN="pilot";window.OBSERVATION_ONLY=true');page.add_script_tag(content=(ROOT/'src/observer.js').read_text())
        page.locator('[data-hk-field]').click();page.locator('[data-hk-field]').press('ControlOrMeta+A');page.locator('[data-hk-field]').press_sequentially('toy-early')
        out={'before':page.evaluate('__hk.snapshot()')}
        page.add_script_tag(content=(ROOT/'vendor/react-19.1.1.production.js').read_text());page.add_script_tag(content=(ROOT/'src/react-adapter.js').read_text())
        page.evaluate('adapter.mount(CFG)');out['hydrated']=page.evaluate('__hk.snapshot()')
        page.evaluate('adapter.commit()');out['committed']=page.evaluate('__hk.snapshot()')
        page.locator('#submit').click();page.wait_for_function('__hk.trace.some(e=>e.type==="application-intent")')
        out['trace']=page.evaluate('__hk.trace');out['endpoint']=json.load(urllib.request.urlopen('http://127.0.0.1:8765/records?run=pilot'))
        out['evidence_class']='offline-real-Chromium; no endpoint submission';out['browser']=b.version;out['framework']=page.evaluate('React.version')
        (ROOT/'results/pilot.json').write_text(json.dumps(out,indent=2));print(json.dumps({k:v for k,v in out.items() if k!='trace'},indent=2));b.close()
finally:
    p.terminate();p.wait(timeout=5)
