"""Fixture-cluster uncertainty for fixed, already-scored penalty experiments."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd


def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();f=pd.read_csv(a.out/'predictions.csv.gz');v=f.pivot(index=['season','fixture_uuid','player_uuid','minutes','total_points'],columns='arm',values='xp').reset_index();v['mae_delta']=abs(v.candidate-v.total_points)-abs(v.baseline-v.total_points);v['bias_delta']=v.candidate-v.baseline
 rows=[];rng=np.random.default_rng(20261023)
 for season,g in v.groupby('season'):
  by=g.groupby('fixture_uuid').agg(mae_delta=('mae_delta','sum'),bias_delta=('bias_delta','sum'),n=('player_uuid','size'))
  ix=rng.integers(len(by),size=(2000,len(by)));count=by.n.to_numpy()[ix].sum(axis=1)
  rows.append(dict(season=season,rows=len(g),fixture_clusters=len(by),mae_delta=float(g.mae_delta.mean()),mae_delta_cluster_95=np.quantile(by.mae_delta.to_numpy()[ix].sum(axis=1)/count,[.025,.975]).tolist(),bias_delta=float(g.bias_delta.mean()),bias_delta_cluster_95=np.quantile(by.bias_delta.to_numpy()[ix].sum(axis=1)/count,[.025,.975]).tolist()))
 (a.out/'uncertainty.json').write_text(json.dumps(dict(method='2000 paired fixture-cluster bootstrap replicates; reused research periods, not independent certification',seasons=rows),indent=2)+'\n')
if __name__=='__main__':main()
