#!/usr/bin/env python3
"""Report latest forecast attempt without replacing the last verified forecast."""
import base64,json,os,urllib.request,urllib.error
from datetime import datetime,timezone
URL='https://api.github.com/repos/pdamkier-del/fpl-analytics-app/contents/app/diagnostic-pipeline-status.json'
BRANCH='free-github-static-20261010'
def main():
    status=os.environ['FORECAST_JOB_STATUS']
    if status not in ('success','failure','cancelled'):raise ValueError('Unknown job status')
    payload=dict(status=status,observed_at=datetime.now(timezone.utc).isoformat(),workflow='https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],locked_model_active=False)
    headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2026-03-10','Content-Type':'application/json'}
    for attempt in range(3):
        body=dict(message='Record diagnostic forecast attempt '+status,branch=BRANCH,content=base64.b64encode((json.dumps(payload)+'\n').encode()).decode())
        try:
            with urllib.request.urlopen(urllib.request.Request(URL+'?ref='+BRANCH,headers=headers),timeout=30) as response:body['sha']=json.load(response)['sha']
        except urllib.error.HTTPError as e:
            if e.code!=404:raise
        try:
            with urllib.request.urlopen(urllib.request.Request(URL,headers=headers,method='PUT',data=json.dumps(body).encode()),timeout=30) as response:json.load(response)
            print('Recorded forecast attempt',status);return
        except urllib.error.HTTPError as e:
            if e.code not in (409,422) or attempt==2:raise
if __name__=='__main__':main()
