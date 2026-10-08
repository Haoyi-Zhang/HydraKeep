import type {NextApiRequest,NextApiResponse} from 'next';
import fs from 'node:fs';
import path from 'node:path';
export default function receipt(req:NextApiRequest,res:NextApiResponse){
 const file=path.resolve(process.cwd(),'receipts.jsonl');
 if(req.method==='POST'){fs.appendFileSync(file,JSON.stringify({run:req.query.run,payload:req.body,receivedAt:Date.now()})+'\n');return res.status(200).json({ok:true});}
 const rows=fs.existsSync(file)?fs.readFileSync(file,'utf8').trim().split('\n').filter(Boolean).map(x=>JSON.parse(x)).filter(x=>x.run===req.query.run):[];
 return res.status(200).json(rows);
}
