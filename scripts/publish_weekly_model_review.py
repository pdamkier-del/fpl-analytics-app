"""Publish the review within the existing B path, preserving models and production."""
import json,os,subprocess,tarfile,tempfile
from pathlib import Path
from weekly_model_review import build
from publish_mm_preview import main as publish
from publish_dashboard_news import fingerprints
ROOT=Path(__file__).resolve().parents[1]
def main():
    subprocess.run(['git','fetch','origin','free-github-static-20261010'],check=True)
    ref='FETCH_HEAD';parent=subprocess.check_output(['git','rev-parse',ref],text=True).strip()
    with tempfile.TemporaryDirectory(prefix='fpl-weekly-')as folder:
        archive=Path(folder)/'preview.tar'
        with archive.open('wb')as output:subprocess.run(['git','archive',parent,'app/mm-preview'],stdout=output,check=True)
        with tarfile.open(archive)as tar:tar.extractall(folder,filter='data')
        source=Path(folder)/'app/mm-preview';before=fingerprints(source);receipt=json.loads((source/'publication.json').read_text());result=build(source,ref)
        after=fingerprints(source)
        assert all(after[k]==v for k,v in before.items()if not k.startswith('weekly-review/')),'Weekly review changed UI/model data'
        os.environ['MM_PREVIEW_SOURCE_DIR']=str(source);os.environ['PREVIEW_SOURCE_SHA']=receipt['preview_source_commit'];publish()
        Path('work/weekly-model-review-proof.json').write_text(json.dumps(dict(updated_at=result['updated_at'],completed_scored_gws=result['completed_scored_gws'],model_files_unchanged=True,production_changed=False),indent=2)+'\n')
if __name__=='__main__':main()
