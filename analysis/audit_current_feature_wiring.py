"""Read-only wiring audit against exact published current inputs; no refits."""
import argparse,hashlib,json
from pathlib import Path
import pandas as pd
from trace_player_points import load_inputs

def audit(forecast,inputs):
    load_inputs(forecast,inputs) # Checks every sealed input byte checksum.
    b=json.loads((inputs/'bootstrap.json').read_text());prov=json.loads((inputs/'provenance.json').read_text());players={p['id']:p for p in forecast['players']};target=pd.read_csv(inputs/'target.csv.gz',low_memory=False);roles=pd.read_csv(inputs/'roles.csv.gz',low_memory=False);cut=pd.Timestamp(prov['data_at']);departures=[];midweek=[]
    for p in b['elements']:
        text=p.get('news','').lower();kind='permanent'if 'permanently'in text else 'season_loan'if 'on loan for the rest of the season'in text else None
        if p['status']=='u'and kind:
            future=[dict(gw=w['gw'],xmins=w['xmins'],xp=w['xpts'])for w in players[p['id']]['weeks'][1:]if w['xmins']>1e-8]
            if future:departures.append(dict(id=p['id'],name=p['web_name'],position=p['element_type'],kind=kind,source_news=p['news'],future=future))
        if p['id']not in players:continue
        person=players[p['id']];q=target[target.player_uuid.eq(person['player_uuid'])].sort_values('gw')
        if q.empty:continue
        h=roles[roles.player_uuid.eq(person['player_uuid'])].copy();h['kick_time']=pd.to_datetime(h.kickoff,utc=True);h=h[h.kick_time.gt(cut-pd.Timedelta(days=7))&h.kick_time.lt(cut)&pd.to_datetime(h.known_at,utc=True).lt(cut)];extra=h[h.competition.ne('prem')]
        if extra.empty:continue
        midweek.append(dict(id=p['id'],name=p['web_name'],MM_minutes_7d=float(q.iloc[0].minutes_7d),MM_rest_days=float(q.iloc[0].rest_days),verified_nonPL_starter_minutes_7d=float(extra.minutes.sum()),known_nonPL_games=extra[['competition','kickoff','minutes','known_at']].to_dict('records'),latest_verified_starter_rest_days=float((cut-h.kick_time.max()).total_seconds()/86400)))
    by={p['id']:p for p in b['elements']};sav=next(p for p in forecast['players']if p['name']=='Sávio')
    return dict(schema='current-code-wiring-audit-v1',forecast_sha256=forecast['forecast_sha256'],input_checksums_verified=True,scope='Frozen 31 October published forecast, not a future live-state claim',source_scopes=prov['source_scopes'],persistent_departures_with_future_minutes=len(departures),departure_position_counts=pd.Series([r['position']for r in departures]).value_counts().to_dict(),departures=departures,missing_nonPL_load_examples=midweek,future_priority=forecast['role_assignment']['future_priority'],dated_injury_example=dict(id=sav['id'],name=sav['name'],news=by[sav['id']]['news'],weeks=[dict(gw=w['gw'],minutes=w['xmins'],fixtures=[r['kickoff']for r in w['fixtures']])for w in sav['weeks']]),production_changed=False)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--forecast',type=Path,required=True);p.add_argument('--inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=audit(json.loads(a.forecast.read_text()),a.inputs);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,indent=2,ensure_ascii=False,default=lambda x:int(x))+'\n');print(json.dumps({k:v for k,v in r.items()if k not in ['departures','missing_nonPL_load_examples','dated_injury_example']},ensure_ascii=False))
