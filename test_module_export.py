"""Export a real ZIP from synthetic ROM changes; no private payload or phone."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
import xml.etree.ElementTree as ET
import zipfile

from core import sha
from ksu_module import ModuleBuild


class ModuleExportTests(unittest.TestCase):
    def test_audio_configs_are_standard_payload_and_vintf_is_complete_at_early_init(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            rom=root/'rom'
            build=ModuleBuild.__new__(ModuleBuild)
            build.rom=SimpleNamespace(parts={p:rom/p for p in ('system','system_ext','vendor','odm','product')},
                                      path=lambda n:rom/n,rel=lambda n:n)
            build.session=root/'session'
            build.tree=build.session/'patch_tree'
            build.tree.mkdir(parents=True)
            build.changes={}
            build.require_metadata=False
            build.log=lambda s:None
            build.source_info={'source_kind':'synthetic-test'}
            audio=['odm/etc/audio_effects_config.xml',
                   'vendor/etc/audio/sku_test/audio_effects_config.xml',
                   'vendor/etc/media_codecs_c2_audio.xml']
            build.info={'configuration':{'effects':audio[:2],'codecs':audio[2:]}}
            files={name:b'<test>modified audio config</test>' for name in audio}
            files.update({
                'odm/etc/dolby/dax-default.xml':b'<test>DAX config</test>',
                'vendor/lib64/soundfx/test.so':b'synthetic-library',
                'system/etc/init/00-dolby-native.rc':b'native-only-rc',
                'system_ext/etc/vintf/manifest.xml':b'<manifest type="framework" version="1.0"/>',
                'vendor/etc/vintf/manifest/dolby-native.xml':b'''<manifest type="device" version="1.0">
                    <hal format="aidl"><name>vendor.dolby.dms</name></hal>
                    <hal format="aidl"><name>android.hardware.media.c2</name><fqname>IComponentStore/default9</fqname></hal>
                    </manifest>''',
            })
            for name,data in files.items():
                build.stage(name,data)
            originals={name:b'<test>stock</test>' for name in audio}
            originals.update({
                'system_ext/etc/vintf/manifest.xml':b'<manifest type="framework" version="1.0"/>',
                'vendor/etc/vintf/manifest.xml':b'<manifest type="device" version="1.0"><hal><name>stock.hal</name></hal></manifest>',
                'vendor/etc/selinux/vendor_hwservice_contexts':b'vendor.dolby.hardware.dms::IDms u:object_r:hal_dms_hwservice:s0\n',
                'vendor/etc/selinux/vendor_service_contexts':b'vendor.dolby.dms.IDms/default u:object_r:hal_aidl_dms_service:s0\n',
            })
            for name,data in originals.items():
                path=rom/name
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(data)
            # Deliberately no vendor.audio-hal-aidl RC: startup no longer pins it.
            (build.session/'sepolicy.rule').write_text('# synthetic policy\n')
            build.export_module()
            with zipfile.ZipFile(build.session/'Dolby_C17_KSU.zip') as archive:
                names=set(archive.namelist())
                mounts={row.split('\t')[1]:row.split('\t')[0] for row in archive.read('mounts.tsv').decode().splitlines()}
                labels={row.split('\t')[0]:row.split('\t')[1:] for row in archive.read('labels.tsv').decode().splitlines()}
                for target in audio+['odm/etc/dolby/dax-default.xml']:
                    source='system/'+target
                    self.assertEqual(archive.read(source),files[target])
                    self.assertEqual(mounts['/'+target],source)
                    self.assertEqual(labels[source],['0644','u:object_r:vendor_configs_file:s0'])
                self.assertFalse(any(n.startswith('late/') for n in names))
                self.assertIn('. "$MODPATH/install-early.sh"',archive.read('customize.sh').decode())
                self.assertIn('/system/bin/sh "$MODPATH/freeze-audioeffectcenter.sh"',
                              archive.read('install-early.sh').decode())
                self.assertIn('com.oplus.audio.effectcenter',archive.read('freeze-audioeffectcenter.sh').decode())
                self.assertTrue(names.isdisjoint({'late.tsv','gate.sh','commit.sh','recover.sh',
                                                  'codec.sh','codec-target','codec-manifest.xml','mode'}))
                vintf=[row.split('\t') for row in archive.read('early/vintf.tsv').decode().splitlines()]
                device=next(row for row in vintf if row[1]=='/vendor/etc/vintf/manifest.xml')
                manifest=ET.fromstring(archive.read('early/'+device[0]))
                self.assertEqual([hal.findtext('name') for hal in manifest.findall('hal')],
                                 ['stock.hal','vendor.dolby.dms','android.hardware.media.c2'])
                self.assertEqual(manifest.findtext("./hal[name='android.hardware.media.c2']/fqname"),'IComponentStore/default9')
                for source,target,expected,label in vintf:
                    self.assertEqual(expected,sha(rom/target.lstrip('/')))
                    self.assertEqual(labels['early/'+source],['0644',label])
                runtime=json.loads(archive.read('module-report.json'))['boot_runtime']
                self.assertFalse(runtime['startup_gate'])
                self.assertFalse(runtime['automatic_audio_rollback'])
                self.assertIn('/odm/etc',runtime['child_mount_roots'])
                self.assertEqual(archive.read('solidify/00-dolby-native.rc'),b'native-only-rc')
            for name,data in originals.items():
                self.assertEqual((rom/name).read_bytes(),data,'Input ROM must remain unchanged')


if __name__=='__main__':
    unittest.main()
