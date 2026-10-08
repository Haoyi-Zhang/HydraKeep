#!/usr/bin/env python3
"""Primary metadata recheck; retrieval success is separate from claim verification."""
import concurrent.futures,datetime,difflib,json,pathlib,re,sys,requests
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'artifact/scripts'))
from audit_paper import entries
def normalized(x):return re.sub('[^a-z0-9]','',re.sub(r'\\[A-Za-z]+','',x).lower())
def check(pair):
 key,b=pair;row={'key':key,'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'title':b['title'],'doi':b.get('doi'),'url':b.get('url')}
 try:
  if b.get('doi'):
   r=requests.get('https://api.crossref.org/works/'+b['doi'],timeout=20)
   if r.status_code==404 and b['doi'].startswith('10.4230/'):
    r=requests.get('https://drops.dagstuhl.de/entities/document/'+b['doi'],timeout=20);r.raise_for_status();row.update(primary='Dagstuhl publisher DOI landing page',http_status=r.status_code,final_url=r.url,status='retrieved');return row
   r.raise_for_status();m=r.json()['message'];title=': '.join(m.get('title',[])+m.get('subtitle',[]))
   row.update(primary='Crossref registration metadata',metadata=m,title_similarity=difflib.SequenceMatcher(None,normalized(b['title']),normalized(title)).ratio(),status='retrieved')
  else:
   r=requests.get(b['url'],timeout=20);row.update(http_status=r.status_code,final_url=r.url,status='retrieved' if r.ok else 'unavailable',primary='specified primary anchor',content_excerpt=r.text[:150])
 except Exception as e:row.update(status='unavailable',error=str(e))
 return row
def main():
 pairs=list(entries((ROOT/'paper/references.bib').read_text()).items())
 with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:rows=list(pool.map(check,pairs))
 out=ROOT/'paper/reference-recheck-20261005.json';out.write_text(json.dumps(rows,ensure_ascii=False,indent=2))
 print(json.dumps({'entries':len(rows),'retrieved':sum(x['status']=='retrieved' for x in rows),'title_mismatches':[{k:x.get(k) for k in ['key','title','title_similarity']} for x in rows if x.get('title_similarity',1)<.88],'unavailable':[x['key'] for x in rows if x['status']=='unavailable']},indent=2))
if __name__=='__main__':main()
