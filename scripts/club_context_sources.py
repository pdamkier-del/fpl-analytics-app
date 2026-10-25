"""Free 20-club editorial context reader. Shadow evidence, never model inputs.

Preserves publisher attribution and missing publication/fixture knowledge.
Does not promote quoted opinions into official facts or fit start probabilities.
"""
import argparse,hashlib,json
from pathlib import Path
from free_match_intel import Tree,clock
from snapshot_predicted_lineups import canonical
SCOUT='https://www.fantasyfootballscout.co.uk/team-news'


def parse_team_news(text,bootstrap,observed_at):
    clock(observed_at)
    teams={t['short_name'].lower():t for t in bootstrap['teams']}
    if len(teams)!=len(bootstrap['teams']):raise ValueError('Ambiguous official club code')
    rows=[];seen=set();rejected=[]
    for node in Tree(text).root.find('team-news-item'):
        code=node.attrs.get('data-team-code','').lower();team=teams.get(code)
        if team is None:rejected.append({'code':code,'reason':'unknown_club'});continue
        if team['id']in seen:raise ValueError('Duplicate club context')
        seen.add(team['id'])
        paragraphs=[x.text()for x in node.walk()if x.tag=='p'and x.text().startswith('Latest News:')]
        headings=[x.text()for x in node.walk()if x.tag=='h2']
        updates=[x.text()for x in node.walk()if x.tag=='em'and x.text().startswith('Last Updated')]
        if len(paragraphs)!=1 or len(headings)!=1:
            rejected.append({'code':code,'reason':'missing_or_ambiguous_narrative'});continue
        if canonical(headings[0])!=canonical(team['name']):raise ValueError('Conflicting club heading and code')
        body=paragraphs[0].removeprefix('Latest News:').strip()
        if len(body)<40:rejected.append({'code':code,'reason':'insufficient_context'});continue
        rows.append(dict(team_id=team['id'],team_name=team['name'],source_team_name=headings[0],source_url=SCOUT,source_kind='editorial_team_news',publisher_group='fantasy_football_scout',observed_at=observed_at,source_updated_label=updates[0]if len(updates)==1 else None,source_published_at=None,publication_precision='unverified',next_gw_freshness='not_verified',fixture_id=None,player_identities_verified=False,official_confirmation=False,model_input_enabled=False,full_text=body,text_sha256=hashlib.sha256(body.encode()).hexdigest(),short_excerpt=' '.join(body.split()[:6])))
    ids={r['team_id']for r in rows}
    return dict(schema='pl-club-editorial-context-trial-v1',source_url=SCOUT,observed_at=observed_at,clubs=rows,rejected=rejected,coverage={'expected_clubs':len(teams),'clubs_with_narrative':len(rows),'missing_club_ids':sorted(t['id']for t in teams.values()if t['id']not in ids)},active_model_changed=False,production_changed=False)


def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--bootstrap',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--include-text',action='store_true');a=p.parse_args()
    receipts=json.loads((a.archive/'receipts.json').read_text());receipt=next(r for r in receipts if r['key']=='scout');raw=(a.archive/'scout.raw').read_bytes()
    if receipt['url']!=SCOUT or receipt['status']!=200 or hashlib.sha256(raw).hexdigest()!=receipt['sha256']:raise ValueError('Unverified source capture')
    report=parse_team_news(raw.decode(),json.loads(a.bootstrap.read_text()),receipt['observed_at']);report['source_receipt']=receipt
    report['bootstrap_sha256']=hashlib.sha256(a.bootstrap.read_bytes()).hexdigest()
    if not a.include_text:
        for r in report['clubs']:r.pop('full_text')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(report['coverage']))
if __name__=='__main__':main()
