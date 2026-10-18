#!/usr/bin/env python3
"""Reuse the existing app verbatim, with isolated B data/plan routing only.

No model fitting, simulation, TS changes or private state are involved.
Generated pages remain inside mm-preview/app; production files are untouched.
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def build(root=ROOT):
    app = root / 'app'
    out = app / 'mm-preview/app'
    out.mkdir(parents=True, exist_ok=True)
    for src in app.iterdir():
        if not src.is_file() or src.suffix not in {'.html', '.js', '.css', '.svg', '.webmanifest'}:
            continue
        text = src.read_text()
        if src.suffix in {'.html', '.js'}:
            # Explicit B identity, never disguise B as the original MM.
            text = text.replace('original_locked_vFinal_diagnostic', 'B_locked_PM_preview')
            text = text.replace('original_locked_MM_assignment', 'B_MM_assignment')
            text = text.replace('fpl-manager-plan-v1', 'fpl-manager-plan-B-preview-v1')
            text = text.replace('fpl-private-job', 'fpl-private-B-preview-job')
            text = text.replace('fpl-wait-for-forecast', 'fpl-B-wait-for-forecast')
            text = text.replace("service.url+'/plans',{method:'POST'", "service.url+'/preview/plans',{method:'POST'")
            text = text.replace('Original MM', 'Individuel MM B').replace('originale MM → vFinal', 'MM B → låst vFinal')
            if src.name == 'catalog-data.js':
                text = text.replace('xp,xmins:valid?', 'xp,pplay:usable?number(first?.p_play):null,xmins:valid?')
                text = text.replace('number(r.matches)>0', '(number(r.matches)>0||number(r.share)>0)')
            if src.name == 'roles-view.js':
                text = text.replace('esc(r.matches)', "esc(r.matches??'Not Available')")
            if src.name == 'classic-catalog.js':
                text = text.replace("['pstart','Avg P(start)']", "['pstart','Avg P(start)'],['pplay','P(spiller) næste GW']")
                text = text.replace("if(key==='pstart')", "if(key==='pstart'||key==='pplay')")
            if src.name in {'classic-manager.js', 'weekly-app.js'}:
                # Preview must not treat synthetic validation fixtures as actual teams.
                text = text.replace('if(!raw||raw.season', 'if(!raw||raw.validation_only===true||raw.season')
                text = text.replace("report.supports_idempotent_submit!==true", "(report.supports_idempotent_submit!==true||report.supports_mm_preview!==true)")
                text = text.replace("if(!r.ok){sessionStorage.removeItem('fpl-private-B-preview-job');", "if(!r.ok){if([404,410,422].includes(r.status))sessionStorage.removeItem('fpl-private-B-preview-job');")
                text = text.replace("if(d.status==='completed'){", "if(d.status==='failed'){sessionStorage.removeItem('fpl-private-B-preview-job');throw Error(d.error||'Python-beregningen fejlede. Dit hold er bevaret.')}if(d.status==='completed'){const latest=await window.FplBExistingApp.forecast();if(latest.forecast_sha256!==forecast.forecast_sha256){sessionStorage.removeItem('fpl-private-B-preview-job');throw Error('Nyt forecast er publiceret. Genindlæs og genberegn; dit hold er bevaret.')}")
            if src.suffix == '.html':
                # Runs before any inline loader. The adapter never alters storage.
                text = text.replace('<head>', '<head><script src="../existing-app-adapter.js?v=1"></script>', 1)
        (out / src.name).write_text(text)
    # Static optional assets remain local; JSON is routed by the verified adapter.
    for name in ['assets', 'icons']:
        if (app / name).is_dir():
            shutil.copytree(app / name, out / name, dirs_exist_ok=True)
    return out


def source_data(bootstrap, fixtures, provenance, forecast, mm):
    """Translate official raw fields and already selected XI; no model logic."""
    official = dict(fetched_at=provenance['bootstrap_observed_at'], next_gw=forecast['gws'][0],
                    season=forecast['season'], teams={str(t['id']): t for t in bootstrap['teams']},
                    players=[dict(p, position=p['element_type'], price=p['now_cost']/10)
                             for p in bootstrap['elements']])
    schedule = dict(fetched_at=official['fetched_at'], fixtures=[dict(
        id=f['id'], gw=f['event'], home=f['team_h'], away=f['team_a'],
        kickoff=f['kickoff_time'], finished=f['finished'], started=f['started'],
        home_score=f['team_h_score'], away_score=f['team_a_score'],
        difficulty_home=f['team_h_difficulty'], difficulty_away=f['team_a_difficulty']) for f in fixtures])
    lineups = dict(source='B_MM_assignment', cutoff=forecast['data_asof'],
                   checksums=forecast.get('checksums'), locked_model_active=False, fixtures=[])
    for team in mm['teams']:
        rows = [p for p in mm['players'] if p['club_id'] == team['club_id'] and p['fixture_id'] == team['fixture_id']]
        selected = sorted((p for p in rows if p['expected_xi']), key=lambda p: p['slot_index'])
        if len(selected) != 11 or sum(p['slot'] == 'GK' for p in selected) != 1:
            continue  # Do not invent a formation if source assignment is unavailable.
        sizes = [1] + [int(n) for n in team['formation'].split('-')]
        layers, offset = [], 0
        for size in sizes:
            layers.append([p['slot'] for p in selected[offset:offset+size]])
            offset += size
        if offset != 11:
            raise ValueError('B formation does not contain 11 slots')
        lineups['fixtures'].append(dict(team_id=team['club_id'], fixture_uuid=team['fixture_id'],
            gw=rows[0]['gw'], kickoff=next(q['kickoff'] for p in forecast['players'] for w in p['weeks']
                for q in w['fixtures'] if q['fixture_uuid'] == team['fixture_id']),
            formation=team['formation'], layers=layers, players=[dict(id=p['fpl_element'],
                selected=p['expected_xi'], unavailable=p['availability'] in ['OUT', 'SUSPENDED'] and p['xmins'] == 0,
                role=p['slot'] or p['primary_role'] or 'UNKNOWN',
                # B exports weighted shares, not raw counts of past starts.
                observed_roles=[dict(role=k, matches=None, share=v) for k,v in p.get('role_probabilities', {}).items()]) for p in rows]))
    return {'current-players.json': official, 'live-fixtures.json': schedule, 'club-lineups.json': lineups}


if __name__ == '__main__':
    print(build())
