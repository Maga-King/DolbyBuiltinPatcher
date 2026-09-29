"""Opt-in Android Enforcing tests; explicit serial, private namespace, synthetic files.

No module installation, no real partition mounts or service/property changes.
Requires KSU BusyBox unshare. Example: --serial SERIAL --adb /path/to/adb.
"""
import argparse
from pathlib import Path
import shlex
import tempfile
import time
import uuid
import adb_mode

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial',required=True)
    parser.add_argument('--adb',required=True)
    args=parser.parse_args()
    adb_mode.adb_path=lambda:args.adb
    adb=adb_mode.Adb(args.serial)
    repo=Path(__file__).resolve().parent
    tag='dolby-mount-lab-'+time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    source='/data/local/tmp/'+tag+'-source'
    lab='/data/local/tmp/'+tag
    out=repo/'validation'/tag;out.mkdir(parents=True)
    initial=adb.shell('cat /proc/1/mountinfo\nps -A | grep -E "dolby|audioserver|audiohal" || true')
    (out/'before.txt').write_bytes(initial)
    q=shlex.quote
    adb.shell('test ! -e '+q(source)+'\ntest ! -e '+q(lab)+'\nmkdir -m 0700 '+q(source)+' '+q(lab))
    try:
        with tempfile.TemporaryDirectory(prefix='dolby-android-lab-') as temporary:
            staging=Path(temporary)
            for name in ('mount-engine.sh','repair-mounts.sh','preserve.sh'):
                text=(repo/'assets/ksu/boot'/name).read_text(encoding='utf-8')
                text=text.replace('S=/dev/mio-preserve-mio_dolby_c17_generated','S="'+lab+'/snapshot"')
                text=text.replace('W=/dev/mio-dolby-meta-repair4','W="'+lab+'/repair-work"')
                text=text.replace('/system/*|/system_ext/*|/vendor/*|/product/*|/odm/*',lab+'/*')
                text=text.replace('[ "$(readlink /proc/self/ns/mnt)" = "$(readlink /proc/1/ns/mnt)" ]',
                                  '[ "$(readlink /proc/self/ns/mnt)" != "$(readlink /proc/1/ns/mnt)" ]')
                text=text.replace('/proc/1/root','/proc/self/root')
                # Simulate only the pre-audio state; never change a real system property.
                text=text.replace('DOLBY_SELINUX=1','DOLBY_SELINUX=1\ngetprop() { [ "$CASE" != late ] && echo stopped || echo running; }')
                (staging/name).write_text(text,encoding='utf-8',newline='\n')
                adb.push(staging/name,source+'/'+name)
            adb.push(repo/'diagnostics/mount-lab-case.sh',source+'/case.sh')
            for case in ('all','partial','wrong-mode','wrong-label','missing-directory','late','none','empty'):
                command=f'LAB={q(lab)} SOURCE={q(source)} CASE={q(case)} /data/adb/ksu/bin/busybox timeout -k 3 25 /data/adb/ksu/bin/busybox unshare -m /system/bin/sh {q(source)}/case.sh'
                data=adb.shell(command,timeout=35)
                (out/(case+'.txt')).write_bytes(data)
                print(data.decode(errors='replace'),flush=True)
        final=adb.shell('cat /proc/1/mountinfo\nps -A | grep -E "dolby|audioserver|audiohal" || true')
        (out/'after.txt').write_bytes(final)
        assert lab.encode() not in final, 'Lab mount leaked into init namespace'
        print('INIT_NAMESPACE_HAS_NO_LAB_MOUNTS',out)
    finally:
        # Exact generated leaves, no user-data globs. Namespace has exited first.
        adb.shell('test "$(readlink -f '+q(source)+')" = '+q(source)+'\n'
                  'test "$(readlink -f '+q(lab)+')" = '+q(lab)+'\n'
                  'rmdir '+q(lab)+'\nrm -rf '+q(source))

if __name__=='__main__':main()
