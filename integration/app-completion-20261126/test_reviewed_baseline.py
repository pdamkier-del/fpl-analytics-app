"""Publication contract regressions, using synthetic public-file metadata only."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import reviewed_baseline as baseline


class ReviewedBaselineTests(unittest.TestCase):
    def setUp(self):
        self.review = dict(
            repository='owner/repo',
            deployment=dict(id=10, sha='a' * 40, run_id=20, job_id=30, workflow='.github/workflows/news.yml'),
            artifact=dict(id=40, name='pages-20', digest='sha256:abc', size_in_bytes=50),
            files={'index.html': hashlib.sha256(b'original').hexdigest()},
        )
        self.responses = {
            'repos/owner/repo/deployments?environment=github-pages&per_page=100': [dict(id=10, sha='a' * 40)],
            'repos/owner/repo/deployments/10/statuses': [dict(state='success', log_url='https://github.com/owner/repo/actions/runs/20/job/30')],
            'repos/owner/repo/actions/runs/20': dict(head_sha='a' * 40, conclusion='success', path='.github/workflows/news.yml'),
            'repos/owner/repo/actions/runs/20/artifacts': dict(artifacts=[dict(**self.review['artifact'], expired=False)]),
        }

    def resolve(self):
        return baseline.resolve(self.review, self.responses.__getitem__)

    def test_exact_deployment_artifact_provenance(self):
        self.assertEqual(self.resolve(), dict(run=20, artifact='pages-20', deployment=10))

    def test_new_deployment_with_same_commit_is_rejected(self):
        self.responses['repos/owner/repo/deployments?environment=github-pages&per_page=100'].insert(0, dict(id=11, sha='a' * 40))
        self.responses['repos/owner/repo/deployments/11/statuses'] = self.responses['repos/owner/repo/deployments/10/statuses']
        with self.assertRaisesRegex(ValueError, 'Live production advanced'):
            self.resolve()

    def test_same_deployment_wrong_commit_is_rejected(self):
        self.responses['repos/owner/repo/deployments?environment=github-pages&per_page=100'][0]['sha'] = 'b' * 40
        with self.assertRaisesRegex(ValueError, 'Live production advanced'):
            self.resolve()

    def test_failed_deployment_does_not_replace_successful(self):
        self.responses['repos/owner/repo/deployments?environment=github-pages&per_page=100'].insert(0, dict(id=11, sha='a' * 40))
        self.responses['repos/owner/repo/deployments/11/statuses'] = [dict(state='failure')]
        self.assertEqual(self.resolve()['deployment'], 10)

    def test_artifact_alteration_expiry_and_missing_are_rejected(self):
        artifact = self.responses['repos/owner/repo/actions/runs/20/artifacts']['artifacts'][0]
        for key, value in [('digest', 'sha256:different'), ('name', 'another-site'), ('size_in_bytes', 51), ('expired', True)]:
            with self.subTest(key=key):
                original = artifact[key]
                artifact[key] = value
                with self.assertRaises(ValueError):
                    self.resolve()
                artifact[key] = original
        self.responses['repos/owner/repo/actions/runs/20/artifacts']['artifacts'] = []
        with self.assertRaises(ValueError):
            self.resolve()

    def test_workflow_provenance_rejected(self):
        self.responses['repos/owner/repo/actions/runs/20']['path'] = 'different.yml'
        with self.assertRaisesRegex(ValueError, 'workflow identity'):
            self.resolve()

    def test_site_integrity_and_only_append_preview(self):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            original = site / 'index.html'
            original.write_bytes(b'original')
            self.assertEqual(baseline.verify_site(site, self.review)['original_files_unchanged'], 1)
            preview = site / baseline.PREFIX / 'app/index.html'
            preview.parent.mkdir(parents=True)
            preview.write_text('preview')
            baseline.verify_site(site, self.review, allow_preview=True)
            with self.assertRaises(ValueError):
                baseline.verify_site(site, self.review)
            original.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                baseline.verify_site(site, self.review, allow_preview=True)
            original.unlink()
            with self.assertRaises(ValueError):
                baseline.verify_site(site, self.review, allow_preview=True)

    def test_unrelated_new_files_symlinks_and_unsafe_paths_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            (site / 'index.html').write_bytes(b'original')
            extra = site / 'unexpected.json'
            extra.write_text('{}')
            with self.assertRaises(ValueError):
                baseline.verify_site(site, self.review, allow_preview=True)
            extra.unlink()
            extra.symlink_to(site / 'index.html')
            with self.assertRaises(ValueError):
                baseline.verify_site(site, self.review, allow_preview=True)
            review = copy.deepcopy(self.review)
            review['files']['../escape'] = 'invalid'
            with self.assertRaisesRegex(ValueError, 'file path'):
                baseline.verify_site(site, review)

    def test_hidden_publication_marker_must_survive_artifact_transfer(self):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            (site / 'index.html').write_bytes(b'original')
            marker = site / '.nojekyll'
            marker.write_bytes(b'')
            review = copy.deepcopy(self.review)
            review['files']['.nojekyll'] = hashlib.sha256(b'').hexdigest()
            baseline.verify_site(site, review)
            marker.unlink()
            with self.assertRaisesRegex(ValueError, 'changed/missing'):
                baseline.verify_site(site, review, allow_preview=True)


if __name__ == '__main__':
    unittest.main()
