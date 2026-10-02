#!/usr/bin/env python3
"""Ingest FPL-Core-Insights detailed lineups + average positions into P(start) v2.

Expected directory layout (one or more GW folders):
  GW1/fixtures.csv
  GW1/lineups.csv
  GW1/average_positions.csv
  ...

Identity is converted immediately to the standing-model policy:
  external_player_id = internal stable player_uuid
  team_external_id   = '<season>:<FPL team_id>'

Starter roles are inferred from confirmed formation + normalized average-position
coordinates. Substitute roles are assigned to the nearest starter-role anchor when
an average position exists. Unused bench players are retained with role=NULL so
recent start/minutes history sees a tactical bench appearance without inventing a role.
"""
from __future__ import annotations
import argparse, json, math, sqlite3
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd

ROLE_FAMILY={
    'GK':'GK',
    'RB':'DEF','RWB':'DEF','RCB':'DEF','CB':'DEF','LCB':'DEF','LWB':'DEF','LB':'DEF',
    'RDM':'MID','DM':'MID','LDM':'MID','RCM':'MID','CM':'MID','LCM':'MID',
    'RAM':'AM','AM':'AM','LAM':'AM','RW':'AM','LW':'AM',
    'SS':'FWD','ST':'FWD',
}


def team_key(season, team_id): return f"{season}:{int(team_id)}"


def parse_formation(v):
    try:
        parts=[int(x) for x in str(v).strip().split('-') if str(x).strip()]
    except Exception:
        return []
    return parts if sum(parts)==10 and 2 <= len(parts) <= 5 else []


def defensive_roles(n):
    return {
        2:['RCB','LCB'],
        3:['RCB','CB','LCB'],
        4:['RB','RCB','LCB','LB'],
        5:['RWB','RCB','CB','LCB','LWB'],
    }.get(n,['CB']*n)


def attacking_roles(n):
    return {
        1:['ST'],
        2:['ST','ST'],
        3:['RW','ST','LW'],
        4:['RW','ST','ST','LW'],
        5:['RW','RAM','ST','LAM','LW'],
    }.get(n,['ST']*n)


def middle_roles(layers, idx):
    """Roles for formation layer idx (0=defensive line, last=forward line)."""
    n=layers[idx]; middle_count=len(layers)-2; depth=idx-1
    back=layers[0]
    if n==1:
        return ['DM'] if depth==0 else ['AM']
    if n==2:
        if middle_count>=2:
            return ['RDM','LDM'] if depth==0 else ['RAM','LAM']
        return ['RCM','LCM']
    if n==3:
        if middle_count>=2 and depth>0:
            return ['RAM','AM','LAM']
        return ['RCM','CM','LCM']
    if n==4:
        if back==3 and depth==0:
            return ['RWB','RCM','LCM','LWB']
        return ['RW','RCM','LCM','LW']
    if n==5:
        if back==3 and depth==0:
            return ['RWB','RCM','CM','LCM','LWB']
        return ['RW','RCM','CM','LCM','LW']
    return ['CM']*n


def role_pattern(layers, idx):
    if idx==0: return defensive_roles(layers[0])
    if idx==len(layers)-1: return attacking_roles(layers[-1])
    return middle_roles(layers,idx)


def _sort_y(df):
    x=df.copy()
    x['_y']=pd.to_numeric(x['y'],errors='coerce')
    x['_y']=x['_y'].fillna(50.0)
    return x.sort_values(['_y','player_id'],kind='stable')


def assign_starter_roles(starters: pd.DataFrame, formation: str):
    """Return player_id -> role using formation lines and average x/y.

    Preferred path uses source broad D/M/F counts to protect against aggressive
    fullbacks crossing midfielders in average-x. If source counts do not match the
    formation, fall back to x-ordered layer assignment.
    """
    layers=parse_formation(formation)
    s=starters.copy()
    s=s[s.position.astype(str).str.upper()!='G'].copy()
    if not layers or len(s)!=10:
        return {}
    s['x']=pd.to_numeric(s['x'],errors='coerce'); s['y']=pd.to_numeric(s['y'],errors='coerce')
    s['position']=s.position.astype(str).str.upper()
    line_frames=[]
    d=s[s.position=='D']; f=s[s.position=='F']; m=s[~s.index.isin(d.index) & ~s.index.isin(f.index)]
    if len(d)==layers[0] and len(f)==layers[-1] and len(m)==sum(layers[1:-1]):
        line_frames=[d]
        if len(layers)>2:
            mm=m.sort_values(['x','y'],kind='stable')
            k=0
            for n in layers[1:-1]:
                line_frames.append(mm.iloc[k:k+n]); k+=n
        line_frames.append(f)
    else:
        # Geometric fallback: average x is normalized from own goal -> opponent goal.
        o=s.sort_values(['x','y'],kind='stable')
        k=0
        for n in layers:
            line_frames.append(o.iloc[k:k+n]); k+=n

    out={}
    for idx,(frame,n) in enumerate(zip(line_frames,layers)):
        roles=role_pattern(layers,idx)
        ordered=_sort_y(frame)
        if len(roles)!=len(ordered): return {}
        for row,role in zip(ordered.itertuples(index=False),roles):
            out[str(row.player_id)]=role
    return out


def nearest_sub_role(row, anchors):
    if not anchors or pd.isna(row.x) or pd.isna(row.y):
        p=str(row.position).upper()
        return {'G':'GK','D':'CB','M':'CM','F':'ST'}.get(p)
    broad=str(row.position).upper()
    allowed={
        'G':{'GK'},
        'D':{'DEF'},
        'M':{'MID','AM','DEF'},  # wing-backs are often source-position M
        'F':{'FWD','AM'},
    }.get(broad,{'DEF','MID','AM','FWD','GK'})
    best=None
    for role,(ax,ay) in anchors.items():
        fam=ROLE_FAMILY.get(role,'MID')
        dist=math.hypot(float(row.x)-ax,float(row.y)-ay)
        penalty=0.0 if fam in allowed else 22.0
        cost=dist+penalty
        if best is None or cost<best[0]: best=(cost,role)
    return best[1] if best else None


def source_player_map(con, season):
    rows=con.execute("""SELECT external_id,player_uuid FROM player_id_mapping
                        WHERE id_namespace='fpl_element' AND season=?""",(season,)).fetchall()
    return {str(r[0]):str(r[1]) for r in rows}


def mode_team(obs, gw, uuids):
    if not uuids: return None
    z=obs[(obs.gw==int(gw)) & obs.player_uuid.isin(uuids)]
    if z.empty:return None
    c=Counter(int(x) for x in z.team_id.dropna())
    return c.most_common(1)[0][0] if c else None


def fixture_for(obs, gw, home_team, away_team, kickoff=None):
    z=obs[(obs.gw==int(gw)) & (obs.team_id==int(home_team)) &
          (obs.opponent_team_id==int(away_team)) & (obs.was_home==1)]
    ids=list(z.fixture_uuid.dropna().unique())
    if len(ids)==1:return str(ids[0])
    if kickoff is not None and len(ids)>1:
        zz=z.copy(); zz['ko']=pd.to_datetime(zz.kickoff_at,utc=True,errors='coerce')
        target=pd.to_datetime(kickoff,utc=True,errors='coerce')
        if pd.notna(target):
            zz['delta']=(zz.ko-target).abs()
            if zz.delta.notna().any(): return str(zz.sort_values('delta').iloc[0].fixture_uuid)
    return None


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--db',default='data_v1_1/normalized/fpl_v1_1.sqlite3')
    ap.add_argument('--season',default='2025-26')
    ap.add_argument('--input-root',required=True,help='directory containing GW*/ fixtures/lineups/average_positions CSVs')
    ap.add_argument('--source-name',default='fpl_core_insights_detailed')
    ap.add_argument('--replace-source',action='store_true')
    ap.add_argument('--audit-out',default='data_v1_1/reports/fpl_core_role_ingest_audit.json')
    a=ap.parse_args()
    con=sqlite3.connect(a.db)
    if a.replace_source:
        mids=[r[0] for r in con.execute('SELECT source_match_id FROM club_matches_v2 WHERE source_name=?',(a.source_name,))]
        if mids:
            q=','.join('?'*len(mids)); con.execute(f'DELETE FROM player_match_roles_v2 WHERE source_match_id IN ({q})',mids)
            con.execute(f'DELETE FROM club_matches_v2 WHERE source_match_id IN ({q})',mids)
            con.commit()

    root=Path(a.input_root)
    line_files=sorted(root.glob('GW*/lineups.csv'),key=lambda p:int(p.parent.name[2:]))
    if not line_files: raise SystemExit(f'no GW*/lineups.csv under {root}')
    line=[]; avg=[]; fix=[]
    for lp in line_files:
        gw=int(lp.parent.name[2:])
        l=pd.read_csv(lp); l['gw']=gw; line.append(l)
        apath=lp.parent/'average_positions.csv'; fpath=lp.parent/'fixtures.csv'
        if apath.exists():
            x=pd.read_csv(apath); x['gw']=gw; avg.append(x)
        if fpath.exists():
            x=pd.read_csv(fpath); x['gw_folder']=gw; fix.append(x)
    line=pd.concat(line,ignore_index=True); avg=pd.concat(avg,ignore_index=True) if avg else pd.DataFrame()
    fix=pd.concat(fix,ignore_index=True) if fix else pd.DataFrame()
    pmap=source_player_map(con,a.season)
    line['player_uuid']=line.player_id.astype(str).map(pmap)
    if not avg.empty: avg['player_uuid']=avg.player_id.astype(str).map(pmap)
    obs=pd.read_sql_query("""SELECT player_uuid,gw,team_id,opponent_team_id,was_home,fixture_uuid,kickoff_at,minutes
                             FROM player_fixture_observations WHERE season=?""",con,params=[a.season])
    obs['player_uuid']=obs.player_uuid.astype(str)

    audit=defaultdict(int); match_audit=[]
    audit['lineup_rows']=len(line); audit['lineup_player_ids_mapped']=int(line.player_uuid.notna().sum())
    audit['average_position_rows']=len(avg); audit['average_position_ids_mapped']=int(avg.player_uuid.notna().sum()) if len(avg) else 0

    # Attach average x/y by match + source player id.
    if len(avg):
        coords=avg[['match_id','player_id','x','y']].copy(); coords['player_id']=coords.player_id.astype(str)
        line['player_id_key']=line.player_id.astype(str)
        line=line.merge(coords,left_on=['match_id','player_id_key'],right_on=['match_id','player_id'],how='left',suffixes=('','_coord'))
        line.drop(columns=['player_id_coord'],errors='ignore',inplace=True)
    else:
        line['x']=float('nan'); line['y']=float('nan')

    fixture_meta={}
    if len(fix):
        for r in fix.itertuples(index=False): fixture_meta[str(r.match_id)]=r

    for (gw,match_id),mg in line.groupby(['gw','match_id'],sort=True):
        home=mg[mg.team_side.astype(str).str.lower()=='home']; away=mg[mg.team_side.astype(str).str.lower()=='away']
        hteam=mode_team(obs,gw,set(home.player_uuid.dropna().astype(str)))
        ateam=mode_team(obs,gw,set(away.player_uuid.dropna().astype(str)))
        meta=fixture_meta.get(str(match_id)); kickoff=getattr(meta,'kickoff_time',None) if meta is not None else None
        fu=fixture_for(obs,gw,hteam,ateam,kickoff) if hteam is not None and ateam is not None else None
        if fu is None:
            audit['matches_unmapped_fixture']+=1
            match_audit.append({'gw':int(gw),'match_id':str(match_id),'status':'fixture_unmapped','home_team':hteam,'away_team':ateam})
            continue
        ko=pd.to_datetime(kickoff,utc=True,errors='coerce')
        if pd.isna(ko):
            zz=obs[obs.fixture_uuid.astype(str)==str(fu)]
            ko=pd.to_datetime(zz.kickoff_at.iloc[0],utc=True,errors='coerce') if len(zz) else pd.NaT
        if pd.isna(ko):
            audit['matches_missing_kickoff']+=1; continue
        src_mid='fplcore:'+str(match_id)
        slug=str(match_id).split('-prem-',1)[-1]
        if '-vs-' in slug: hname,aname=slug.split('-vs-',1)
        else: hname,aname=f'team-{hteam}',f'team-{ateam}'
        observed=(ko+pd.Timedelta(hours=3)).isoformat()
        con.execute("""INSERT OR REPLACE INTO club_matches_v2
          (source_match_id,season,kickoff_at,competition,competition_stage,round_strength,
           home_team_name,away_team_name,home_team_external_id,away_team_external_id,source_name,payload_path,observed_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (src_mid,a.season,ko.isoformat(),'PL',f'GW{int(gw)}',None,hname,aname,team_key(a.season,hteam),team_key(a.season,ateam),a.source_name,str(root),observed))

        for side,team in [('home',hteam),('away',ateam)]:
            sg=mg[mg.team_side.astype(str).str.lower()==side].copy()
            if sg.empty: continue
            formation=str(sg.formation.dropna().iloc[0]) if sg.formation.notna().any() else ''
            starters=sg[sg.is_starting.astype(str).str.lower().isin(['true','1','yes'])].copy()
            starter_roles=assign_starter_roles(starters,formation)
            if len(starter_roles)!=10:
                audit['team_lineups_role_inference_failed']+=1
            # Role anchors from actual starter average positions.
            anchors_raw=defaultdict(list)
            for r in starters.itertuples(index=False):
                role=starter_roles.get(str(r.player_id))
                if role and pd.notna(r.x) and pd.notna(r.y): anchors_raw[role].append((float(r.x),float(r.y)))
            anchors={role:(sum(x for x,_ in pts)/len(pts),sum(y for _,y in pts)/len(pts)) for role,pts in anchors_raw.items()}

            for r in sg.itertuples(index=False):
                if pd.isna(r.player_uuid):
                    audit['rows_skipped_unmapped_player']+=1; continue
                pid=str(r.player_uuid)
                zz=obs[(obs.fixture_uuid.astype(str)==str(fu)) & (obs.player_uuid==pid)]
                mins=float(zz.minutes.max()) if len(zz) and zz.minutes.notna().any() else 0.0
                started=str(r.is_starting).lower() in {'true','1','yes'}
                role=starter_roles.get(str(r.player_id)) if started else None
                if not started and mins>0:
                    rr=type('SubRow',(),{'x':r.x,'y':r.y,'position':r.position})
                    role=nearest_sub_role(rr,anchors)
                    if role: audit['sub_roles_inferred']+=1
                if not started and mins<=0: role=None
                con.execute("""INSERT OR REPLACE INTO player_match_roles_v2
                  (source_match_id,external_player_id,player_name,team_external_id,started,minutes,in_matchday_squad,
                   role,role_x,role_y,source_name,observed_at)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (src_mid,pid,str(r.player_name),team_key(a.season,team),int(started),mins,1,role,
                   None if pd.isna(r.x) else float(r.x),None if pd.isna(r.y) else float(r.y),a.source_name,observed))
                audit['role_rows_inserted']+=1
                if role: audit['rows_with_role']+=1
        audit['matches_inserted']+=1
        match_audit.append({'gw':int(gw),'match_id':str(match_id),'status':'ok','fixture_uuid':fu,
                            'home_team_external_id':team_key(a.season,hteam),'away_team_external_id':team_key(a.season,ateam)})
    con.commit()
    report={'summary':dict(audit),'matches':match_audit}
    out=Path(a.audit_out); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'summary':dict(audit),'audit_out':str(out)},indent=2))

if __name__=='__main__': main()
