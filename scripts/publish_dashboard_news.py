"""Refresh only public availability news, preserving the deployed B app/model."""
import hashlib,json,os,re,subprocess,tarfile,tempfile
from pathlib import Path
import requests
from collect_dashboard_news import build,seal,URL
from publish_mm_preview import main as publish
ROOT=Path(__file__).resolve().parents[1]

def fingerprints(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()for p in root.rglob('*')if p.is_file() and p.relative_to(root).parts[0]!='news'and p.name!='publication.json'}

def main():
    subprocess.run(['git','fetch','origin','free-github-static-20261010'],cwd=ROOT,check=True)
    parent=subprocess.check_output(['git','rev-parse','FETCH_HEAD'],cwd=ROOT,text=True).strip()
    with tempfile.TemporaryDirectory(prefix='fpl-public-news-')as folder:
        archive=Path(folder)/'preview.tar'
        with archive.open('wb')as output:subprocess.run(['git','archive',parent,'app/mm-preview'],cwd=ROOT,stdout=output,check=True)
        with tarfile.open(archive)as tar:tar.extractall(folder,filter='data')
        source=Path(folder)/'app/mm-preview';before=fingerprints(source)
        receipt=json.loads((source/'publication.json').read_text());ui=receipt['preview_source_commit']
        if not re.fullmatch('[a-f0-9]{40}',ui):raise ValueError('Unknown existing UI provenance')
        response=requests.get(URL,timeout=45,headers={'Cache-Control':'no-cache','User-Agent':'FPLAnalyticsAvailability/1'});response.raise_for_status()
        news=build(response.json());news=seal(dict(news,collector_source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()))
        out=source/'news/availability.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(news,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n')
        assert before==fingerprints(source),'News refresh altered existing UI or model files'
        os.environ['MM_PREVIEW_SOURCE_DIR']=str(source);os.environ['PREVIEW_SOURCE_SHA']=ui
        publish()
        # The publisher may preserve additional immutable historical receipts,
        # but must not modify any existing app/model file during a news refresh.
        after=fingerprints(ROOT/'.mm-preview-site/mm-preview')
        assert all(after.get(name)==digest for name,digest in before.items())
        record=dict(ui_source_unchanged=ui,existing_preview_files_preserved=True,existing_preview_files=len(before),news_observed_at=news['observed_at'],source_url=URL)
        (ROOT/'work/dashboard-news-publication.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
if __name__=='__main__':main()
