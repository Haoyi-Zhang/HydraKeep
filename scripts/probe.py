#!/usr/bin/env python3
"""Actual environment, loopback endpoint unit probe, and policy failure record."""
import json,pathlib,subprocess,time,urllib.request,os,platform,shutil,socket
from playwright.sync_api import sync_playwright
ROOT=pathlib.Path(__file__).resolve().parents[1]
def get(url):
    with urllib.request.urlopen(url,timeout=3) as r:
        text=r.read().decode()
        try:return json.loads(text)
        except json.JSONDecodeError:return text
def main():
    out={'python':platform.python_version(),'node':subprocess.check_output(['node','-v'],text=True).strip(),'cpu_visible':os.cpu_count(),'cpu_quota':pathlib.Path('/sys/fs/cgroup/cpu.max').read_text().strip(),'memory_limit_bytes':int(pathlib.Path('/sys/fs/cgroup/memory.max').read_text()),'disk_free_bytes':shutil.disk_usage(ROOT).free,'network_env':os.environ.get('NETWORK'),'no_policy_changes':True}
    p=subprocess.Popen(['node','src/server.mjs'],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        for _ in range(30):
            try:out['node_health']=get('http://127.0.0.1:8765/health');break
            except Exception:time.sleep(.1)
        else:raise RuntimeError('local Node endpoint did not become healthy')
        for typ,body in [('application/json',b'{"value":"toy-endpoint"}'),('application/x-www-form-urlencoded',b'value=toy-native')]:
            req=urllib.request.Request('http://127.0.0.1:8765/submit?run=probe',data=body,headers={'Content-Type':typ},method='POST')
            with urllib.request.urlopen(req,timeout=3) as r:assert r.status==200
        out['non_browser_endpoint_records']=get('http://127.0.0.1:8765/records?run=probe')
        out['endpoint_evidence_scope']='Python HTTP client to local Node server only; not browser submission'
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH','/usr/bin/chromium'),headless=True,args=['--no-sandbox']);out['chromium']=browser.version
            page=browser.new_page()
            try:
                page.goto('http://127.0.0.1:8765/health',timeout=4000);out['browser_localhost']='navigation allowed'
            except Exception as e:out['browser_localhost']='blocked or unavailable';out['browser_error']=str(e)
            page.close();browser.close()
    finally:
        p.terminate();p.wait(timeout=5)
    try:socket.getaddrinfo('registry.npmjs.org',443);out['npm_dns']='resolved'
    except OSError as e:out['npm_dns']=str(e)
    (ROOT/'results/environment.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
if __name__=='__main__':main()
