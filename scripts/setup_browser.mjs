#!/usr/bin/env node
/** Extract the pinned Linux Chromium binary using ordinary file operations. */
import fs from 'node:fs';
import path from 'node:path';
import zlib from 'node:zlib';
import {pipeline} from 'node:stream/promises';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const packageRoot=path.resolve(path.dirname(require.resolve('@sparticuz/chromium')),'../..');
const destination=process.argv[2]||'/tmp/hydrakeep-chromium';
await fs.promises.mkdir(path.dirname(destination),{recursive:true});
await pipeline(fs.createReadStream(path.join(packageRoot,'bin/chromium.br')),zlib.createBrotliDecompress(),fs.createWriteStream(destination));
await fs.promises.chmod(destination,0o755);
console.log(JSON.stringify({binary:destination,package:'@sparticuz/chromium',packageVersion:'143.0.4'}));
