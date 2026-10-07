import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/'scripts/audit_2024_25_historical_layer.py'
spec=importlib.util.spec_from_file_location('season_data_audit',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class CutoffAuditTests(unittest.TestCase):
 def test_target_future_and_unmapped_never_in_history(self):
  rows=[{'player_uuid':'a','available_at_proxy':'2024-08-16T16:00:00Z'}, {'player_uuid':'a','available_at_proxy':'2024-08-16T17:30:00Z'}, {'player_uuid':'a','available_at_proxy':'2024-08-17T00:00:00Z'}, {'player_uuid':None,'available_at_proxy':'2024-08-01T00:00:00Z'}]
  self.assertEqual(m.asof(rows,'2024-08-16T17:30:00Z'),rows[:1])
 def test_ambiguity_not_resolved_arbitrarily(self):
  self.assertIsNone(m.unique({'a','b'}));self.assertIsNone(m.unique(set()));self.assertEqual(m.unique({'a'}),'a')
 def test_nonfinite_json_and_layout_not_average_position(self):
  self.assertEqual(m.clean({'x':float('nan'),'a':[float('inf'),2]}),{'x':None,'a':[None,2]})
 def test_exact_normalization_only(self):
  self.assertEqual(m.norm('Pervis Estupiñán'),m.norm('Pervis Estupinan'))
  self.assertNotEqual(m.norm('Bruno Fernandes'),m.norm('Bruno Guimarães'))
  self.assertEqual(m.club('Manchester United'),m.club('Man Utd'))
if __name__=='__main__':unittest.main()
