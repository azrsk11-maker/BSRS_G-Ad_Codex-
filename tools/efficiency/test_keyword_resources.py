"""Resource selection changes concurrency only, never coverage or deadlines."""
import unittest
from unittest.mock import patch
from pathlib import Path
import keyword_resources as r
import keyword_modules as runner


class KeywordResourceTests(unittest.TestCase):
    def test_auto_uses_cpu_and_available_memory_and_never_exceeds_four(self):
        for cpus,gib,wanted in ((12,1,1),(12,4,2),(4,8,4),(2,16,2),(3,16,3),(32,64,4)):
            with self.subTest(cpus=cpus,gib=gib):
                value=r.select('auto',{'cpu_count':cpus,'memory_available_bytes':gib*1024**3})
                self.assertEqual(value['selected_workers'],wanted)
                self.assertTrue(r.valid_selection(value,wanted))

    def test_unknown_memory_is_conservative_and_extra_workers_fail_closed(self):
        unknown={'cpu_count':12,'memory_available_bytes':None}
        self.assertEqual(r.select('auto',unknown)['selected_workers'],1)
        for mode in ('3','4'):
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                r.select(mode,unknown)
        self.assertEqual(r.select('2',unknown)['selected_workers'],2)

    def test_unbound_modes_boolean_counts_tampered_metadata_and_extra_fields_fail(self):
        seen={'cpu_count':4,'memory_available_bytes':8*1024**3}
        value=r.select('auto',seen)
        for changed in ({**value,'selected_workers':5},{**value,'maximum_workers':1000},
                        {**value,'memory_per_worker_bytes':1},{**value,'extra':'invalid'},
                        {**value,'memory_available_bytes':-1},{**value,'cpu_count':True}):
            self.assertFalse(r.valid_selection(changed,changed['selected_workers']))
        self.assertFalse(r.valid_selection(value,True))
        for mode in ('0','5','unbounded',4):
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                r.select(mode,seen)

    def test_effective_cpu_count_respects_affinity_and_kernel_quota(self):
        with patch.object(r.os,'cpu_count',return_value=12), \
                patch.object(r.os,'sched_getaffinity',return_value={0,1,2,3},create=True), \
                patch.object(Path,'is_file',return_value=True), \
                patch.object(Path,'read_text',return_value='200000 100000'), \
                patch.object(r,'available_memory',return_value=16*1024**3):
            seen=r.observe()
        self.assertEqual(seen['cpu_count'],2)
        self.assertEqual(r.select('auto',seen)['selected_workers'],2)

    def test_unknown_or_invalid_kernel_quota_never_expands_capacity(self):
        with patch.object(r.os,'cpu_count',return_value=12), \
                patch.object(r.os,'sched_getaffinity',return_value={0,1,2,3},create=True), \
                patch.object(Path,'is_file',return_value=True), \
                patch.object(Path,'read_text',side_effect=OSError('synthetic unavailable quota')), \
                patch.object(r,'available_memory',return_value=16*1024**3):
            seen=r.observe()
        self.assertEqual(seen['cpu_count'],1)

    def test_scheduling_hint_keeps_every_discovered_module(self):
        # Ordering is independent of selection; dynamic discovery remains intact.
        names=['test_unknown_new_module',*runner.SLOW_MODULES,'test_alpha']
        ordered=sorted(names,key=lambda n:(runner.SLOW_MODULES.index(n) if n in runner.SLOW_MODULES else len(runner.SLOW_MODULES),n))
        self.assertEqual(sorted(ordered),sorted(names))
        self.assertEqual(ordered[0],'test_bank_channel_login_admission')
        self.assertLess(ordered.index('test_ofqual_veterinary_admission'),ordered.index('test_unknown_new_module'))
        self.assertIn('test_unknown_new_module',ordered)
        self.assertEqual(runner.TIMEOUT,300)
