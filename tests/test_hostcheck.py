import contextlib
import io
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import hostcheck as h

class HostcheckTests(unittest.TestCase):
    def test_memory_available_not_free(self):
        self.assertEqual(h.memory_percent('MemTotal: 1000 kB\nMemFree: 20 kB\nMemAvailable: 300 kB'), 70)
    def test_missing_memory(self):
        with self.assertRaises(KeyError): h.memory_percent('MemTotal: 100 kB')
    def test_bad_memory(self):
        for text in ['MemTotal: 0\nMemAvailable: 0', 'MemTotal: 100\nMemAvailable: 200']:
            with self.assertRaises(ValueError): h.memory_percent(text)
    def test_reserved_blocks(self):
        s = SimpleNamespace(f_blocks=100, f_bfree=30, f_bavail=20, f_files=100, f_ffree=40)
        disk, inode = h.filesystem_percent(s)
        self.assertAlmostEqual(disk, 100*70/90)
        self.assertEqual(inode, 60)
    def test_no_inode_support(self):
        self.assertIsNone(h.filesystem_percent(SimpleNamespace(f_blocks=100,f_bfree=30,f_bavail=20,f_files=0,f_ffree=0))[1])
    def test_zero_filesystem(self):
        with self.assertRaises(ValueError): h.filesystem_percent(SimpleNamespace(f_blocks=0,f_bfree=0,f_bavail=0))
    def test_threshold_edges(self):
        self.assertEqual([h.percent_status(v,80,90) for v in [79.9,80,89.9,90]], ['ok','warning','warning','critical'])
    def test_raw_threshold_before_rounding(self):
        self.assertEqual(h.metric('x',79.999,80,90)['status'],'ok')
    def test_reject_nan(self):
        with self.assertRaises(ValueError): h.metric('x',float('nan'),80,90)
    def test_exit_precedence(self):
        for states, expected in [(['ok'],0),(['warning'],1),(['unknown','warning'],3),(['unknown','critical'],2)]:
            self.assertEqual(h.exit_code([{'status':s} for s in states]),expected)
    def test_unavailable_sources(self):
        with patch('hostcheck.Path.read_text',side_effect=PermissionError), patch('hostcheck.os.statvfs',side_effect=OSError):
            self.assertTrue(all(c['status']=='unknown' for c in h.collect('/',80,90)))
    def test_cli_json(self):
        out = io.StringIO()
        with patch('hostcheck.sys.platform','linux'), patch('hostcheck.collect',return_value=[h.metric('memory_used',20,80,90)]),contextlib.redirect_stdout(out):
            self.assertEqual(h.main(['--json']),0)
        self.assertEqual(json.loads(out.getvalue())['schema_version'],1)
    def test_bad_thresholds(self):
        for args in [['--warning','90','--critical','80'],['--warning','nan'],['--critical','101']]:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit): h.main(args)
    def test_nonlinux(self):
        with patch('hostcheck.sys.platform','win32'),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(h.main([]),3)
    def test_missing_path(self):
        self.assertTrue(any(c['status']=='unknown' for c in h.collect('/nonexistent-hostcheck-test-path',80,90)))

if __name__ == '__main__': unittest.main()
