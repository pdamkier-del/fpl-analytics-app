import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('audit', Path(__file__).resolve().parents[1]/'scripts/audit_fpl_team_news.py')
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)

class ResearchContract(unittest.TestCase):
    def test_states_are_not_minutes(self):
        self.assertEqual(a.normalized('a', 0), 'AVAILABLE')
        self.assertEqual(a.normalized('a', previous='i'), 'RETURNED_AVAILABLE')
        self.assertEqual(a.normalized('d', None), 'DOUBT')
        self.assertEqual(a.normalized('d', 25), 'MAJOR_DOUBT')
        self.assertEqual(a.normalized('s'), 'SUSPENDED')
        self.assertEqual(a.normalized('n'), 'UNKNOWN')
    def test_clock_is_not_certified(self):
        n=a.timestamp('2025-08-15T12:52:00Z'); c=a.timestamp('2025-08-15T12:52:48Z')
        t,v,r=a.certified_time(n,c,'parent',[])
        self.assertFalse(v); self.assertEqual(t,c)
    def test_server_finish_conservative(self):
        n=a.timestamp('2026-01-17T06:39:00Z'); c=a.timestamp('2026-01-17T06:39:55Z')
        run=dict(name='cache',head_sha='parent',status='completed',conclusion='success',created_at='2026-01-17T06:39:00Z',updated_at='2026-01-17T06:40:00Z')
        t,v,r=a.certified_time(n,c,'parent',[run])
        self.assertTrue(v); self.assertEqual(t,a.timestamp(run['updated_at']))
    def test_postdeadline_exclusion_and_carry(self):
        base=dict(source_id='one',fpl_element=1,gw=1,cutoff='2025-08-15T17:30:00Z',effective_at='2025-08-15T12:00:00Z',archive_clock_effective_at='2025-08-15T12:00:00Z',deadline_matches=True,future_news_timestamp=False,timing_verified=True,raw_status='i',raw_news='injury',news_added='2025-08-15T11:00:00Z',payload_current_event=None,payload_next_event=1,chance_this_round=None,chance_next_round=0,identity_status='mapped')
        late=dict(base,source_id='late',effective_at='2025-08-15T18:00:00Z',raw_status='a')
        ds=[dict(gw=1,cutoff=base['cutoff']),dict(gw=2,cutoff='2025-08-22T17:30:00Z')]
        rows,c=a.project([base,late],ds,True)
        self.assertEqual(rows[0]['raw_status'],'i')
        self.assertEqual(rows[1]['raw_status'],'a')
        self.assertIsNone(rows[1]['scoped_chance'])
        self.assertTrue(rows[1]['carried_from_earlier_gw'])
        self.assertEqual(c[0]['post_deadline_excluded_rows'],1)

if __name__=='__main__': unittest.main()
