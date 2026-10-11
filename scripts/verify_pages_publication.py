"""Prevent a queued older Pages build replacing a newer verified forecast."""
import argparse,base64,json,os
from pathlib import Path
from urllib.request import Request,urlopen

def identity(forecast):
    if forecast.get('locked_model_active') is not False or forecast.get('model')!='original_locked_vFinal_diagnostic':raise ValueError('Invalid diagnostic publication contract')
    return {k:forecast[k] for k in ('data_asof','gws','checksums')}

def verify(snapshot,current):
    if snapshot!=identity(current):raise ValueError('Newer verified forecast exists; older Pages publication refused')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--record',action='store_true');args=parser.parse_args()
    if args.record:
        snapshot=identity(json.loads(Path('app/vfinal-diagnostic.json').read_text()))
        encoded=base64.b64encode(json.dumps(snapshot,sort_keys=True).encode()).decode()
        with open(os.environ['GITHUB_OUTPUT'],'a') as stream:stream.write('snapshot='+encoded+'\n')
    else:
        snapshot=json.loads(base64.b64decode(os.environ['PAGES_SNAPSHOT']))
        headers={'Accept':'application/vnd.github.raw+json','Cache-Control':'no-cache'}
        if os.environ.get('GITHUB_TOKEN'):headers['Authorization']='Bearer '+os.environ['GITHUB_TOKEN']
        url='https://api.github.com/repos/pdamkier-del/fpl-analytics-app/contents/app/vfinal-diagnostic.json?ref=free-github-static-20261010'
        with urlopen(Request(url,headers=headers),timeout=45) as response:current=json.load(response)
        if 'content' in current:current=json.loads(base64.b64decode(current['content']))
        verify(snapshot,current)
        print('Current diagnostic cutoff and checksums verified before serialized Pages deployment.')
if __name__=='__main__':main()
