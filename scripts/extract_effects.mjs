/** Conservative read/write extraction for the authored transition subset.
 * Unknown syntax is TOP. Dynamic properties, calls, aliases and nested closures
 * are not guessed. This analyzes code executed in the browser, not contract files.
 */
import fs from 'node:fs';
import * as acorn from '../vendor/acorn.mjs';
export function effect(fn){
 const r=new Set(),w=new Set();let known=true;
 const member=n=>n?.type==='MemberExpression'&&n.object.type==='Identifier'&&n.object.name==='s'&&!n.computed&&n.property.type==='Identifier'?n.property.name:null;
 function expr(n){
  if(!n){known=false;return;}
  if(n.type==='Literal'){if(n.regex||n.bigint||!(n.value===null||['string','boolean','number'].includes(typeof n.value)))known=false;return;}
  if(n.type==='Identifier'){if(n.name!=='v')known=false;return;}
  const k=member(n);if(k!==null){r.add('state:'+k);return;}
  if(n.type==='AssignmentExpression'&&n.operator==='='){
   const k=member(n.left);if(k===null)known=false;else w.add('state:'+k);expr(n.right);return;
  }
  if(n.type==='BinaryExpression'&&['+','-','===','!=='].includes(n.operator)){expr(n.left);expr(n.right);return;}
  known=false;
 }
 if(fn.type!=='ArrowFunctionExpression'||fn.async||fn.params.length!==2||fn.params[0].name!=='s'||fn.params[1].name!=='v'||fn.body.type!=='BlockStatement')known=false;
 else for(const s of fn.body.body){if(s.type==='ExpressionStatement')expr(s.expression);else known=false;}
 return {known,reads:[...r].sort(),writes:[...w].sort(),unknown_effects:!known};
}
export function extract(source){
 const tree=acorn.parse(source,{ecmaVersion:2022});const output=Object.create(null);
 for(const st of tree.body){
  const e=st.expression;
  if(st.type==='ExpressionStatement'&&e.type==='AssignmentExpression'&&e.operator==='='&&e.left.type==='MemberExpression'&&!e.left.computed&&e.left.object.name==='window'&&e.left.property.name==='HANDLERS'&&e.right.type==='ObjectExpression'){
   for(const p of st.expression.right.properties){
    if(p.type!=='Property'||p.computed||p.kind!=='init'||p.method)throw Error('unsupported handler declaration');
    const key=p.key.name??p.key.value;
    if(typeof key!=='string'||Object.hasOwn(output,key)||['__proto__','constructor','prototype'].includes(key))throw Error('invalid or duplicate handler name');
    output[key]=effect(p.value);
   }
  }else throw Error('unsupported top-level source');
 }
 return output;
}
if(process.argv[2]){let start=performance.now();const effects=extract(fs.readFileSync(process.argv[2],'utf8'));console.log(JSON.stringify({parser:acorn.version,scope:'closed state-member assignment subset',analysis_ms:performance.now()-start,effects},null,2));}
