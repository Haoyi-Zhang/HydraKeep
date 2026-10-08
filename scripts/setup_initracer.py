#!/usr/bin/env python3
"""Build an unchanged pinned analyzer locally; no upstream source redistribution."""
import argparse,json,pathlib,shutil,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--destination',required=True);args=ap.parse_args();dest=pathlib.Path(args.destination).resolve()
if dest.exists():raise SystemExit('Choose a new destination so an existing checkout is never overwritten.')
subprocess.run(['git','clone','https://github.com/cs-au-dk/initracer.git',str(dest)],check=True)
commit='b5f1c0bffd118008c64b30ec3723b2443b6d95cf';subprocess.run(['git','checkout',commit],cwd=dest,check=True)
# This lock pins the packaging dependencies used for the measured analyzer bundle.
shutil.copy2(ROOT/'scripts/initracer/package.json',dest/'package.json')
shutil.copy2(ROOT/'scripts/initracer/package-lock.json',dest/'package-lock.json')
subprocess.run(['npm','ci','--ignore-scripts','--no-audit','--no-fund'],cwd=dest,check=True)
(dest/'out').mkdir(exist_ok=True)
with (dest/'out/raw-bundle.js').open('wb') as f:subprocess.run(['node','node_modules/browserify/bin/cmd.js','-r','./src/analysis.js:initracer'],cwd=dest,stdout=f,check=True)
raw=(dest/'out/raw-bundle.js').read_text();(dest/'out/bundle.js').write_text("(function(){if(typeof window.initRacer==='object')return;var require;\n"+raw+"\nrequire('initracer')();})();\n")
shutil.copy2(ROOT/'scripts/initracer/control-server.cjs',dest/'control-server.cjs')
(dest/'HYDRAKEEP-BUILD.json').write_text(json.dumps({'commit':commit,'analyzer_sources_modified':False,'driver':'custom local HTTP and browser input','excluded_dependencies':['images','chokidar','lsof'],'scope':'original HTML/JS instrumenters and observation analysis; not original proxy/Protractor pipeline'},indent=2)+'\n')
print(dest)
