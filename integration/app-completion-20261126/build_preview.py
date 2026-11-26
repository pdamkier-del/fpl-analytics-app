"""Append an isolated UI preview; every pre-existing Pages file stays byte-identical."""
import argparse,hashlib,shutil,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PREFIX='previews/team-transfers-20261126'
def hashes(root):return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()for p in root.rglob('*')if p.is_file()}
def build(site):
 before=hashes(site);source=site/'mm-preview';dest=site/PREFIX
 if not(source/'app/overview.html').is_file():raise ValueError('Actual Pages baseline missing')
 if dest.exists():shutil.rmtree(dest)
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
 # Reuse the exact currently deployed plan renderer, applying only UI orchestration changes.
 text=(source/'transfers-workspace.js').read_text()
 text=text.replace("document.querySelector('[data-open-alternatives]').addEventListener", "document.querySelector('[data-open-alternatives]')?.addEventListener")
 text=text.replace('FplPlannerExperience.mount(c);','if(!window.FplSharedTeam)FplPlannerExperience.mount(c);')
 text=text.replace("if(!latest||!c.state?.squad?.length)return null;", "if(!latest||!c.state?.squad?.length)return null;\n  const shared=window.FplSharedTeam?.status();if(shared?.actual?.squad?.length===15&&c.state.squad.every(p=>shared.actual.squad.some(q=>q.id===p.id)))return null;")
 text=text.replace("if(!c.state){status.innerHTML=", "if(window.FplSharedTeam&&!window.FplSharedTeam.status().actual){status.textContent='';return;}\n if(!c.state){status.innerHTML=")
 (dest/'transfers-workspace.js').write_text(text)
 # JSON stays on the existing sealed data source; no manager or forecast payload copied.
 for page in(dest/'app').glob('*.html'):
  text=page.read_text()
  if 'preview-data-root.js'not in text:text=text.replace('<head>','<head><script src="preview-data-root.js"></script>',1)
  if page.name=='advanced.html':text=text.replace('overview.html#','advanced-overview.html#')
  page.write_text(text)
 after=hashes(site)
 changed=[p for p,h in before.items()if not p.startswith(PREFIX+'/')and after.get(p)!=h]
 if changed:raise ValueError('Production files changed: '+','.join(changed[:4]))
 return dict(preview_path=PREFIX+'/app/overview.html',original_files_unchanged=len([p for p in before if not p.startswith(PREFIX+'/')]),preview_files=len([p for p in after if p.startswith(PREFIX+'/')]),models_recomputed=False,private_payloads_baked_in=False)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('site',type=Path);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args();a.receipt.write_text(json.dumps(build(a.site),indent=2)+'\n')
