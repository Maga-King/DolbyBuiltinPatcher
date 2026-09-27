import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import xml.etree.ElementTree as ET
from core import (ASSETS, PatchError, apply_session, append_cil, merge_effects, merge_codecs,
                  merge_framework, safe, sha, save_json)

class MergeTests(unittest.TestCase):
    def test_real_vendor_xml_namespaces_and_include_root(self):
        effects=(ASSETS/'effects-reference.xml').read_bytes()
        result=merge_effects(effects,effects)
        self.assertEqual(result,merge_effects(result,effects))
        codecs=(ASSETS/'codecs-reference.xml').read_bytes()
        self.assertEqual(ET.fromstring(merge_codecs(codecs,codecs)).tag,'Included')
        self.assertIn(b'Copyright',merge_codecs(codecs,codecs))

    def test_effects_preserve_stock_and_are_idempotent(self):
        original=b'<audio_effects_conf version="2.0"><libraries><library name="stock" path="stock.so"/></libraries><effects><effect name="stock_fx" library="stock" uuid="stock-uuid"/></effects><postprocess><stream type="music"/></postprocess></audio_effects_conf>'
        ref=(ASSETS/'effects-reference.xml').read_bytes()
        result=merge_effects(original,ref)
        root=ET.fromstring(result)
        self.assertEqual(root.find("./effects/effect[@name='stock_fx']").get('uuid'),'stock-uuid')
        self.assertIsNotNone(root.find('./postprocess/stream'))
        self.assertEqual(merge_effects(result,ref),result)
        self.assertEqual(root.find("./effects/effect[@name='dap']").get('type'),'46d279d9-9be7-453d-9d7c-ef937f675587')

    def test_conflicting_effect_rejected(self):
        data=b'<audio_effects_conf><libraries><library name="dolby_dap_lab" path="other.so"/></libraries><effects/></audio_effects_conf>'
        with self.assertRaises(PatchError):merge_effects(data,(ASSETS/'effects-reference.xml').read_bytes())

    def test_codecs_keep_encoder_and_include(self):
        data=b'<MediaCodecs><Include href="stock.xml"/><Decoders><MediaCodec name="c2.qti.foo"/></Decoders><Encoders><MediaCodec name="enc"/></Encoders></MediaCodecs>'
        ref=(ASSETS/'codecs-reference.xml').read_bytes()
        result=merge_codecs(data,ref)
        root=ET.fromstring(result)
        self.assertEqual(len(root.findall('./Decoders/MediaCodec')),3)
        self.assertEqual(root.find('./Include').get('href'),'stock.xml')
        self.assertIsNotNone(root.find('./Encoders/MediaCodec'))
        self.assertEqual(result,merge_codecs(result,ref))

    def test_framework_preserves_non_hidl_limits(self):
        source=b'<manifest type="framework" version="9.0"><hal format="hidl" max-level="8"><name>android.hidl.manager</name></hal><hal max-level="9"><name>stock</name></hal></manifest>'
        result=merge_framework(source);root=ET.fromstring(result)
        self.assertIsNone(root.findall('hal')[0].get('max-level'))
        self.assertEqual(root.findall('hal')[1].get('max-level'),'9')
        self.assertEqual(result,merge_framework(result))

    def test_cil_idempotent(self):
        result=append_cil('(type original)\n','(type extra)')
        self.assertEqual(append_cil(result,'(type extra)'),result)
        self.assertIn('(type original)',result)

class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.rom=SimpleNamespace(parts={p:self.root/p for p in ('vendor','odm')},path=lambda n:self.root/n)
        header=bytearray(64);header[:5]=b'\x7fELF\x02';header[18:20]=b'\xb7\x00'
        self.put('vendor/lib64/hw/libaudioeffecthal.qti.so',bytes(header)+b'audio_effects_custom.xml\x00')
        for sku in ('everest','newchip'):
            self.put(f'vendor/etc/audio/sku_{sku}/audio_effects_custom.xml',b'<audio_effects_conf><libraries/><effects/></audio_effects_conf>')
        self.audio=b'<Included><Decoders><MediaCodec name="c2.vendor.flac.decoder" type="audio/flac"/></Decoders></Included>'

    def put(self,name,data):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)

    def test_custom_platform_and_filename_shared_leaf(self):
        from discovery import discover
        self.put('vendor/etc/shared_audio.xml',self.audio)
        for sku in ('everest','newchip'):
            self.put(f'vendor/etc/media_codecs_{sku}.xml',b'<MediaCodecs><Include href="shared_audio.xml"/></MediaCodecs>')
        info=discover(self.rom)
        self.assertEqual(info['codecs'],['vendor/etc/shared_audio.xml'])
        self.assertEqual(len(info['effects']),2)
        self.assertEqual(len(info['codec_entry_coverage']),2)

    def test_two_disjoint_platform_directories(self):
        from discovery import discover
        for sku in ('one','two'):
            self.put(f'vendor/etc/{sku}/media_codecs.xml',b'<MediaCodecs><Include href="local.xml"/></MediaCodecs>')
            self.put(f'vendor/etc/{sku}/local.xml',self.audio)
        self.assertEqual(len(discover(self.rom)['codecs']),2)

    def test_missing_include_blocks_candidate(self):
        from discovery import discover
        self.put('vendor/etc/media_codecs.xml',self.audio.replace(b'<Decoders>',b'<Include href="missing.xml"/><Decoders>'))
        with self.assertRaises(PatchError):discover(self.rom)

    def test_duplicate_include_and_cycle_rejected(self):
        from discovery import discover
        self.put('vendor/etc/shared_audio.xml',self.audio)
        self.put('vendor/etc/media_codecs.xml',b'<MediaCodecs><Include href="shared_audio.xml"/><Include href="shared_audio.xml"/></MediaCodecs>')
        with self.assertRaises(PatchError):discover(self.rom)
        self.put('vendor/etc/media_codecs.xml',b'<MediaCodecs><Include href="media_codecs.xml"/></MediaCodecs>')
        with self.assertRaises(PatchError):discover(self.rom)

    def test_mtk_or_32bit_backend_rejected(self):
        from discovery import discover
        self.put('vendor/lib64/hw/libaudioeffecthal.qti.so',b'not-arm64')
        with self.assertRaises(PatchError):discover(self.rom)

class PackingTests(unittest.TestCase):
    def test_dna_exact_lookup_preserves_hyphen_paths(self):
        from core import context_key,upsert_context
        import re
        paths=['vendor/bin/hw/vendor.dolby.hardware.dms@2.0-service',
               'vendor/etc/dolby/dax-default.xml','vendor/etc/vintf/manifest/dolby-native.xml',
               'odm/etc/dolby/dax-default.xml',
               'system_ext/lib64/dolbyaidl/vendor.dolby.dms-V1-ndk_dolby.so',
               'system_ext/lib64/dolbyaidl/android.hardware.media.c2-V1-ndk_dolby.so']
        for path in paths:
            key=context_key(path)
            self.assertNotIn(r'\-',key)
            self.assertIsNotNone(re.fullmatch(key,'/'+path))
            lines=upsert_context([],path,'u:object_r:correct:s0')
            lookup=dict(line.split() for line in lines)
            self.assertEqual(lookup[key],'u:object_r:correct:s0')

    def test_context_update_merges_legacy_and_dna_duplicates(self):
        from core import context_key,upsert_context
        import re
        path='vendor/bin/hw/dolby-test.so';key=context_key(path)
        lines=['# user comment','/'+re.escape(path)+' old_type',key+' wrong_type','/unrelated other_type']
        fixed=upsert_context(lines,path,'correct_type')
        self.assertEqual(fixed,['# user comment',key+' correct_type','/unrelated other_type'])
        self.assertEqual(upsert_context(fixed,path,'correct_type'),fixed)
        self.assertEqual(upsert_context([key+' kept_type'],path,'ignored',False),[key+' kept_type'])

    def test_slot_directory_uses_metadata_key_not_slot_name(self):
        from core import Rom, write
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for part in ('system_a/system','system_ext_a','vendor_a','odm_a','product_a'):
                (root/part/'etc').mkdir(parents=True)
            write(root/'config/system_a_fs_config','system/system/etc/init 0 0 0755\n')
            write(root/'config/vendor_a_file_contexts','/vendor/etc/selinux u:object_r:vendor_configs_file:s0\n')
            rom=Rom(root)
            self.assertEqual(rom.packing_prefix('system','fs_config'),('system_a/system','system/system'))
            self.assertEqual(rom.packing_prefix('vendor','file_contexts'),('vendor_a','vendor'))

class PolicyTests(unittest.TestCase):
    def test_stock_rules_export_existing_grants_without_lifting_conditionals(self):
        from policy_sources import forms,stock_rules
        source='''; (allow bogus fake (file (read)))
(type hal_dms_default)
(allow hal_dms_default vendor_data_file (file (read write)))
(booleanif gate (true (allow hal_dms_default secret (file (read)))))
(filecon "/quoted(path)" file context)
(neverallow domain hal_dms_default (process (ptrace)))'''
        statements=list(forms(source))
        self.assertEqual(len(statements),5)
        grants,records=stock_rules({'vendor.cil':source})
        self.assertEqual(grants['vendor.cil'],['(allow hal_dms_default vendor_data_file (file (read write)))'])
        self.assertTrue(any(r['cil'].startswith('(neverallow') for r in records))
        self.assertTrue(any(r['cil'].startswith('(type ') for r in records))
        # Rebuilding an already-patched ROM must not re-import the tool's own block.
        patched=append_cil(source,'\n'.join(grants['vendor.cil'])+'\n(allow hal_dms_default another (file (read)))')
        again,_=stock_rules({'vendor.cil':patched})
        self.assertEqual(again,grants)

    def test_missing_type_adaptation_requires_evidence_not_empty_declarations(self):
        from policy_sources import adapt
        row=dict(source='dms',target='urandom_device',object_class='chr_file',permissions=['read'],
                 cil='(allow dms urandom_device (chr_file (read)))')
        branches={'normal':({'dms','random_device'},{'chr_file':{'read'}})}
        result,report=adapt([row],branches,{'urandom_device':[dict(target='random_device',entry='/dev/urandom')]})
        self.assertEqual(result[0]['target'],'random_device')
        self.assertEqual(len(report),1)
        self.assertEqual(result[0]['adapted_from'],row['cil'])
        unresolved,report=adapt([row],branches,{'urandom_device':[]})
        self.assertEqual(unresolved,[row]);self.assertFalse(report)

    def test_upstream_attributes_reused_or_defined_without_duplicate_types(self):
        from policy_sources import upstream_delta
        names={'hal_dms','hal_dms_client','hal_dms_server'}
        existing=upstream_delta({'normal':(names,{}),'debug':(names,{})})
        self.assertNotIn('(typeattribute hal_dms)',existing)
        absent=upstream_delta({'normal':(set(),{}),'debug':(set(),{})})
        self.assertIn('(typeattribute hal_dms)',absent)
        self.assertNotIn('(type hal_dms_default)',absent)
        with self.assertRaises(PatchError):upstream_delta({'normal':(names,{}),'debug':(set(),{})})

    def test_upstream_effective_macro_grants_and_export(self):
        from policy_rules import magisk_rules
        source=(ASSETS/'upstream-lunaris/expanded.cil').read_text(encoding='utf-8')
        exported=magisk_rules(source)
        self.assertIn('allow hal_dms_default init unix_stream_socket { connectto }',exported)
        self.assertIn('allow hal_dms_server hidl_base_hwservice hwservice_manager { add }',exported)
        self.assertIn('typeattribute hal_dms_default halserverdomain',exported)
        self.assertIn('dontaudit init hal_dms_default process { noatsecure }',exported)
        self.assertIn('ioctl lock map watch watch_reads append write',exported)

    def test_context_merge_refuses_conflicting_service_label(self):
        from policy_sources import ensure_contexts
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);name='vendor/etc/selinux/vendor_hwservice_contexts'
            path=root/name;path.parent.mkdir(parents=True)
            original='vendor.dolby.hardware.dms::IDms u:object_r:other_hwservice:s0\n'
            path.write_text(original,encoding='utf-8')
            build=SimpleNamespace(get=lambda name:root/name)
            with self.assertRaises(PatchError):ensure_contexts(build)
            self.assertEqual(path.read_text(encoding='utf-8'),original)

    def test_native_compiler_error_codes_not_confused_with_crashes(self):
        from policy import semantic_failure
        log='Failed to resolve AST\nFailed to compile cildb: -2'
        for code in (-2,4294967294,4294967295,1):
            self.assertTrue(semantic_failure(code,log))
        for code in (0,0xc0000005,0xc0000409,-12):
            self.assertFalse(semantic_failure(code,log))
        self.assertFalse(semantic_failure(4294967295,'Failed to open input\n'+log))
        self.assertFalse(semantic_failure(4294967295,'Out of memory\n'+log))

    def test_symbols_common_permissions_and_comment_exclusion(self):
        from policy_rules import symbols
        types,classes=symbols('''; (type fake)
            (type dms) (typeattribute hal_server) (typealias alias)
            (common file (read open map)) (class file (entrypoint)) (classcommon file file)
            (filecon "/(type quoted)" file context)''')
        self.assertEqual(types,{'dms','hal_server','alias'})
        self.assertEqual(classes['file'],{'read','open','map','entrypoint'})

    def test_select_requires_both_branches_and_reports_missing(self):
        from policy_rules import select
        row=dict(source='dms',target='lib',object_class='file',permissions=['read','map'])
        normal=({'dms','lib'},{'file':{'read','map'}})
        debug=({'dms'},{'file':{'read'}})
        accepted,skipped=select([row],{'normal':normal,'debug':debug})
        self.assertFalse(accepted)
        why=skipped[0]['reasons'][0]
        self.assertEqual(why['branch'],'debug')
        self.assertEqual(why['missing_types'],['lib'])
        self.assertEqual(why['missing_permissions'],['map'])

    def test_optional_bisection_retains_all_other_rules(self):
        from policy_rules import filter_compilable
        rows=[dict(id=i) for i in range(9)]
        def trial(selected):
            return {'detail':'bad rule'} if any(r['id'] in (2,7) for r in selected) else None
        good,bad=filter_compilable(rows,trial)
        self.assertEqual([r['id'] for r in good],[0,1,3,4,5,6,8])
        self.assertEqual([r['id'] for r in bad],[2,7])
        self.assertTrue(all(r['diagnostic'] for r in bad))

    def test_optional_filter_stops_on_infrastructure_or_baseline_failure(self):
        from policy_rules import filter_compilable
        with self.assertRaises(TimeoutError):
            filter_compilable([dict(id=1)],lambda rows: (_ for _ in ()).throw(TimeoutError()))
        with self.assertRaises(RuntimeError):
            filter_compilable([dict(id=1)],lambda rows: dict(error='always fails'))

    def test_baseline_failure_never_reaches_filter_or_staging(self):
        from policy import compile_all
        from core import write
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);session=root/'output';session.mkdir()
            name='vendor/etc/selinux/vendor_sepolicy.cil'
            original=root/name;original.parent.mkdir(parents=True)
            original.write_text('(type original)\n(neverallow original original (file (write)))\n',encoding='utf-8')
            before=original.read_bytes()
            build=SimpleNamespace(rom=SimpleNamespace(path=lambda n:root/n),session=session,log=lambda s:None)
            result=SimpleNamespace(returncode=1,stdout=b'',stderr=b'Failed to resolve allow statement')
            # The subprocess is mocked; a source-only checkout needs no compiler binary.
            fixture_assets=root/'fixture-assets'
            write(fixture_assets/'native/secilc.exe','test-only placeholder; never executed')
            with patch('policy.inputs',return_value=[name]),patch('policy.subprocess.run',return_value=result) as run, \
                 patch('policy_rules.filter_compilable',side_effect=AssertionError('must not filter stock')), \
                 patch('policy.ASSETS',fixture_assets):
                with self.assertRaisesRegex(PatchError,'baseline'):compile_all(build)
                self.assertIn('-N',run.call_args.args[0])
            self.assertEqual(original.read_bytes(),before)

    def test_catalog_has_no_global_wildcards_permissive_or_transition(self):
        from policy_rules import catalog,magisk_rules
        rows=catalog()
        self.assertGreater(len(rows),150)
        self.assertTrue(all(r['cil'].startswith('(allow ') and '*' not in r['cil'] for r in rows))
        self.assertTrue(all(r['source'] not in ('domain','appdomain') and r['target']!='file_type' for r in rows))
        essential=(ASSETS/'dolby.cil').read_text(encoding='utf-8')
        exported=magisk_rules(essential+'\n'+'\n'.join(r['cil'] for r in rows))
        self.assertIn('type_transition init hal_dms_default_exec process hal_dms_default',exported)
        self.assertNotIn('permissive ',exported)
        with self.assertRaises(ValueError):magisk_rules('(type invented)')

    def test_append_preserves_stock_neverallow_and_broad_grants(self):
        stock='(neverallow a b (file (write)))\n(allow domain file_type (file (read write)))\n'
        result=append_cil(stock,'(allow dolby lib (file (read)))')
        self.assertTrue(result.startswith(stock))
        self.assertEqual(result,append_cil(result,'(allow dolby lib (file (read)))'))

class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        base=Path(self.tmp.name);self.rom=base/'rom';self.session=base/'session'
        self.rom.mkdir();self.session.mkdir()
        (self.rom/'old').write_bytes(b'original')
        for name in ('patch_tree','original_files'):(self.session/name).mkdir()
        (self.session/'original_files/old').write_bytes(b'original')
        (self.session/'patch_tree/old').write_bytes(b'patched')
        (self.session/'patch_tree/new').write_bytes(b'new')
        rows=[dict(path='old',before=sha(self.rom/'old'),after=sha(self.session/'patch_tree/old')),
              dict(path='new',before=None,after=sha(self.session/'patch_tree/new'))]
        save_json(self.session/'report.json',dict(rom=str(self.rom),applied=False,files=rows))

    def test_apply_then_restore(self):
        apply_session(self.session)
        self.assertEqual((self.rom/'old').read_bytes(),b'patched')
        self.assertTrue((self.rom/'new').is_file())
        apply_session(self.session,restore=True)
        self.assertEqual((self.rom/'old').read_bytes(),b'original')
        self.assertFalse((self.rom/'new').exists())

    def test_changed_input_refuses_all_writes(self):
        (self.rom/'old').write_bytes(b'user change')
        with self.assertRaises(PatchError):apply_session(self.session)
        self.assertFalse((self.rom/'new').exists())
        self.assertEqual((self.rom/'old').read_bytes(),b'user change')

    def test_corrupt_payload_refuses_all_writes(self):
        (self.session/'patch_tree/new').write_bytes(b'corrupted')
        with self.assertRaises(PatchError):apply_session(self.session)
        self.assertEqual((self.rom/'old').read_bytes(),b'original')

    def test_mid_apply_failure_rolls_back(self):
        import core
        original=core.os.replace;calls=[]
        def fail_second(src,dst):
            calls.append(str(dst))
            if len(calls)==2:raise OSError('test disk failure')
            return original(src,dst)
        with patch('core.os.replace',side_effect=fail_second):
            with self.assertRaises(OSError):apply_session(self.session)
        self.assertEqual((self.rom/'old').read_bytes(),b'original')
        self.assertFalse((self.rom/'new').exists())

    def test_restore_preserves_later_user_changes(self):
        apply_session(self.session)
        (self.rom/'new').write_bytes(b'user edit')
        with self.assertRaises(PatchError):apply_session(self.session,restore=True)
        self.assertEqual((self.rom/'old').read_bytes(),b'patched')

    def test_path_traversal_rejected(self):
        for p in ('../outside','/absolute','C:/Windows','a\\..\\b'):
            with self.assertRaises(PatchError):safe(self.rom,p)

class AdbTests(unittest.TestCase):
    def test_remote_root_cannot_be_live_partition_or_broad_directory(self):
        from adb_mode import remote_root
        self.assertEqual(remote_root('/data/DNA/DNA_AB/'),'/data/DNA/DNA_AB')
        self.assertEqual(remote_root('/sdcard/ROM 文件夹'),'/sdcard/ROM 文件夹')
        for value in ('','/','/data','/vendor/etc','/system/system','/data/local/tmp',
                      '/storage/emulated/0','/data/DNA/../adb','/data/DNA/a\nb'):
            with self.assertRaises(PatchError):remote_root(value)

    def test_host_cache_path_ambiguities_rejected(self):
        from adb_mode import relative_path
        self.assertEqual(relative_path('vendor/etc/中文 文件.xml'),'vendor/etc/中文 文件.xml')
        for path in ('../outside','/data/other','config/x:y','vendor/CON','vendor/x.','config/a\tb','a\\b'):
            with self.assertRaises(PatchError):relative_path(path)

    def test_explicit_device_is_bound_even_with_multiple_connected(self):
        from adb_mode import Adb
        rows=[dict(serial='phone-one',state='device',model='one'),dict(serial='phone-two',state='device',model='two')]
        response=SimpleNamespace(returncode=0,stdout=b'0\r\n',stderr=b'')
        with patch('adb_mode.devices',return_value=rows),patch('adb_mode.execute',return_value=response) as execute:
            with self.assertRaises(PatchError):Adb('')
            adb=Adb('phone-two');adb.shell('id')
            for call in execute.call_args_list:
                self.assertEqual(call.args[0][1:3],['-s','phone-two'])
                self.assertEqual(call.args[0][3:5],['shell','-T'])

    def test_multiple_devices_are_not_silently_first_selected(self):
        from adb_mode import Adb
        with patch('adb_mode.devices',return_value=[dict(serial='one',state='device',model='one')]):
            with self.assertRaises(PatchError):Adb('not-connected')

    def test_in_place_is_default_without_user_output_directory(self):
        from patcher_workflow import patch_local
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            fake=SimpleNamespace(run=lambda:root/'session')
            with patch('patcher_workflow.history_root',return_value=root),patch('patcher_workflow.Build',return_value=fake), \
                 patch('patcher_workflow.apply_session') as apply:
                patch_local('rom');apply.assert_called_once()
            with patch('patcher_workflow.history_root',return_value=root),patch('patcher_workflow.Build',return_value=fake), \
                 patch('patcher_workflow.apply_session') as apply:
                patch_local('rom',build_only=True);apply.assert_not_called()

class KsuTests(unittest.TestCase):
    def test_live_binding_uses_runtime_not_stale_vendor_build_prop(self):
        from ksu_boot import target_bindings
        build=SimpleNamespace(source_info={'runtime_properties':{
            'ro.system.build.fingerprint':'system-current',
            'ro.vendor.build.fingerprint':'vendor-current','ro.board.platform':'sun'}},
            rom=SimpleNamespace(props=lambda:{'ro.vendor.build.fingerprint':'stale'}))
        self.assertEqual(target_bindings(build)['ro.vendor.build.fingerprint'],'vendor-current')

    def test_offline_module_does_not_claim_vendor_property_is_runtime(self):
        from ksu_boot import target_bindings
        build=SimpleNamespace(source_info={},rom=SimpleNamespace(props=lambda:{
            'ro.system.build.fingerprint':'system-current',
            'ro.vendor.build.fingerprint':'old-ossi','ro.board.platform':'sun'}))
        self.assertNotIn('ro.vendor.build.fingerprint',target_bindings(build))

    def test_early_runtime_no_system_service_restart(self):
        for name in ('gate.sh','codec.sh','commit.sh','recover.sh','preserve.sh','init.rc'):
            text=(ASSETS/'ksu/boot'/name).read_text(encoding='utf-8')
            self.assertNotIn('ctl.restart',text)
            self.assertNotIn('ctl.stop',text)
            self.assertNotIn('killall',text)
            self.assertNotIn('hash()',text)
        rc=(ASSETS/'ksu/boot/init.rc').read_text(encoding='utf-8')
        self.assertIn('on early-init',rc)
        self.assertIn('timeout_period 25',rc)
        self.assertLess(rc.index('exec_start mio-dolby-readiness'),rc.index('exec_start mio-dolby-commit'))
        code=(ASSETS/'ksu/boot/codec.sh').read_text(encoding='utf-8')
        self.assertLess(code.index('linker64 --list'),code.index('mount -o bind "$M/codec-manifest.xml"'))

    def test_android_mksh_hash_alias_is_not_used_as_function(self):
        text=(ASSETS/'ksu/service.sh').read_text(encoding='utf-8')
        self.assertNotIn('hash()',text)
        self.assertNotIn('$(hash ',text)
        self.assertIn('file_digest()',text)
        self.assertIn('cmp -s "$1" "$2"',text)

    def test_codec_service_can_recover_after_runtime_crash(self):
        from ksu_boot import validate_codec_recovery
        rc=(ASSETS/'ksu/boot/init.rc').read_text(encoding='utf-8')
        validate_codec_recovery(rc)
        codec=rc.split('service mio-dolby-codec ',1)[1].split('\n\n',1)[0]
        self.assertNotIn('oneshot',codec)
        self.assertIn('interface aidl android.hardware.media.c2.IComponentStore/default9',codec)
        self.assertIn('restart_period 3',codec)
        self.assertIn('    disabled',codec)  # preserve the pre-audio readiness gate

    def test_codec_recovery_rejects_broken_templates(self):
        from ksu_boot import validate_codec_recovery
        rc=(ASSETS/'ksu/boot/init.rc').read_text(encoding='utf-8')
        mapping='    interface aidl android.hardware.media.c2.IComponentStore/default9'
        for bad in (rc.replace(mapping,''),rc.replace(mapping,mapping+'\n    oneshot'),
                    rc.replace('    restart_period 3','    restart_period 0'),
                    rc.replace(mapping,mapping+'\n    critical'),
                    rc.replace(mapping,mapping+'\n    onrestart restart audioserver'),
                    rc.replace(mapping,mapping+'\n    reboot_on_failure reboot'),
                    rc+'\nservice mio-dolby-codec /bad\n    disabled\n',
                    rc.replace('service mio-dolby-codec ','service missing-codec ')):
            with self.subTest(rc=bad),self.assertRaises(PatchError):validate_codec_recovery(bad)

    def test_action_does_not_report_old_boot_as_current(self):
        text=(ASSETS/'ksu/action.sh').read_text(encoding='utf-8')
        self.assertIn('cmp -s "$MODDIR/.runtime/boot" /proc/sys/kernel/random/boot_id',text)
        self.assertIn('getprop init.svc.$name',text)
        self.assertNotIn('ctl.restart',text)
        self.assertNotIn('while ',text)

    def test_initrc_cache_guard_is_bounded_and_not_hot_reload(self):
        text=(ASSETS/'ksu/boot/initrc-cache.sh').read_text(encoding='utf-8')
        self.assertIn('timeout 8 "$KSUD" initrc refresh',text)
        self.assertIn('CACHE_REFRESHED_NEXT_BOOT_ONLY',text)
        self.assertIn('"$M/disable"',text)
        self.assertIn('"$M/remove"',text)
        self.assertIn('"$PENDING"',text)
        self.assertNotIn('while ',text)
        self.assertNotIn('ctl.',text)
        self.assertNotIn('setprop',text)
        self.assertEqual(text.count('"$KSUD" initrc refresh'),1)
        service=(ASSETS/'ksu/boot/service.sh').read_text(encoding='utf-8')
        self.assertEqual(service.count('"$M/initrc-cache.sh" repair'),1)
        action=(ASSETS/'ksu/action.sh').read_text(encoding='utf-8')
        self.assertIn('"$MODDIR/initrc-cache.sh" check',action)

    def test_metamodule_description_is_not_dolby_identity(self):
        text=(ASSETS/'ksu/customize.sh').read_text(encoding='utf-8')
        self.assertNotIn('grep -qi dolby "$prop"',text)
        self.assertIn("'^(id|name)=.*dolby'",text)

    def test_partition_mapping_and_destination_guard(self):
        from ksu_module import module_path,check_destination
        self.assertEqual(module_path('system/lib64/test.so'),'system/lib64/test.so')
        self.assertEqual(module_path('vendor/lib64/test.so'),'system/vendor/lib64/test.so')
        self.assertEqual(module_path('system_ext/priv-app/Test/Test.apk'),'system/system_ext/priv-app/Test/Test.apk')
        with self.assertRaises(PatchError):module_path('vendor/../unsafe')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(PatchError):check_destination(root/'inside.zip',root)
            with self.assertRaises(PatchError):check_destination(root/'not-a-zip.txt')

    def test_live_writeback_record_is_rejected_before_adb(self):
        from adb_mode import apply_remote
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);save_json(root/'adb-session.json',dict(source_kind='adb-live-readonly',writeback_allowed=False))
            with patch('adb_mode.Adb') as adb:
                with self.assertRaises(PatchError):apply_remote(root)
                adb.assert_not_called()

    def test_live_request_cannot_have_writeback_path(self):
        from ksu_module import generate_module
        with patch('adb_mode.Adb') as adb:
            with self.assertRaises(PatchError):generate_module('out.zip',root='/data/DNA/DNA_AB',serial='one',live=True)
            with self.assertRaises(PatchError):generate_module('out.zip',live=True)
            adb.assert_not_called()

    def test_cancel_save_does_not_read_device_or_build(self):
        from gui import App
        app=SimpleNamespace(target=lambda:('phone',None),mode=SimpleNamespace(get=lambda:'ADB 实时读取'),start=lambda fn:self.fail('must not start'))
        with patch('gui.filedialog.asksaveasfilename',return_value=''),patch('gui.generate_module') as build:
            App.module(app);build.assert_not_called()

    def test_runtime_has_no_hws_restart_or_early_audio_configuration(self):
        text=(ASSETS/'ksu/service.sh').read_text(encoding='utf-8')
        self.assertNotIn('ctl.restart hwservicemanager',text)
        self.assertNotIn('ctl.stop hwservicemanager',text)
        self.assertNotIn('killall',text)
        self.assertIn('setprop ctl.start hwservicemanager',text)
        self.assertLess(text.index('getprop sys.boot_completed'),text.index('mount -o bind'))
        self.assertIn('no polling remains',text)
        self.assertFalse((ASSETS/'ksu/post-fs-data.sh').exists())
        rc=(ASSETS/'ksu/init-services.rc').read_text(encoding='utf-8')
        self.assertEqual(rc.count('    disabled'),3)
        self.assertEqual(rc.count('    oneshot'),2)
        from ksu_boot import validate_codec_recovery
        validate_codec_recovery(rc)
        self.assertNotIn('critical',rc)

if __name__=='__main__':unittest.main(verbosity=2)
