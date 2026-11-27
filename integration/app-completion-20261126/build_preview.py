"""Append an isolated UI preview; every pre-existing Pages file stays byte-identical."""
import argparse,hashlib,shutil,json,re
from pathlib import Path
from reviewed_baseline import REVIEW,verify_site
ROOT=Path(__file__).resolve().parent
PREFIX='previews/team-transfers-20261126'
def hashes(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()for p in root.rglob('*')if p.is_file()}
def build(site,replace_preview=False):
 before=hashes(site);source=site/'mm-preview';dest=site/PREFIX
 if not(source/'app/overview.html').is_file():raise ValueError('Actual Pages baseline missing')
 if dest.exists():
  if not replace_preview:raise ValueError('Preview destination already exists; refusing to overwrite existing Pages files')
  shutil.rmtree(dest)
 shutil.copytree(source/'app',dest/'app')
 for path in source.iterdir():
  if path.is_file()and path.suffix in ['.js','.css']:shutil.copy2(path,dest/path.name)
 (dest/'gk').mkdir(exist_ok=True)
 for name in ['contract.js','app.js']:
  if(source/'gk'/name).is_file():shutil.copy2(source/'gk'/name,dest/'gk'/name)
 # Keep the actual expert dashboard reachable, not a replacement/fork of its logic.
 shutil.copy2(source/'app/overview.html',dest/'app/advanced-overview.html')
 for path in(ROOT/'ui').iterdir():
  if path.name not in ['advanced-overview.html','classic-manager.js','advanced.html']:shutil.copy2(path,dest/'app'/path.name)
 client=dest/'app/classic-manager.js';text=client.read_text();anchor='onChange();FplPlannerExperience.mount(snapshot());feedback();'
 if text.count(anchor)!=1:raise ValueError('Existing manager-client render anchor changed')
 client.write_text(text.replace(anchor,'onChange();if(!window.FplSharedTeam)FplPlannerExperience.mount(snapshot());feedback();'))
 text=client.read_text();anchor='function resumeIfRequested(){'
 if text.count(anchor)!=1:raise ValueError('Existing manager resume anchor changed')
 client.write_text(text.replace(anchor,anchor+"if(window.FplSharedTeam&&!window.FplSharedTeam.status().actual)return;"))
 # Reuse the exact deployed renderer; require every orchestration anchor.
 text=(source/'transfers-workspace.js').read_text()
 def replace_once(text,old,new):
  if text.count(old)!=1:raise ValueError('Existing UI anchor changed: '+old[:65])
  return text.replace(old,new,1)
 text=replace_once(text,"document.querySelector('[data-open-alternatives]').addEventListener", "document.querySelector('[data-open-alternatives]')?.addEventListener")
 text=replace_once(text,'FplPlannerExperience.mount(c);','if(!window.FplSharedTeam)FplPlannerExperience.mount(c);')
 text=replace_once(text,"if(!latest||!c.state?.squad?.length)return null;", "if(!latest||!c.state?.squad?.length)return null;\n  const shared=window.FplSharedTeam?.status();if(shared?.actual?.squad?.length===15&&c.state.squad.every(p=>shared.actual.squad.some(q=>q.id===p.id)))return null;")
 text=replace_once(text,"if(!c.state){status.innerHTML=", "if(window.FplSharedTeam&&!window.FplSharedTeam.status().actual){button.disabled=true;status.textContent='';return;}\n if(!c.state){status.innerHTML=")
 text=replace_once(text,"if(drift?.needsConfirmation&&!drift.confirmed){button.disabled=true;", "const sharedOfficial=window.FplSharedTeam?.status().actual;if(sharedOfficial&&(!Number.isInteger(sharedOfficial.bank_tenths)||!c.state?.squad?.every(p=>sharedOfficial.squad.some(q=>q.id===p.id)))){button.disabled=true;status.textContent='TS v3 afventer verificerede købspriser, bank og gratis transfers for den officielle trup.';return;}\n if(drift?.needsConfirmation&&!drift.confirmed){button.disabled=true;")
 text=replace_once(text,"if(fetchingLatest||snap.busy)return;", "const official=window.FplSharedTeam?.status().actual;if(official&&(!Number.isInteger(official.bank_tenths)||!snap.state?.squad?.every(p=>official.squad.some(q=>q.id===p.id)))){draw();return;}\n if(fetchingLatest||snap.busy)return;")
 text=replace_once(text,"function failed(e){target.replaceChildren();status.textContent=", "function failed(e){target.replaceChildren();if(window.FplSharedTeam&&!window.FplSharedTeam.status().actual){status.textContent='';return;}status.textContent=")
 anchor='try{await FplManagerClient.load();draw();FplTransferPreview.render();FplManagerClient.bind'
 text=replace_once(text,anchor,"window.addEventListener('fpl-official-team-ready',async()=>{try{await FplManagerClient.load();draw();}catch(e){failed(e);}});\n"+anchor)
 (dest/'transfers-workspace.js').write_text(text)
 importer=dest/'app/manager-import.js';text=importer.read_text()
 if 'window.FplOfficialManagerImport'not in text:
  if not all(name in text for name in ['function fromOfficialHistory','function reconcileOfficialHistory','function loadInitialPrices']):raise ValueError('Official importer functions missing')
  importer.write_text(text+'\nwindow.FplOfficialManagerImport=Object.freeze({fromOfficialHistory,reconcileOfficialHistory,loadInitialPrices});\n')
 # Explain the unchanged two-hour guard; do not relax freshness/identity rules.
 gate=dest/'app/forecast-window.js';text=gate.read_text()
 text=text.replace("reason: 'Den aktuelle officielle gameweek og deadline kan ikke bekræftes.'", "reason: Number.isFinite(observed)&&now-observed>2*3600000?'FPL-status fra '+new Date(observed).toLocaleString('da-DK')+' er mere end to timer gammel. Datatjenesten skal opdatere status, før TS v3 kan beregnes.':'Den aktuelle officielle gameweek eller deadline mangler eller matcher ikke. Afventer verificerede data.'")
 gate.write_text(text)
 # JSON stays on the existing sealed data source; no manager or forecast payload copied.
 assets={p.name:hashlib.sha256(p.read_bytes()).hexdigest()[:16]for p in(ROOT/'ui').iterdir()if p.suffix in ['.js','.css']}
 assets['classic-manager.js']=hashlib.sha256((dest/'app/classic-manager.js').read_bytes()).hexdigest()[:16]
 for page in(dest/'app').glob('*.html'):
  text=page.read_text()
  if 'preview-data-root.js'not in text:text=text.replace('<head>','<head><script src="preview-data-root.js"></script>',1)
  if page.name=='advanced.html':text=text.replace('overview.html#','advanced-overview.html#')
  # Existing browser installations must load matching new renderer/helper bytes.
  for name,digest in assets.items():
   text=re.sub(r'((?:src|href)=")'+re.escape(name)+r'(?:\?[^"\s]*)?(\")',lambda m:m[1]+name+'?asset='+digest+m[2],text)
  page.write_text(text)
 after=hashes(site)
 preserved={p:h for p,h in before.items()if not(replace_preview and p.startswith(PREFIX+'/'))}
 changed=[p for p,h in preserved.items()if after.get(p)!=h]
 if changed:raise ValueError('Production files changed: '+','.join(changed[:4]))
 return dict(preview_path=PREFIX+'/app/overview.html',original_files_unchanged=len(preserved),preview_files=len([p for p in after if p.startswith(PREFIX+'/')]),models_recomputed=False,private_payloads_baked_in=False)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('site',type=Path);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--baseline',type=Path,default=REVIEW);a=p.parse_args()
 review=json.loads(a.baseline.read_text());verify_site(a.site,review)
 receipt=build(a.site,replace_preview=review.get('replaceable_preview_prefix')==PREFIX+'/');receipt.update(verify_site(a.site,review,allow_preview=True));receipt['baseline_sha256']=hashlib.sha256(a.baseline.read_bytes()).hexdigest()
 a.receipt.write_text(json.dumps(receipt,indent=2)+'\n')
