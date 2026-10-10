"""Lossless provider-schema evidence; no inferred tackle alias or model math."""
import hashlib,json
from pathlib import Path


def passing_percentage(stat):
    if stat.get('type') != 'fractionWithPercentage':
        return None
    a, n = stat.get('value'), stat.get('total')
    if a is None or n is None:
        return None
    a, n = float(a), float(n)
    if not 0 <= a <= n:
        raise ValueError('Invalid accurate passes fraction')
    # 0/0 is unobserved, not a measured zero percent.
    return 100.0*a/n if n > 0 else None


def manifest_details(repo, manifest):
    """Select only checksummed captures belonging to this immutable cutoff."""
    repo=Path(repo);cutoff=manifest['observed_at'];found={}
    for source in manifest['sources']:
        if '/fotmob/details/' not in source['path']:continue
        if source['observed_at']>cutoff:raise ValueError('Post-cutoff provider capture')
        path=repo/source['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('Provider capture checksum mismatch')
        match=json.loads(path.read_text());mid=str(match['general']['matchId'])
        if mid in found:raise ValueError('Duplicate manifest provider identity '+mid)
        found[mid]=(match,path)
    if not found:raise ValueError('No manifest provider details')
    return found


def raw_evidence(root, paths=None):
    evidence = {}
    for path in (paths if paths is not None else sorted(Path(root).glob('*/fotmob/details/*.json'))):
        match = json.loads(path.read_text())
        mid = str(match['general']['matchId'])
        for pid, player in (match.get('content', {}).get('playerStats') or {}).items():
            for section in player.get('stats', []):
                for label, item in section.get('stats', {}).items():
                    if item.get('key') != 'accurate_passes':
                        continue
                    percentage = passing_percentage(item.get('stat', {}))
                    if percentage is None:
                        continue
                    key = (mid, str(pid))
                    prior = evidence.get(key)
                    if prior is not None and prior['value'] != percentage:
                        raise ValueError('Conflicting archived passing statistics '+str(key))
                    evidence[key] = {'value': percentage, 'source_path': str(path),
                                     'source_key': 'accurate_passes',
                                     'numerator': item['stat']['value'],
                                     'denominator': item['stat']['total']}
    return evidence
