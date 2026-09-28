"""Root-only integration tests in a disposable Linux mount namespace, NOT on Android.

Run: sudo python3 test_mount_linux.py
No phone access, SELinux disabled only in the test engine's label helper (not the host).
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ENGINE = Path(__file__).resolve().parent / 'assets/ksu/boot/mount-engine.sh'


@unittest.skipUnless(os.environ.get('DOLBY_MOUNT_TEST_WORKER') == '1', 'requires isolated mount test runner')
class MountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='dolby-mount-test-')
        self.root = Path(self.tmp.name)
        self.original = self.root / 'stock'
        self.payload = self.root / 'payload'
        self.work = self.root / 'scratch'
        for directory in (self.original, self.payload, self.work):
            directory.mkdir()
        self.run_cmd('mount', '-t', 'tmpfs', '-o', 'mode=0700', 'KSU', str(self.work))
        self.run_cmd('mount', '--make-rprivate', str(self.work))
        self.children = []
        self.script(' : > "$W/published"')

    def tearDown(self):
        # Each publication is a test-owned tree; never delete through a live bind.
        self.script('rollback_publications', check=False)
        for child in reversed(self.children):
            self.run_cmd('umount', '-l', str(child), check=False)
        self.run_cmd('umount', '-l', str(self.work), check=False)
        self.tmp.cleanup()

    def run_cmd(self, *args, check=True):
        return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=check)

    def script(self, body, check=True):
        env = dict(os.environ, ENGINE=str(ENGINE), W=str(self.work),
                   ORIGINAL=str(self.original), PAYLOAD=str(self.payload), DOLBY_SELINUX='0')
        return subprocess.run(['sh', '-c', '. "$ENGINE"\n' + body], env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=check)

    def publish(self):
        self.script('set -e\nmerge_tree "$ORIGINAL" "$PAYLOAD" "$W/tree" "$ORIGINAL"\n'
                    'cp /proc/self/mountinfo "$W/before"\n'
                    'mount --rbind "$W/tree" "$ORIGINAL"\n'
                    'record_publication "$ORIGINAL"\n'
                    'mount -o remount,bind,ro "$ORIGINAL"')

    def test_merge_preserves_nested_mounts_and_symlinks(self):
        (self.original / 'stock.so').write_text('stock')
        (self.original / 'link.so').symlink_to('stock.so')
        nested = self.original / 'opex'
        nested.mkdir()
        self.run_cmd('mount', '-t', 'tmpfs', 'opex-test', str(nested))
        self.children.append(nested)
        (nested / 'wallpaper.so').write_text('important original mount')
        (self.payload / 'dolby.so').write_text('dolby')
        self.publish()
        self.assertEqual((self.original / 'dolby.so').read_text(), 'dolby')
        self.assertEqual((self.original / 'link.so').read_text(), 'stock')
        self.assertTrue((self.original / 'link.so').is_symlink())
        self.assertEqual((nested / 'wallpaper.so').read_text(), 'important original mount')
        self.script('rollback_publications')
        self.assertFalse((self.original / 'dolby.so').exists())
        self.assertEqual((nested / 'wallpaper.so').read_text(), 'important original mount')

    def test_payload_inside_existing_child_mount(self):
        nested = self.original / 'soundfx'
        nested.mkdir()
        self.run_cmd('mount', '-t', 'tmpfs', 'original-soundfx', str(nested))
        self.children.append(nested)
        (nested / 'stock.so').write_text('stock-effect')
        (self.payload / 'soundfx').mkdir()
        (self.payload / 'soundfx' / 'dolby.so').write_text('effect')
        self.publish()
        self.assertEqual((nested / 'stock.so').read_text(), 'stock-effect')
        self.assertEqual((nested / 'dolby.so').read_text(), 'effect')
        self.script('rollback_publications')
        self.assertFalse((nested / 'dolby.so').exists())
        self.assertEqual((nested / 'stock.so').read_text(), 'stock-effect')

    def test_replacement_is_read_only_and_reversible(self):
        (self.original / 'same.so').write_text('old')
        (self.payload / 'same.so').write_text('new')
        self.publish()
        self.assertEqual((self.original / 'same.so').read_text(), 'new')
        with self.assertRaises(OSError):
            (self.original / 'same.so').write_text('bad')
        self.script('rollback_publications')
        self.assertEqual((self.original / 'same.so').read_text(), 'old')

    def test_android_bracket_command_and_punctuation_are_preserved(self):
        (self.original / 'toybox_vendor').write_text('toybox')
        (self.original / '[').symlink_to('toybox_vendor')
        (self.original / 'a[1](x):test').write_text('punctuation')
        (self.payload / 'dolby.so').write_text('dolby')
        self.publish()
        self.assertEqual(os.readlink(self.original / '['), 'toybox_vendor')
        self.assertEqual((self.original / '[').read_text(), 'toybox')
        self.assertEqual((self.original / 'a[1](x):test').read_text(), 'punctuation')
        self.script('rollback_publications')
        self.assertFalse((self.original / 'dolby.so').exists())

    def test_unencodable_paths_are_rejected_not_executed(self):
        self.assertNotEqual(self.script('safe_path "/vendor/a b"',check=False).returncode,0)
        self.assertNotEqual(self.script('safe_path "/vendor/../data"',check=False).returncode,0)
        self.assertEqual(self.script('safe_path "/vendor/bin/["').returncode,0)

    def test_abort_symlink_collision_before_publication(self):
        (self.original / 'same.so').symlink_to('/dev/null')
        (self.payload / 'same.so').write_text('replacement')
        result = self.script('merge_tree "$ORIGINAL" "$PAYLOAD" "$W/tree" "$ORIGINAL"', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(os.readlink(self.original / 'same.so'), '/dev/null')

    def test_bind_failure_falls_back_to_copy_without_touching_stock(self):
        (self.original / 'same.so').write_text('stock')
        (self.payload / 'same.so').write_text('replacement')
        result=self.script('mount() { return 1; }\n'
                           'merge_tree "$ORIGINAL" "$PAYLOAD" "$W/tree" "$ORIGINAL"')
        self.assertIn('复制兜底',result.stdout)
        self.assertEqual((self.work/'tree/same.so').read_text(),'replacement')
        self.assertEqual((self.original/'same.so').read_text(),'stock')
        self.script('cp /proc/self/mountinfo "$W/before"\n'
                    'mount --rbind "$W/tree" "$ORIGINAL"\nrecord_publication "$ORIGINAL"\n'
                    'mount -o remount,bind,ro "$W/tree" "$ORIGINAL"')
        with self.assertRaises(OSError):
            (self.original/'same.so').write_text('bad')

    def test_readonly_failure_unbinds_before_copy(self):
        (self.payload/'same.so').write_text('source')
        result=self.script('mount() { case "$*" in *remount*) return 1;; esac; command mount "$@"; }\n'
                           'merge_tree "$ORIGINAL" "$PAYLOAD" "$W/tree" "$ORIGINAL"\n'
                           '[ -z "$(mount_id "$W/tree/same.so")" ]')
        self.assertIn('复制兜底',result.stdout)
        (self.work/'tree/same.so').write_text('independent copy')
        self.assertEqual((self.payload/'same.so').read_text(),'source')

    def test_fallback_aborts_when_unbind_fails_or_budget_exceeded(self):
        (self.payload/'same.so').write_text('source')
        result=self.script('mount() { case "$*" in *remount*) return 1;; esac; command mount "$@"; }\n'
                           'umount() { return 1; }\n'
                           'merge_tree "$ORIGINAL" "$PAYLOAD" "$W/tree" "$ORIGINAL"',check=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((self.payload/'same.so').read_text(),'source')
        result=self.script('mount() { return 1; }\ncopied_bytes=134217728\n'
                           'merge_tree "$ORIGINAL" "$PAYLOAD" "$W/other" "$ORIGINAL"',check=False)
        self.assertNotEqual(result.returncode,0)

    def test_rollback_does_not_unmount_replaced_foreign_file(self):
        (self.payload / 'same.so').write_text('dolby')
        self.publish()
        other = self.root / 'other.so'
        other.write_text('another module')
        self.run_cmd('mount', '-o', 'bind', str(other), str(self.original / 'same.so'))
        result = self.script('rollback_publications')
        self.assertIn('挂载归属已变化', result.stdout)
        self.assertEqual((self.original / 'same.so').read_text(), 'another module')
        self.run_cmd('umount', str(self.original / 'same.so'))


if __name__ == '__main__':
    if '--worker' not in sys.argv:
        if os.geteuid() != 0:
            raise SystemExit('Requires root for an isolated mount namespace; do not run on a phone.')
        raise SystemExit(subprocess.call(['unshare', '--mount', '--propagation', 'private',
                                         sys.executable, str(Path(__file__).resolve()), '--worker']))
    sys.argv.remove('--worker')
    # The decorator above is evaluated before main; enable only this explicit worker.
    MountTests.__unittest_skip__ = False
    unittest.main(verbosity=2)
