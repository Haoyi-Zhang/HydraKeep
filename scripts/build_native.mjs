import {build} from 'esbuild';
import fs from 'node:fs';
import crypto from 'node:crypto';
const versions={original:'vue',before:'vue-before',after:'vue-after',current:'vue-current'};
fs.mkdirSync('vendor/native',{recursive:true});
const outputs=[];
for(const mode of ['development','production']){
 for(const framework of ['react','vue']){
  for(const [tag,pkg] of (framework==='react'?[['original','react']]:Object.entries(versions))){
   const code=framework==='react'?`
import * as R from 'react'; import * as D from 'react-dom/client'; import * as B from 'react-dom';
import {reactComponent} from './src/native/react-form.mjs';
window.multi={async mount(cfg){const App=reactComponent(R,cfg,hk,HANDLERS,B,true); B.flushSync(()=>D.hydrateRoot(document.getElementById('root'),R.createElement(App)));await new Promise(r=>setTimeout(r,0));},async commit(){hk.api.commit();},async settle(){await new Promise(r=>setTimeout(r,0));}};
`:`
import * as V from '${pkg}'; import {vueComponent} from './src/native/vue-form.mjs';
window.multi={async mount(cfg){V.createSSRApp(vueComponent(V,cfg,hk,HANDLERS,true)).mount('#root');await V.nextTick();},async commit(){hk.api.commit();await V.nextTick();},async settle(){await V.nextTick();}};
`;
   const name=`${framework}-${tag}-${mode}.js`;
   await build({stdin:{contents:code,resolveDir:process.cwd(),sourcefile:'client-entry.js'},bundle:true,format:'iife',platform:'browser',target:'es2020',outfile:'vendor/native/'+name,minify:mode==='production',define:{'process.env.NODE_ENV':JSON.stringify(mode),__VUE_OPTIONS_API__:'true',__VUE_PROD_DEVTOOLS__:'false',__VUE_PROD_HYDRATION_MISMATCH_DETAILS__:'false'}});
   outputs.push({name,framework,tag,mode,sha256:crypto.createHash('sha256').update(fs.readFileSync('vendor/native/'+name)).digest('hex')});
  }
 }
}
fs.writeFileSync('vendor/native/manifest.json',JSON.stringify(outputs,null,2));
console.log(JSON.stringify({builds:outputs.length}));
