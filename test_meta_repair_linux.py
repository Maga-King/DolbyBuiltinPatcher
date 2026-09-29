"""Synthetic metamodule/conflict fixtures, never installed on an Android phone.

Run in WSL/Linux: sudo python3 test_meta_repair_linux.py
Each case mounts only a disposable directory inside a private mount namespace.
Android namespace/SELinux helpers are adapted, not proof of phone compatibility.
"""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
SCRIPTS=HERE/'assets/ksu/boot'


@unittest.skipUnless(os.name=='posix' and os.geteuid()==0, 'requires Linux root mount namespace')
class RepairTests(unittest.TestCase):
    def case(self, *, meta='partial', new_directory=False, bad_mode=False, fail_readonly=False,
             conflict=False, layers=1, bind_failure=False, late_audio=False, disabled=False,
             repeat=False, symlink_conflict=False, relocate=False, preserve_conflict=False,
             late_foreign=False):
        with tempfile.TemporaryDirectory(prefix='dolby-meta4-') as folder:
            base=Path(folder)
            module=base/'module'; module.mkdir()
            root=base/'vendor/lib64'; root.mkdir(parents=True)
            child=root/'opex'; child.mkdir()
            live=base/'live'; live.mkdir(); (live/'oem.so').write_text('updated-oem')
            (child/'oem.so').write_text('base-oem')
            public=module/'system/vendor/lib64'; public.mkdir(parents=True)
            files=['one.so','newdir/two.so' if new_directory else 'two.so']
            for name in files:
                p=public/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text('dolby-'+name)
                if '/' not in name: (root/name).write_text('old-'+name)
            upper=base/'upper'; upper.mkdir()
            for name in (files if meta=='all' else files[:1] if meta=='partial' else []):
                dest=upper/name; dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes((public/name).read_bytes())
                dest.chmod(0o600 if bad_mode and name==files[1] else 0o644)
            (module/'mount-roots.txt').write_text(str(root)+'\n')
            (module/'mounts.tsv').write_text(''.join(f'system/vendor/lib64/{name}\t{root/name}\tunused\n' for name in files))
            (module/'labels.tsv').write_text(''.join(f'system/vendor/lib64/{name}\t0644\tu:object_r:vendor_file:s0\n' for name in files))
            (module/'.runtime').mkdir()
            if disabled:(module/'disable').touch()
            conflict_file=base/'foreign.so';conflict_file.write_text('foreign-module')
            if symlink_conflict:
                (root/'two.so').unlink()
                (root/'two.so').symlink_to(conflict_file)
            if relocate:
                (module/'system/vendor').rename(module/'vendor')
                (module/'system/vendor').symlink_to('../vendor')
            (module/'mount-engine.sh').write_bytes((SCRIPTS/'mount-engine.sh').read_bytes())
            preserve=(SCRIPTS/'preserve.sh').read_text().replace('S=/dev/mio-preserve-mio_dolby_c17_generated','S="$SNAPSHOT"')
            preserve=preserve.replace('BB=/data/adb/ksu/bin/busybox','BB=')
            preserve=preserve.replace('/system/*|/system_ext/*|/vendor/*|/product/*|/odm/*',str(base)+'/*')
            (module/'preserve.sh').write_text(preserve)
            repair=(SCRIPTS/'repair-mounts.sh').read_text()
            repair=repair.replace('S=/dev/mio-preserve-mio_dolby_c17_generated','S="$SNAPSHOT"')
            repair=repair.replace('W=/dev/mio-dolby-meta-repair4','W="$REPAIR_WORK"')
            repair=repair.replace('mount() { "$BB" mount "$@"; }','''mount() {
                for last in "$@"; do :; done
                if [ "${FAIL_STAGE_BIND:-0}" = 1 ] && [ "$1" = -o ] && [ "$2" = bind ]; then
                    case "$last" in "$REPAIR_WORK"/*) return 1;; esac
                fi
                case "$*" in *remount,bind,ro*)
                    for last in "$@"; do :; done
                    if [ "${FAIL_READONLY:-0}" = 1 ] && [ "$last" = "$ROOT/two.so" ]; then return 1; fi;;
                esac
                command mount "$@"
            }''')
            repair=repair.replace('umount() { "$BB" umount "$@"; }','umount() { command umount "$@"; }')
            repair=repair.replace('DOLBY_SELINUX=1','DOLBY_SELINUX=0\nchcon() { return 0; }\ngetprop() { echo "${AUDIO_STATE:-stopped}"; }')
            repair=repair.replace('[ "$(readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)" ]','[ 1 = 1 ]')
            repair=repair.replace('/proc/1/root','/proc/self/root')
            (module/'repair-mounts.sh').write_text(repair)
            env=os.environ|dict(M=str(module),ROOT=str(root),CHILD=str(child),LIVE=str(live),UPPER=str(upper),
                SNAPSHOT=str(base/'snapshot'),REPAIR_WORK=str(base/'repair-work'),META=meta,
                EXPECT_FAIL='1' if meta in ('none','empty') or fail_readonly or late_audio or disabled or symlink_conflict or preserve_conflict else '0',
                CONFLICT=str(int(conflict)),LAYERS=str(layers),FAIL_STAGE_BIND=str(int(bind_failure)),
                AUDIO_STATE='running' if late_audio else 'stopped',REPEAT=str(int(repeat)),
                FOREIGN=str(conflict_file),PRESERVE_CONFLICT=str(int(preserve_conflict)),
                LATE_FOREIGN=str(int(late_foreign)),
                FAIL_READONLY='1' if fail_readonly else '0',NEW_DIRECTORY='1' if new_directory else '0',BAD_MODE='1' if bad_mode else '0')
            script='''set -eu
                mount --bind "$LIVE" "$CHILD"
                if [ "$PRESERVE_CONFLICT" = 1 ]; then mount --bind "$FOREIGN" "$ROOT/two.so"; fi
                sh "$M/preserve.sh" save
                if [ "$META" != none ]; then
                    i=0
                    while [ "$i" -lt "$LAYERS" ]; do
                        if ! mount -t overlay -o "lowerdir=$UPPER:$ROOT,ro" KSU "$ROOT"; then
                            [ "$i" -gt 0 ] || exit 31
                            echo "OVERLAY_STACK_LIMIT_AFTER=$i"
                            break
                        fi
                        i=$((i+1))
                    done
                fi
                if [ "$CONFLICT" = 1 ]; then mount --bind "$FOREIGN" "$ROOT/two.so"; fi
                cp /proc/self/mountinfo "$M/.runtime/meta-before-restore.mountinfo"
                sh "$M/preserve.sh" restore
                cp /proc/self/mountinfo "$M/before-repair"
                awk '/ - overlay / {print $3}' /proc/self/mountinfo | sort -u > "$M/overlay-before"
                if sh "$M/repair-mounts.sh" run; then result=0; else result=$?; fi
                if [ "$EXPECT_FAIL" = 1 ]; then
                    [ "$result" != 0 ] && [ ! -e "$M/.runtime/repair-ok" ]
                    [ "$(cat "$CHILD/oem.so")" = updated-oem ]
                    if [ "$PRESERVE_CONFLICT" = 1 ]; then
                        [ "$(cat "$ROOT/two.so")" = foreign-module ]
                    fi
                    if [ "$FAIL_READONLY" = 1 ]; then
                        [ "$(cat "$ROOT/two.so")" = old-two.so ]
                        awk -v p="$ROOT" '$5==p && / - overlay / {ok=1} END {exit !ok}' /proc/self/mountinfo
                    fi
                else
                    [ "$result" = 0 ]
                    awk '/ - overlay / {print $3}' /proc/self/mountinfo | sort -u > "$M/overlay-after"
                    cmp "$M/overlay-before" "$M/overlay-after"
                    cmp "$M/.runtime/repair-ok" /proc/sys/kernel/random/boot_id
                    [ "$(cat "$CHILD/oem.so")" = updated-oem ]
                    cmp "$ROOT/one.so" "$M/system/vendor/lib64/one.so"
                    if [ "$NEW_DIRECTORY" = 1 ]; then
                        cmp "$ROOT/newdir/two.so" "$M/system/vendor/lib64/newdir/two.so"
                    else
                        cmp "$ROOT/two.so" "$M/system/vendor/lib64/two.so"
                        [ "$(stat -c %a "$ROOT/two.so")" = 644 ]
                    fi
                    if [ "$META" = all ] && [ "$BAD_MODE" = 0 ]; then
                        if [ "$CONFLICT" = 0 ]; then
                            [ ! -e "$REPAIR_WORK" ]
                            cmp "$M/before-repair" /proc/self/mountinfo
                        fi
                    fi
                    if [ "$REPEAT" = 1 ]; then
                        cp /proc/self/mountinfo "$M/before-repeat"
                        sh "$M/repair-mounts.sh" run
                        cmp "$M/before-repeat" /proc/self/mountinfo
                    fi
                    if [ "$LATE_FOREIGN" = 1 ]; then
                        mount --bind "$FOREIGN" "$ROOT/two.so"
                        . "$M/mount-engine.sh"
                        W="$REPAIR_WORK"
                        rollback_publications
                        [ "$(cat "$ROOT/two.so")" = foreign-module ]
                    fi
                fi
            '''
            run=subprocess.run(['unshare','--mount','--propagation','private','sh','-c',script],env=env,text=True,capture_output=True,timeout=25)
            self.assertEqual(run.returncode,0,run.stdout+'\n'+run.stderr)
            return run.stdout

    def test_all_provided_no_extra_mounts(self): self.case(meta='all')
    def test_partial_file_repair(self): self.case()
    def test_missing_directory_repair_preserves_oem_child(self): self.case(new_directory=True)
    def test_matching_content_wrong_mode_is_repaired(self): self.case(meta='all',bad_mode=True)
    def test_absent_metamodule_does_not_become_self_mount(self): self.case(meta='none')
    def test_empty_metamodule_does_not_become_self_mount(self): self.case(meta='empty')
    def test_readonly_failure_rolls_back_only_repair(self): self.case(fail_readonly=True)
    def test_foreign_file_overrides_metamodule_before_repair(self):self.case(meta='all',conflict=True)
    def test_overlay_stack_limit_needs_no_additional_overlay(self):self.case(layers=8,new_directory=True)
    def test_payload_bind_failure_uses_bounded_copy(self):
        self.assertIn('复制兜底',self.case(bind_failure=True))
    def test_late_audio_does_not_publish(self):self.case(late_audio=True)
    def test_disabled_module_does_not_publish(self):self.case(disabled=True)
    def test_repeat_repair_does_not_add_mounts(self):self.case(repeat=True)
    def test_payload_symlink_collision_is_refused(self):self.case(symlink_conflict=True)
    def test_installer_partition_relocation(self):self.case(relocate=True)
    def test_preserved_foreign_dolby_path_is_not_silently_displaced(self):self.case(preserve_conflict=True)
    def test_rollback_leaves_later_foreign_mount_in_place(self):self.case(late_foreign=True)


if __name__=='__main__':
    assert os.geteuid()==0
    unittest.main(verbosity=2)
