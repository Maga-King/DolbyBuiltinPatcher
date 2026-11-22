"""Execute production install helpers against local shell stubs; no Android device."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ASSETS=Path(__file__).parent/'assets/ksu/boot'


@unittest.skipUnless(shutil.which('sh'), 'requires a POSIX shell (run in WSL)')
class InstallHelperTests(unittest.TestCase):
    def run_case(self,kind):
        with tempfile.TemporaryDirectory(prefix='dolby-package-') as tmp:
            root=Path(tmp)
            app=root/'data-app/test/base.apk';app.parent.mkdir(parents=True)
            bundled=root/'module.apk';bundled.write_bytes(b'expected signed APK fixture')
            if kind!='no-install':app.write_bytes(b'wrong APK' if kind=='wrong-apk' else bundled.read_bytes())
            state=root/'package-state.sh'
            state.write_text((ASSETS/'package-state.sh').read_text().replace('/data/app/',str(root/'data-app')+'/'))
            prelude='''
                busybox() { shift; shift; shift; shift; shift; shift; "$@"; }
                sleep() { :; }
                pm() {
                    if [ "$1" = install ]; then
                        echo 'cmd: Failure calling service package: Failed transaction (2147483646)'
                        [ "$CASE" = normal ] && return 0
                        return 1
                    fi
                    if [ "$CASE" = query-fails ]; then echo 'Failed transaction' >&2; return 1; fi
                    printf 'package:%s\\n' "$REGISTERED"
                }
                . "$HELPER"
                BB=busybox
                APP=org.lunaris.dolby
                dolby_install_update "$APK"
            '''
            registered=root/'system-app/base.apk' if kind=='system-only' else app
            if kind=='system-only':registered.parent.mkdir();registered.write_bytes(bundled.read_bytes())
            result=subprocess.run(['sh'],input=prelude,text=True,capture_output=True,timeout=10,
                env=os.environ|{'HELPER':str(state),'CASE':kind,'REGISTERED':str(registered),'APK':str(bundled),'R':tmp})
            self.assertEqual(bundled.read_bytes(),b'expected signed APK fixture')
            return result

    def test_binder_error_after_install_is_verified_success(self):
        result=self.run_case('committed-error')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('Failed transaction',result.stdout)

    def test_normal_install_is_verified(self):
        self.assertEqual(self.run_case('normal').returncode,0)

    def test_actual_install_failure_wrong_apk_or_mount_cannot_be_success(self):
        for kind in ('no-install','wrong-apk','system-only','query-fails'):
            with self.subTest(kind=kind):self.assertEqual(self.run_case(kind).returncode,1)

    def test_coloros_unlock_command_falls_back_without_false_success(self):
        prelude='''
            busybox() { shift; shift; shift; shift; shift; shift; "$@"; }
            cmd() {
                if [ "$1" = activity ]; then printf '%s\\n' "$ACTIVITY"; return 0; fi
                printf '%s\\n' "$USER_QUERY"
            }
            . "$HELPER"
            BB=busybox
            dolby_user_unlock_state
        '''
        cases=[('RUNNING_UNLOCKED','Unknown command: is-user-unlocked','true'),
               ('RUNNING_LOCKED','true','false'),
               ('Unknown command','true','true'),
               ('Unknown command','Unknown command: is-user-unlocked','unknown')]
        for activity,user_query,expected in cases:
            with self.subTest(activity=activity,user_query=user_query):
                result=subprocess.run(['sh'],input=prelude,text=True,capture_output=True,timeout=10,
                    env=os.environ|{'HELPER':str(ASSETS/'user-state.sh'),'ACTIVITY':activity,'USER_QUERY':user_query})
                self.assertEqual(result.stdout.strip(),expected,result.stderr)


if __name__=='__main__':unittest.main()
