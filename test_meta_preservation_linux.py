"""Local mount-namespace reproduction. Never accesses an Android device."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parent
ENGINE = REPO / 'assets/ksu/boot/mount-engine.sh'


@unittest.skipUnless(os.name=='posix' and os.geteuid()==0, 'requires Linux root mount namespace')
class PreservationTests(unittest.TestCase):
    def run_case(self, body):
        old = (REPO/'assets/ksu/boot/preserve.sh').read_text()
        with tempfile.TemporaryDirectory(prefix='dolby-meta-preserve-') as folder:
            root = Path(folder)
            module = root / 'module'
            module.mkdir()
            lib = root / 'system_ext/lib64'
            etc = root / 'vendor/etc'
            child = lib / 'oplusex/com.oplus.moduleservices'
            child.mkdir(parents=True)
            (child / 'liboem.so').write_text('old-base-library')
            manifest = etc / 'vintf/manifest.xml'
            manifest.parent.mkdir(parents=True)
            manifest.write_text('stock-manifest')
            live = root / 'opex-live'
            live.mkdir()
            (live / 'liboem.so').write_text('updated-opex-library')
            early = root / 'early-manifest.xml'
            early.write_text('dolby-early-manifest')
            for part in ('lib', 'etc'):
                payload = root / ('payload-' + part) / 'dolby'
                payload.mkdir(parents=True)
                (payload / 'added').write_text('dolby-payload')
            (module / 'mount-roots.txt').write_text(f'{lib}\n{etc}\n')
            # Keep the old save/restore algorithm, adapting only Android paths
            # and its bundled BusyBox command to this disposable Linux fixture.
            old = old.replace('M=${0%/*}', 'M="$MODULE"')
            old = old.replace('S=/dev/mio-preserve-mio_dolby_c17_generated', 'S="$SNAPSHOT"')
            old = old.replace('BB=/data/adb/ksu/bin/busybox', 'BB=')
            old = old.replace('/system/*|/system_ext/*|/vendor/*|/product/*|/odm/*',
                              str(root) + '/*')
            script = module / 'preserve.sh'
            script.write_text(old)
            env = os.environ | {
                'MODULE': str(module), 'SNAPSHOT': str(root / 'snapshot'),
                'LIB': str(lib), 'ETC': str(etc), 'CHILD': str(child),
                'LIVE': str(live), 'EARLY': str(early), 'MANIFEST': str(manifest),
                'LIB_PAYLOAD': str(root / 'payload-lib'),
                'ETC_PAYLOAD': str(root / 'payload-etc'),
                'ENGINE': str(ENGINE), 'W': str(root / 'work'),
                'DOLBY_SELINUX': '0',
            }
            setup = '''set -eu
                mkdir "$W"
                mount --bind "$LIVE" "$CHILD"
                mount --bind "$EARLY" "$MANIFEST"
                overlay_parents() {
                    mount -t overlay -o "lowerdir=$LIB_PAYLOAD:$LIB,ro" KSU "$LIB"
                    mount -t overlay -o "lowerdir=$ETC_PAYLOAD:$ETC,ro" KSU "$ETC"
                }
            '''
            result = subprocess.run(
                ['unshare', '--mount', '--propagation', 'private', 'sh', '-c', setup + body],
                env=env, text=True, capture_output=True, timeout=25)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout

    def test_postmount_payload_success_does_not_prove_oem_children_survive(self):
        self.run_case('''
            overlay_parents
            [ "$(cat "$CHILD/liboem.so")" = old-base-library ]
            [ "$(cat "$MANIFEST")" = stock-manifest ]
            . "$ENGINE"
            : > "$W/targets"
            plan_tree "$LIB" "$LIB_PAYLOAD"
            plan_tree "$ETC" "$ETC_PAYLOAD"
            [ ! -s "$W/targets" ]
            cmp "$LIB/dolby/added" "$LIB_PAYLOAD/dolby/added"
            # A post-overlay recursive mirror still sees the wrong OEM library.
            mkdir "$W/late-mirror"
            mount --rbind "$LIB" "$W/late-mirror"
            [ "$(cat "$W/late-mirror/oplusex/com.oplus.moduleservices/liboem.so")" = old-base-library ]
        ''')

    def test_original_pre_save_and_post_restore_recover_both_children(self):
        self.run_case('''
            sh "$MODULE/preserve.sh" save
            overlay_parents
            [ "$(cat "$CHILD/liboem.so")" = old-base-library ]
            sh "$MODULE/preserve.sh" restore
            [ "$(cat "$CHILD/liboem.so")" = updated-opex-library ]
            [ "$(cat "$MANIFEST")" = dolby-early-manifest ]
            cmp "$LIB/dolby/added" "$LIB_PAYLOAD/dolby/added"
            cmp "$ETC/dolby/added" "$ETC_PAYLOAD/dolby/added"
        ''')

    def test_rebinding_only_vintf_does_not_repair_hidden_oem_library(self):
        self.run_case('''
            overlay_parents
            mount --bind "$EARLY" "$MANIFEST"
            [ "$(cat "$MANIFEST")" = dolby-early-manifest ]
            [ "$(cat "$CHILD/liboem.so")" = old-base-library ]
        ''')


if __name__ == '__main__':
    assert os.geteuid() == 0, 'Run with WSL root inside private mount namespaces'
    unittest.main(verbosity=2)
