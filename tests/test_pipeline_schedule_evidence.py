from scripts.publish_pipeline_status import retain_schedule_evidence

def receipt(trigger='schedule', status='success'):
    return dict(trigger=trigger,status=status,observed_at='2026-10-11T14:30:00Z',workflow='https://github.com/example/run/1',schedule='17 0-23 * * *')

def test_only_first_successful_scheduled_attempt_is_automatic_evidence():
    for trigger,status,attempt in [('push','success','1'),('schedule','failure','1'),('schedule','success','2')]:
        assert 'last_scheduled_success' not in retain_schedule_evidence(receipt(trigger,status),{},attempt)
    assert retain_schedule_evidence(receipt(),{},'1')['last_scheduled_success']['schedule']=='17 0-23 * * *'

def test_later_push_or_failure_preserves_real_automatic_evidence():
    earlier=retain_schedule_evidence(receipt(),{},'1')
    for trigger,status in [('push','success'),('schedule','failure')]:
        assert retain_schedule_evidence(receipt(trigger,status),earlier,'1')['last_scheduled_success']==earlier['last_scheduled_success']
