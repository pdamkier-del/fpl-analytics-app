import pytest
from verify_b_publication_artifact import verify, REPO, MODEL_WORKFLOW, WRAPPER_WORKFLOW, REUSABLE

SOURCE = 'f492be4795bfd630ba91377d71497e68c1d85934'
ARTIFACTS = [dict(id=1, name='mm-current-live-preview', expired=False)]
BASE = dict(status='completed', conclusion='success', head_repository={'full_name': REPO})
WRAPPER = dict(BASE, path=WRAPPER_WORKFLOW, head_branch='main', event='workflow_dispatch')
WORKFLOW = f'  PREVIEW_SOURCE_SHA: {SOURCE}\n    uses: {REUSABLE}\n      source_ref: {SOURCE}\n'
JOBS = [dict(name='current / current', status='completed', conclusion='success')]


def test_accepts_standalone_exact_source_and_successful_pinned_main_wrapper():
    assert verify(dict(BASE, path=MODEL_WORKFLOW, head_sha=SOURCE), ARTIFACTS, SOURCE) == 1
    assert verify(WRAPPER, ARTIFACTS, SOURCE, workflow=WORKFLOW, jobs=JOBS) == 1


@pytest.mark.parametrize('change', [dict(conclusion='action_required'), dict(status='in_progress'),
    dict(head_branch='other'), dict(event='pull_request'), dict(path='other.yml'),
    dict(head_repository={'full_name': 'another/repository'})])
def test_rejects_unverified_origin(change):
    with pytest.raises(ValueError):
        verify(dict(WRAPPER, **change), ARTIFACTS, SOURCE, workflow=WORKFLOW, jobs=JOBS)


@pytest.mark.parametrize('workflow,jobs', [
    (WORKFLOW.replace(SOURCE, 'a' * 40), JOBS),
    (WORKFLOW.replace('      source_ref: ' + SOURCE, '      source_ref: ' + 'b' * 40), JOBS),
    (WORKFLOW.replace(REUSABLE, REUSABLE.rsplit('@', 1)[0] + '@main'), JOBS),
    (WORKFLOW, [dict(name='current / current', conclusion='skipped')]),
])
def test_rejects_different_source_workflow_or_skipped_computation(workflow, jobs):
    with pytest.raises(ValueError):
        verify(WRAPPER, ARTIFACTS, SOURCE, workflow=workflow, jobs=jobs)


@pytest.mark.parametrize('artifacts', [[], ARTIFACTS * 2, [dict(ARTIFACTS[0], expired=True)]])
def test_rejects_missing_expired_or_ambiguous_artifact(artifacts):
    with pytest.raises(ValueError):
        verify(WRAPPER, artifacts, SOURCE, workflow=WORKFLOW, jobs=JOBS)


@pytest.mark.parametrize('conclusion', ['failure', 'cancelled'])
def test_later_ui_failure_does_not_discard_successful_numerical_work(conclusion):
    assert verify(dict(WRAPPER, conclusion=conclusion), ARTIFACTS, SOURCE,
                  workflow=WORKFLOW, jobs=JOBS) == 1
    with pytest.raises(ValueError):
        verify(dict(WRAPPER, conclusion=conclusion), ARTIFACTS, SOURCE,
               workflow=WORKFLOW, jobs=[dict(name='current / current', status='completed', conclusion='failure')])
