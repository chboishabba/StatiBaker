"""Deterministic acceptance tests for StatiBaker temporal leaf."""
from datetime import date, timedelta
import unittest
from sb.temporal_reduction import reduce_day

class TemporalReductionTests(unittest.TestCase):
    def test_full_lifecycle_and_independent_types(self):
        d=date(2026,10,25)
        first=reduce_day(None,as_of=d,atoms=["a","same"],threads=["t","same"])
        self.assertEqual(first.atom_new,("a","same"))
        self.assertEqual(first.thread_new,("same","t"))
        second=reduce_day(first.state,as_of=d+timedelta(days=1),atoms=["same","b"],threads=["same"])
        self.assertEqual(second.atom_new,("b",))
        self.assertEqual(second.atom_carryover,("same",))
        self.assertEqual(second.atom_resolved,("a",))
        self.assertEqual(second.thread_resolved,("t",))
        self.assertEqual(second.state.atoms["same"].age_days,1)
        self.assertEqual(second.state.resolved_atoms["a"].age_days,1)
        third=reduce_day(second.state,as_of=d+timedelta(days=2),atoms=["a","same","b"],threads=["t"])
        self.assertEqual(third.atom_new,("a",))
        self.assertEqual(third.state.atoms["a"].age_days,0)
        self.assertEqual(third.thread_new,("t",))
        self.assertEqual(third.thread_resolved,("same",))
        self.assertIn("a",third.state.resolved_atoms)

    def test_invalid_and_missing_inputs(self):
        d=date(2026,10,25)
        previous=reduce_day(None,as_of=d,atoms=["a"],threads=[])
        for options in (
            dict(atoms=["a","a"],threads=[]),
            dict(atoms=[""],threads=[]),
            dict(atoms="a",threads=[]),
            dict(atoms=[],threads=[],complete_snapshot=False),
        ):
            with self.assertRaises(ValueError):
                reduce_day(previous.state,as_of=d+timedelta(days=1),**options)
        for offset in (-1,0,2):
            with self.assertRaises(ValueError):
                reduce_day(previous.state,as_of=d+timedelta(days=offset),atoms=[],threads=[])

    def test_empty_day_replay_is_not_idempotently_mutated(self):
        d=date(2026,10,25)
        empty=reduce_day(None,as_of=d,atoms=[],threads=[])
        with self.assertRaises(ValueError):
            reduce_day(empty.state,as_of=d,atoms=[],threads=[])

    def test_order_and_determinism(self):
        d=date(2026,10,25)
        x=reduce_day(None,as_of=d,atoms=["b","a"],threads=["y","x"])
        y=reduce_day(None,as_of=d,atoms=["a","b"],threads=["x","y"])
        self.assertEqual(x,y)
        self.assertEqual(x.atom_new,("a","b"))

if __name__=="__main__":
    unittest.main()
