"""Synthetic public-data publication contracts; no real manager information."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

import refresh_data as data
from preserve_pages import inspect_tar


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime(2026,11,27,12,tzinfo=timezone.utc)
        self.f=dict(model='B-MM-PM-TS-v1',chain_version='B-MM-PM-TS-v1',mm_version='B-MM-PM-TS-v1',model_revision='frozen',code_sha256={'source':'a'*64},parts={'pm':'frozen'},normal_match_timeline={'version':'frozen'},freshness_limit_hours=24,season='2026-27',locked_model_active=False,gws=[12,13,14,15,16,17],data_asof=(self.now-timedelta(hours=1)).isoformat(),origin_deadline=(self.now+timedelta(hours=6)).isoformat(),players=[dict(id=1,team_id=1,position=1,price_tenths=50)])
        self.f['forecast_sha256']=hashlib.sha256(data.canonical(self.f)).hexdigest()
        self.old=deepcopy(self.f);self.old['data_asof']=(self.now-timedelta(days=1)).isoformat()
        self.news=dict(schema='fpl-dashboard-availability-v1',source_url='https://fantasy.premierleague.com/api/bootstrap-static/',next_gw=12,deadline=self.f['origin_deadline'],observed_at=(self.now-timedelta(minutes=5)).isoformat(),players=[dict(id=1,team=1,position=1,price_tenths=50)])
        self.seal_news()
        self.bootstrap=dict(events=[dict(id=12,is_next=True,deadline_time=self.f['origin_deadline'])],elements=[dict(id=1,team=1,element_type=1,now_cost=50)])

    def seal_news(self):
        self.news.pop('content_sha256',None);self.news['content_sha256']=hashlib.sha256(data.canonical(self.news)).hexdigest()

    def test_current_window(self):
        data.check_window(self.f,self.news,self.bootstrap,self.now)

    def test_ten_price_changes_cannot_be_ignored(self):
        self.bootstrap['elements'][0]['now_cost']=51
        with self.assertRaisesRegex(ValueError,'prices'):
            data.check_window(self.f,self.news,self.bootstrap,self.now)

    def test_wrong_status_catalogue_stale_and_checksum_rejected(self):
        self.news['players'][0]['price_tenths']=51;self.seal_news()
        with self.assertRaises(ValueError):data.check_window(self.f,self.news,self.bootstrap,self.now)
        self.setUp();self.news['observed_at']=(self.now-timedelta(hours=2)).isoformat();self.seal_news()
        with self.assertRaises(ValueError):data.check_window(self.f,self.news,self.bootstrap,self.now)
        self.setUp();self.news['content_sha256']='b'*64
        with self.assertRaises(ValueError):data.check_window(self.f,self.news,self.bootstrap,self.now)

    def test_deadline_and_future_capture_rejected(self):
        with self.assertRaises(ValueError):data.check_window(self.f,self.news,self.bootstrap,self.now+timedelta(days=1))
        with self.assertRaises(ValueError):data.check_window(self.f,self.news,self.bootstrap,self.now-timedelta(hours=2))
        self.bootstrap['events'][0]['id']=13
        with self.assertRaises(ValueError):data.check_window(self.f,self.news,self.bootstrap,self.now)

    def capture(self,root):
        for folder in ['current','gk','news']:(root/folder).mkdir()
        def put(name,obj):
            path=root/name;path.write_bytes(data.canonical(obj));return data.digest(path)
        fi=put('current/forecast.json',self.f);put('gk/forecast.json',self.f)
        index=dict(forecast_sha256=self.f['forecast_sha256'],forecast_file_sha256=fi,desktop_probabilities=dict(forecast_sha256=self.f['forecast_sha256']))
        pairs={'mm.json':'mm_file_sha256','catalogue.json':'catalogue_sha256','chain-validation.json':'chain_validation_sha256','pm-audit.json':'pm_audit_sha256','role-ledger.csv.gz':'role_ledger_sha256'}
        for name,key in pairs.items():index[key]=put('current/'+name,{})
        index['existing_app_data_sha256']=put('current/existing-app-data.json',dict(forecast_sha256=self.f['forecast_sha256']))
        put('current/index.json',index)
        gi=dict(forecast_sha256=fi,mm_sha256=put('gk/gk-mm.json',{}),evidence_sha256=put('gk/evidence.json',{}));put('gk/index.json',gi);put('news/availability.json',self.news)

    def test_complete_original_capture_and_unchanged_model(self):
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);self.capture(root)
            self.assertEqual(data.validate_capture(root,self.old,self.now,self.bootstrap)['forecast_sha256'],self.f['forecast_sha256'])
            altered=deepcopy(self.old);altered['code_sha256']['source']='b'*64
            with self.assertRaisesRegex(ValueError,'Frozen model'):data.validate_capture(root,altered,self.now,self.bootstrap)
            (root/'gk/forecast.json').write_text('{}')
            with self.assertRaises(ValueError):data.validate_capture(root,self.old,self.now,self.bootstrap)

    def test_candidate_scope_preserves_all_ui_and_history(self):
        review=dict(files={'mm-preview/current/forecast.json':'a','previews/team-transfers-20261126/app/shared-team.js':'b','overview.html':'c','mm-preview/current/history/old.mm.json.gz':'d'})
        new=deepcopy(review);new['files']['mm-preview/current/forecast.json']='updated'
        self.assertEqual(data.candidate_changes(review,new),['mm-preview/current/forecast.json'])
        for name in ['overview.html','previews/team-transfers-20261126/app/shared-team.js','mm-preview/current/history/old.mm.json.gz','mm-preview/current/private-manager.json']:
            with self.subTest(name=name):
                wrong=deepcopy(new);wrong['files'][name]='changed'
                with self.assertRaises(ValueError):data.candidate_changes(review,wrong)
        del new['files']['overview.html']
        with self.assertRaises(ValueError):data.candidate_changes(review,new)

    def test_unreviewed_new_paths_and_code_are_not_data(self):
        for name in ['../mm-preview/current/input.json','mm-preview/current/optimizer.js','app/current/forecast.json','/mm-preview/current/state.json']:
            self.assertFalse(data.data_path(name))

    def test_exact_producer_wrapper_and_success_required(self):
        run=dict(status='completed',conclusion='success',path='.github/workflows/mm-current-preview-publication.yml',head_sha=data.WRAPPER,head_branch='integration/stable-live-app-20261122')
        responses={f'repos/{data.REPO}/actions/runs/1':run,f'repos/{data.REPO}/actions/runs/1/jobs?per_page=100':dict(jobs=[dict(name='gk_cap_candidate / current',conclusion='success')]),f'repos/{data.REPO}/actions/runs/1/artifacts':dict(artifacts=[dict(id=2,name='mm-current-live-preview',expired=False,digest='sha256:fake')])}
        self.assertEqual(data.source_run(1,responses.__getitem__)['numerical_source'],data.SOURCE)
        run['conclusion']='failure'
        with self.assertRaises(ValueError):data.source_run(1,responses.__getitem__)
        run['conclusion']='success';run['head_sha']='unreviewed'
        with self.assertRaises(ValueError):data.source_run(1,responses.__getitem__)

    def test_tar_recovery_inventory_rejects_links(self):
        with tempfile.TemporaryDirectory()as folder:
            root=Path(folder);(root/'index.html').write_text('public')
            with tarfile.open(root/'site.tar','w')as tar:tar.add(root/'index.html',arcname='index.html')
            self.assertEqual(inspect_tar(root/'site.tar'),{'index.html':data.digest(root/'index.html')})
            with tarfile.open(root/'bad.tar','w')as tar:
                member=tarfile.TarInfo('link');member.type=tarfile.SYMTYPE;member.linkname='/etc/passwd';tar.addfile(member)
            with self.assertRaises(ValueError):inspect_tar(root/'bad.tar')


if __name__=='__main__':unittest.main()
