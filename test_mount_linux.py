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

    def plan(self):
        self.script('set -e\n: > "$W/targets"\nplan_tree "$ORIGINAL" "$PAYLOAD"')
        return [line.split('\t') for line in (self.work/'targets').read_text().splitlines()]

    def publish_minimal(self):
        plan=self.plan()
        for n,(kind,target,payload) in enumerate(plan):
            stage=self.work/('minimal-'+str(n))
            if kind=='F':
                self.script(f'stage_payload "{payload}" "{stage}"')
            else:
                self.script(f'merge_tree "{target}" "{payload}" "{stage}" "{target}"')
        for n,(kind,target,_) in enumerate(plan):
            stage=self.work/('minimal-'+str(n))
            operation='-o bind' if kind=='F' else '--rbind'
            self.script(f'set -e\ncp /proc/self/mountinfo "$W/before"\n'
                        f'mount {operation} "{stage}" "{target}"\nrecord_publication "{target}"\n'
                        f'mount -o remount,bind,ro "{stage}" "{target}"')
        return plan

    def test_minimal_new_hw_service_never_visits_horae(self):
        (self.original/'bin/hw').mkdir(parents=True)
        (self.original/'bin/horae').write_text('stock')
        (self.original/'bin/hw/stock-hal').write_text('hal')
        (self.payload/'bin/hw').mkdir(parents=True)
        (self.payload/'bin/hw/dolby').write_text('dolby')
        plan=self.plan()
        self.assertEqual([(k,t) for k,t,p in plan],[('D',str(self.original/'bin/hw'))])
        # Reproduce the reported unrelated-file failure if it is ever touched.
        self.script('mount() { case "$*" in *horae*) return 1;; esac; command mount "$@"; }\n'
                    'merge_tree "$ORIGINAL/bin/hw" "$PAYLOAD/bin/hw" "$W/probe" "$ORIGINAL/bin/hw"')
        self.publish_minimal()
        self.assertEqual((self.original/'bin/hw/dolby').read_text(),'dolby')
        self.assertEqual((self.original/'bin/horae').read_text(),'stock')
        targets=(self.work/'published').read_text()
        self.assertNotIn(str(self.original/'bin/horae'),targets)
        self.script('rollback_publications')
        self.assertFalse((self.original/'bin/hw/dolby').exists())

    def test_minimal_existing_files_are_independent_readonly_binds(self):
        (self.original/'etc').mkdir();(self.payload/'etc').mkdir()
        for name in ('one.xml','two.xml'):
            (self.original/'etc'/name).write_text('old')
            (self.payload/'etc'/name).write_text('new')
        plan=self.publish_minimal()
        self.assertEqual([kind for kind,_,_ in plan],['F','F'])
        for _,target,_ in plan:
            self.assertEqual(Path(target).read_text(),'new')
            with self.assertRaises(OSError):Path(target).write_text('bad')
        self.script('rollback_publications')
        self.assertEqual((self.original/'etc/one.xml').read_text(),'old')

    def test_minimal_new_directory_requires_nearest_existing_parent(self):
        (self.original/'lib64').mkdir()
        (self.payload/'lib64/dolbyaidl').mkdir(parents=True)
        (self.payload/'lib64/dolbyaidl/new.so').write_text('new')
        self.assertEqual([(k,t) for k,t,_ in self.plan()],[('D',str(self.original/'lib64'))])

    def test_minimal_missing_child_absorbs_other_targets_in_same_directory(self):
        (self.original/'etc').mkdir();(self.payload/'etc').mkdir()
        (self.original/'etc/existing').write_text('old')
        (self.payload/'etc/existing').write_text('new')
        (self.payload/'etc/added').write_text('new')
        self.assertEqual([(k,t) for k,t,_ in self.plan()],[('D',str(self.original/'etc'))])

    def test_minimal_rejects_symlink_type_collision_and_overlapping_roots(self):
        (self.original/'file').symlink_to('/dev/null')
        (self.payload/'file').write_text('new')
        result=self.script(': > "$W/targets"\nplan_tree "$ORIGINAL" "$PAYLOAD"',check=False)
        self.assertNotEqual(result.returncode,0)
        result=self.script(': > "$W/targets"\nplan_target D "$ORIGINAL" "$PAYLOAD"\n'
                           'plan_target F "$ORIGINAL/file" "$PAYLOAD/file"',check=False)
        self.assertNotEqual(result.returncode,0)

    def test_minimal_keeps_unrelated_opex_submount_untouched(self):
        (self.original/'bin/hw').mkdir(parents=True)
        (self.original/'lib64/oplusex').mkdir(parents=True)
        self.run_cmd('mount','-t','tmpfs','opex-test',str(self.original/'lib64/oplusex'))
        self.children.append(self.original/'lib64/oplusex')
        (self.original/'lib64/oplusex/stock.so').write_text('opex')
        (self.payload/'bin/hw').mkdir(parents=True)
        (self.payload/'bin/hw/dolby').write_text('new')
        before=self.script('mount_id "$ORIGINAL/lib64/oplusex"').stdout
        self.publish_minimal()
        self.assertEqual(self.script('mount_id "$ORIGINAL/lib64/oplusex"').stdout,before)
        self.assertEqual((self.original/'lib64/oplusex/stock.so').read_text(),'opex')

    def test_minimal_single_file_copy_fallback_stays_private(self):
        (self.original/'file').write_text('old');(self.payload/'file').write_text('new')
        self.assertEqual(self.plan()[0][0],'F')
        result=self.script('mount() { return 1; }\nstage_payload "$PAYLOAD/file" "$W/single"')
        self.assertIn('复制兜底',result.stdout)
        self.assertEqual((self.original/'file').read_text(),'old')
        self.assertEqual((self.work/'single').read_text(),'new')

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
