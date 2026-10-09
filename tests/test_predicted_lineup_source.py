#!/usr/bin/env python3
"""Source-qualified external XI must preserve actual coordinates, team and GW."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import importlib.util,json

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('expert',ROOT/'scripts/snapshot_predicted_lineups.py')
mod=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(mod)

def test():
    names=['Goalie','RB One','CB One','CB Two','LB One','Mid One',
           'Mid Two','AM One','RW One','LW One','Striker']
    li=''.join('<li class="Formation-module__X__player" style="--x:'+str(12+i*7)+'%;--y:'+str(87-i*7)+'%">'
        '<span class="Formation-module__X__name">'+n+'</span></li>' for i,n in enumerate(names))
    source='''<section aria-labelledby="chelsea-team-news"><h2>Chelsea Predicted Lineup</h2>
    <time dateTime="Mon Oct 05 2026 18:42:59 GMT+0000 (Coordinated Universal Time)">5 October 2026</time>
    <div class="Formation-module__X__fixtureGw">GW<!-- -->6</div>
    <div class="Formation-module__X__pitch" role="img" aria-label="Chelsea predicted lineup: '''
    source+=', '.join(names)+'"><ul class="Formation-module__X__players">'+li+'</ul></div></section>'
    official={'official_next_gw':6,'teams':[{'id':8,'name':'Chelsea','short_name':'CHE'}]}
    result=mod.parse(source,official,observed_at='2026-10-09T10:00:00Z')
    assert len(result['lineups'])==1,result
    team=result['lineups'][0]
    assert team['club']=='CHE' and team['gw']==6
    assert team['updated'].startswith('Mon Oct 05 2026')
    assert team['players'][0]=={'name':'Goalie','x':12.,'y':87.}
    assert len(team['players'])==11
    assert mod.parse(source,{**official,'official_next_gw':7})['lineups']==[]
    with TemporaryDirectory() as t:
        tmp=Path(t); in_path=tmp/'official.json';out_path=tmp/'expert.js'
        in_path.write_text(json.dumps(official))
        captured=mod.capture(official_path=in_path,out_path=out_path,fetch=lambda url:source)
        assert len(captured['lineups'])==1
        assert out_path.read_text().startswith('window.FPL_EXPERT_LINEUPS=')
        failed=mod.capture(official_path=in_path,out_path=out_path,fetch=lambda url:(_ for _ in ()).throw(OSError('offline')))
        assert failed['lineups']==[]
    print('EXPERT_LINEUP_PARSER_OK',len(team['players']),'pitch positions, GW cutoff and failure case')
if __name__=='__main__':test()
