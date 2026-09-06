from __future__ import annotations
import json,time
from pathlib import Path
import requests
from yt_dlp import YoutubeDL
from smart_http_guard import read_limited_bytes, validate_https_url
from smart_procedural_caption_extract import extract_caption
OFFICIAL='UCPbhr02AfVb2nd5pm12BxTw'
SRC=Path('runtime/procedural_sources/MEGA_PROCEDURAL_CRONOGRAM_DATASET.json')
OUTDIR=Path('runtime/procedural_sources/youtube_captions')
OUT=Path('runtime/procedural_sources/YOUTUBE_PROCEDURAL_RECENT.json')
CAPTION_MAX_BYTES=8*1024*1024
CAPTION_HOST_SUFFIXES=('youtube.com','googlevideo.com')
def find_official(contest,date_iso):
 y,m,d=date_iso.split('-'); q=f'ytsearch6:Loterias CAIXA {d}/{m}/{y}'
 with YoutubeDL({'quiet':True,'extract_flat':True,'skip_download':True}) as ydl: info=ydl.extract_info(q,download=False)
 for e in info.get('entries',[]):
  if e.get('channel_id')==OFFICIAL and str(contest) in (e.get('description') or ''): return {'id':e['id'],'url':e['url'],'title':e.get('title')}
 return None
def caption_url(video_url):
 with YoutubeDL({'quiet':True,'skip_download':True}) as ydl: info=ydl.extract_info(video_url,download=False)
 caps=info.get('automatic_captions') or {}; choices=caps.get('pt-orig') or caps.get('pt') or []
 for c in choices:
  if c.get('ext')=='json3': return c.get('url')
 return None
def main():
 OUTDIR.mkdir(parents=True, exist_ok=True)
 d=json.loads(SRC.read_text(encoding='utf-8')); rows=[r for r in d['rows'] if r['evidence_status'].startswith('VERIFIED')][-15:]; out=[]
 for r in rows:
  contest=int(r['contest']); date=r['draw_date']; print('SEARCH',contest,date,flush=True)
  try: hit=find_official(contest,date)
  except Exception as exc:
   out.append({'contest':contest,'draw_date':date,'status':'SEARCH_ERROR','error_type':type(exc).__name__}); continue
  if not hit:
   out.append({'contest':contest,'draw_date':date,'status':'OFFICIAL_VIDEO_NOT_FOUND'}); continue
  try: cu=caption_url(hit['url'])
  except Exception as exc:
   out.append({'contest':contest,'draw_date':date,'status':'CAPTION_AUTH_OR_ACCESS_REQUIRED','video_id':hit['id'],'video_url':hit['url'],'error_type':type(exc).__name__}); print('ACCESS',contest,type(exc).__name__,flush=True); continue
  if not cu:
   out.append({'contest':contest,'draw_date':date,'status':'AUTO_CAPTION_NOT_FOUND','video_id':hit['id'],'video_url':hit['url']}); continue
  try:
   cu=validate_https_url(cu,allowed_host_suffixes=CAPTION_HOST_SUFFIXES); cp=OUTDIR/f"{hit['id']}.pt-orig.json3"; resp=requests.get(cu,timeout=20,stream=True); resp.raise_for_status(); cp.write_bytes(read_limited_bytes(resp,max_bytes=CAPTION_MAX_BYTES))
   ev=extract_caption(cp,contest,hit['id'],hit['url']); ev['draw_date']=date; ev['status']='PASS'; ev['video_title']=hit['title']; out.append(ev); print('PASS',contest,ev.get('ball_case_identifier'),ev.get('opening_seal_identifier'),flush=True)
  except Exception as exc:
   out.append({'contest':contest,'draw_date':date,'status':'CAPTION_PARSE_ERROR','video_id':hit['id'],'video_url':hit['url'],'error_type':type(exc).__name__}); print('PARSE_ERROR',contest,type(exc).__name__,flush=True)
  time.sleep(0.1)
 doc={'schema':'SMART_YOUTUBE_PROCEDURAL_RECENT_V1','channel_id':OFFICIAL,'rows':out,'pass_count':sum(x.get('status')=='PASS' for x in out),'auth_or_access_count':sum(x.get('status')=='CAPTION_AUTH_OR_ACCESS_REQUIRED' for x in out),'same_contest_predictive_weight_authorized':False}
 OUT.write_text(json.dumps(doc,indent=2,ensure_ascii=False),encoding='utf-8'); print(json.dumps({'pass_count':doc['pass_count'],'auth_or_access_count':doc['auth_or_access_count'],'rows':len(out)},ensure_ascii=False))
if __name__=='__main__': main()
