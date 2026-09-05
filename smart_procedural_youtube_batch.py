from __future__ import annotations
import argparse,json,time,subprocess,sys
from pathlib import Path
from yt_dlp import YoutubeDL
from smart_procedural_caption_extract import extract_caption
OFFICIAL='UCPbhr02AfVb2nd5pm12BxTw'
SRC=Path('runtime/procedural_sources/MEGA_PROCEDURAL_CRONOGRAM_DATASET.json')
CAP=Path('runtime/procedural_sources/youtube_captions'); CAP.mkdir(parents=True,exist_ok=True)
def find_official(contest,date_iso):
 y,m,d=date_iso.split('-'); q=f'ytsearch6:Loterias CAIXA {d}/{m}/{y}'
 with YoutubeDL({'quiet':True,'extract_flat':True,'skip_download':True}) as ydl: info=ydl.extract_info(q,download=False)
 for e in info.get('entries',[]):
  if e.get('channel_id')==OFFICIAL and str(contest) in (e.get('description') or ''): return {'id':e['id'],'url':e['url'],'title':e.get('title')}
 return None
def acquire_caption(hit):
 cp=CAP/f"{hit['id']}.pt-orig.json3"
 if cp.exists() and cp.stat().st_size>1000: return cp
 cmd=[sys.executable,'-m','yt_dlp','--quiet','--write-auto-subs','--sub-langs','pt-orig','--sub-format','json3','--skip-download','-o',str(CAP/'%(id)s.%(ext)s'),hit['url']]
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=90)
 if r.returncode!=0 or not cp.exists(): raise RuntimeError('caption acquisition failed')
 return cp
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--offset',type=int,default=0); ap.add_argument('--count',type=int,default=15); a=ap.parse_args()
 d=json.loads(SRC.read_text(encoding='utf-8')); allrows=[r for r in d['rows'] if r['evidence_status'].startswith('VERIFIED')]
 end=max(0,len(allrows)-a.offset); start=max(0,end-a.count); rows=allrows[start:end]; out=[]
 for r in rows:
  contest=int(r['contest']); date=r['draw_date']; print('SEARCH',contest,date,flush=True)
  try: hit=find_official(contest,date)
  except Exception as exc: out.append({'contest':contest,'draw_date':date,'status':'SEARCH_ERROR','error_type':type(exc).__name__}); continue
  if not hit: out.append({'contest':contest,'draw_date':date,'status':'OFFICIAL_VIDEO_NOT_FOUND'}); continue
  try:
   cp=acquire_caption(hit); ev=extract_caption(cp,contest,hit['id'],hit['url']); ev['draw_date']=date; ev['status']='PASS'; ev['video_title']=hit['title']; out.append(ev); print('PASS',contest,ev.get('ball_case_identifier'),ev.get('opening_seal_identifier'),flush=True)
  except Exception as exc:
   out.append({'contest':contest,'draw_date':date,'status':'CAPTION_AUTH_OR_ACCESS_REQUIRED','video_id':hit['id'],'video_url':hit['url'],'error_type':type(exc).__name__}); print('ACCESS',contest,type(exc).__name__,flush=True)
  time.sleep(0.1)
 path=Path(f'runtime/procedural_sources/YOUTUBE_PROCEDURAL_BATCH_offset{a.offset}_count{a.count}.json'); doc={'schema':'SMART_YOUTUBE_PROCEDURAL_BATCH_V2','offset':a.offset,'count':a.count,'rows':out,'pass_count':sum(x.get('status')=='PASS' for x in out),'same_contest_predictive_weight_authorized':False}; path.write_text(json.dumps(doc,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps({'file':str(path),'pass_count':doc['pass_count'],'rows':len(out)},ensure_ascii=False))
if __name__=='__main__': main()
