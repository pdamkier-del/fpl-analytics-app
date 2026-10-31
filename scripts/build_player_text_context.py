"""Export manually reviewed public context; no forecast or manager writes."""
from pathlib import Path
import argparse,json,hashlib
ROOT=Path(__file__).resolve().parents[1]

def build(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);records=[]
    old=json.loads((ROOT/'analysis/results/player-context-sources-20261025/evidence.json').read_text())
    for r in old['records']:
        role=r['evidence_category']in ['coach_role_conditional','coach_tactical_instruction','coach_trust']
        records.append(dict(player_id=r['player_id'],team_id=r['fpl_team_id'],category=r['evidence_category'],source_url=r['source_url'],excerpt=r['excerpt'],published_at=r['source_published_at'],observed_at=r['first_observed_in_this_review'],interpretation=r['interpretation_da'],qualification=r['qualification_da'],scope='role_context'if role else 'historical_match',source_kind='Trænercitat'if r['direct_coach_quote']else 'Klubbens artikel',model_input_enabled=False))
    extra=json.loads((ROOT/'analysis/results/pl-club-context-20261025/primary-samples.json').read_text())
    summaries={454:('Træneren beskrev mulighed for en trupplads, men ikke kapacitet til 90 minutter.','Udtalelsen gjaldt Palace-kampen 25. oktober. Det er ikke en ny minutbegrænsning til næste kamp.'),366:('Wirtz skal vurderes efter et slag på anklen. Klubben beskriver de tidlige tegn som positive.','Tidlig optimisme er ikke en bekræftet raskmelding eller en sikker start.'),346:('Klubbens optakt beskrev Calvert-Lewin som tvivlsom med en fodskade.','Oplysningen gjaldt Sunderland-kampen; hans status til næste kamp er ikke fastlagt af denne artikel.')}
    for r in extra['records']:
        pid=r['player_id']
        if pid not in summaries:continue
        s=r['source'];summary,qualification=summaries[pid]
        records.append(dict(player_id=pid,team_id=r['team_id'],category=r['category'],source_url=s['url'],excerpt=r['excerpt'],published_at=r['source_published_at'],observed_at=s['observed_at'],interpretation=summary,qualification=qualification,scope='dated_status'if pid==366 else 'historical_match',source_kind='Trænercitat'if pid==454 else 'Klubbens artikel',model_input_enabled=False))
    source=ROOT/'analysis/results/pl-club-context-20261025';coverage=json.loads((source/'editorial-coverage.json').read_text());text=(source/'README.md').read_text();summaries={}
    for line in text.splitlines():
        if not line.startswith('| ')or line.startswith('| Klub'):continue
        cells=[c.strip()for c in line.strip('|').split('|')]
        if len(cells)==2:summaries[cells[0]]=cells[1]
    teams=[]
    for t in coverage['clubs']:
        teams.append(dict(team_id=t['team_id'],summary=summaries.get(t['team_name'],'Kildebelagt klubkontekst er indsamlet; individuel vurdering mangler.'),source_url=t['source_url'],observed_at=t['observed_at'],source_updated_label=t['source_updated_label'],scope='GW8_historical',model_input_enabled=False))
    data=dict(schema='player-text-context-v1',season='2026-27',observed_at=max(r['observed_at']for r in records),records=records,teams=teams,forecast_effect='none',automatic_refresh=False)
    raw=(json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n').encode();(out/'evidence.json').write_bytes(raw)
    index=dict(schema='player-text-context-index-v1',file='evidence.json',sha256=hashlib.sha256(raw).hexdigest(),observed_at=data['observed_at'])
    (out/'index.json').write_text(json.dumps(index,sort_keys=True)+'\n');print(json.dumps(dict(players=len({r['player_id']for r in records}),records=len(records),clubs=len(teams),sha256=index['sha256'])))
    return data
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=ROOT/'app/mm-preview/text-context');a=p.parse_args();build(a.out)
