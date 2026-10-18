"""Prevent a queued older Pages build replacing a newer verified forecast."""
import argparse,base64,json,os,hashlib
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

def identity(forecast):
    if forecast.get('locked_model_active') is not False or forecast.get('model')!='original_locked_vFinal_diagnostic':raise ValueError('Invalid diagnostic publication contract')
    return {k:forecast[k] for k in ('data_asof','gws','checksums')}

def preview_identity(index,publication):
    if index is None and publication is None:return None
    if not isinstance(index,dict) or not isinstance(publication,dict) or not publication.get('preview_source_commit'):
        raise ValueError('Incomplete MM preview publication identity')
    return dict(source_commit=publication['preview_source_commit'],index_sha256=hashlib.sha256(json.dumps(index,sort_keys=True,separators=(',',':')).encode()).hexdigest())

def verify(snapshot,current,current_preview=None):
    expected=identity(current)
    if {k:snapshot.get(k) for k in expected}!=expected:raise ValueError('Newer verified forecast exists; older Pages publication refused')
    if snapshot.get('mm_preview')!=current_preview:raise ValueError('Newer verified MM preview exists; older Pages publication refused')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--record',action='store_true');args=parser.parse_args()
    if args.record:
        snapshot=identity(json.loads(Path('app/vfinal-diagnostic.json').read_text()))
        def local(path):return json.loads(Path(path).read_text()) if Path(path).exists() else None
        snapshot['mm_preview']=preview_identity(local('app/mm-preview/current/index.json'),local('app/mm-preview/publication.json'))
        encoded=base64.b64encode(json.dumps(snapshot,sort_keys=True).encode()).decode()
        with open(os.environ['GITHUB_OUTPUT'],'a') as stream:stream.write('snapshot='+encoded+'\n')
    else:
        snapshot=json.loads(base64.b64decode(os.environ['PAGES_SNAPSHOT']))
        headers={'Accept':'application/vnd.github.raw+json','Cache-Control':'no-cache'}
        if os.environ.get('GITHUB_TOKEN'):headers['Authorization']='Bearer '+os.environ['GITHUB_TOKEN']
        def remote(path,optional=False):
            url='https://api.github.com/repos/pdamkier-del/fpl-analytics-app/contents/'+path+'?ref=free-github-static-20261010'
            try:
                with urlopen(Request(url,headers=headers),timeout=45) as response:value=json.load(response)
            except HTTPError as error:
                if optional and error.code==404:return None
                raise
            return json.loads(base64.b64decode(value['content'])) if 'content' in value else value
        current=remote('app/vfinal-diagnostic.json')
        preview=preview_identity(remote('app/mm-preview/current/index.json',True),remote('app/mm-preview/publication.json',True))
        verify(snapshot,current,preview)
        print('Current diagnostic and MM preview versions verified before serialized Pages deployment.')
if __name__=='__main__':main()
