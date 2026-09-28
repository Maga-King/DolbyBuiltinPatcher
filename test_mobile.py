"""Host tests for the Android adapter without touching a phone or user ROM."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core import PatchError, save_json

spec=importlib.util.spec_from_file_location('mobile_bridge',Path(__file__).parent/'android/app/src/main/python/mobile_bridge.py')
mobile=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mobile)


class MobileTests(unittest.TestCase):
    def test_frozen_console_failure_never_aborts_build(self):
        from app import console_log
        for error in (OSError(22,'Invalid argument'),ValueError('closed')):
            stream=Mock()
            stream.write.side_effect=error
            with patch('app.sys.stdout',stream):console_log('日志')

    def test_module_manifest_selection_is_platform_independent(self):
        from ksu_module import device_manifest
        from types import SimpleNamespace
        vendor=self.work/'vendor'
        manifests=vendor/'etc/vintf/manifest';manifests.mkdir(parents=True)
        for name in ('Ims.xml','android.xml'):
            (manifests/name).write_text('<manifest type="device" version="1.0"/>')
        fragment=self.work/'dolby.xml'
        fragment.write_text('<manifest type="device" version="1.0"><hal><name>vendor.dolby.dms</name></hal></manifest>')
        build=SimpleNamespace(get=lambda n:fragment,rom=SimpleNamespace(parts={'vendor':vendor},path=lambda n:self.work/n))
        name,_=device_manifest(build)
        self.assertEqual(name,'vendor/etc/vintf/manifest/android.xml')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work=Path(self.temp.name)
        self.reader=Mock(serial='local-root')
        self.reader.validate_root.return_value='/data/DNA/DNA_01'
        self.bridge=Mock()
        self.bridge.isCancelled.return_value=False
        self.log=Mock()
        self.setup=patch.object(mobile,'setup',return_value=(self.work,self.work,self.reader,self.log))
        self.setup.start();self.addCleanup(self.setup.stop)

    def record(self,state='complete',applied=True):
        session=self.work/'ROM_test/build/Dolby_test'
        save_json(session/'adb-session.json',dict(root='/data/DNA/DNA_01',state=state,serial='local-root',job='/data/DNA/.dolby-patcher-backups/test'))
        save_json(session/'report.json',dict(applied=applied))
        return session

    def test_status_uses_local_transport_never_adb_constructor(self):
        session=self.record()
        with patch('adb_mode.monitor_remote') as monitor,patch('adb_mode.Adb') as adb:
            result=json.loads(mobile.rom_operation('runtime',str(self.work),self.bridge,'/data/DNA/DNA_01','status'))
            monitor.assert_called_once_with(session,self.reader,self.log)
            adb.assert_not_called()
            self.assertEqual(result['operation'],'status')

    def test_module_from_rom_is_readonly_and_never_uses_live_snapshot(self):
        (self.work/'assets').mkdir()
        (self.work/'assets/payload.zip').touch()
        info=dict(libraries={},root='/data/DNA/DNA_01')
        self.reader.snapshot.return_value=(self.work/'snapshot',info)
        with patch('ksu_module.ModuleBuild') as builder:
            builder.return_value.run.return_value=self.work/'session'
            result=json.loads(mobile.generate('runtime',str(self.work),self.bridge,'/data/DNA/DNA_01'))
            self.reader.snapshot.assert_called_once()
            self.reader.snapshot_live.assert_not_called()
            self.assertFalse(info['writeback_allowed'])
            self.assertFalse(result['installed'])
            self.assertFalse(builder.call_args.kwargs['enforce_sdk'])
            self.bridge.writing.assert_not_called()

    def test_module_live_does_not_use_rom_path(self):
        (self.work/'assets').mkdir()
        (self.work/'assets/payload.zip').touch()
        self.reader.snapshot_live.return_value=(self.work/'snapshot',dict(libraries={}))
        with patch('ksu_module.ModuleBuild') as builder:
            builder.return_value.run.return_value=self.work/'session'
            mobile.generate('runtime',str(self.work),self.bridge)
            self.reader.snapshot.assert_not_called()
            self.reader.snapshot_live.assert_called_once()

    def test_restore_brackets_write_and_passes_transport(self):
        session=self.record()
        with patch('adb_mode.apply_remote') as apply:
            mobile.rom_operation('runtime',str(self.work),self.bridge,'/data/DNA/DNA_01','restore')
            apply.assert_called_once_with(session,restore=True,log=self.log,transport=self.reader)
            self.assertEqual([c.args for c in self.bridge.writing.call_args_list],[(True,),(False,)])

    def test_pending_transaction_blocks_new_build(self):
        self.record('running',False)
        with patch('core.Build') as build:
            with self.assertRaisesRegex(PatchError,'未解决'):
                mobile.rom_operation('runtime',str(self.work),self.bridge,'/data/DNA/DNA_01','patch')
            build.assert_not_called()

    def test_duplicate_patch_rejected(self):
        self.record()
        with self.assertRaisesRegex(PatchError,'已修改过'):
            mobile.rom_operation('runtime',str(self.work),self.bridge,'/data/DNA/DNA_01','patch')

    def test_cancel_before_restore_never_starts_transaction(self):
        self.record();self.bridge.isCancelled.return_value=True
        with patch('adb_mode.apply_remote') as apply:
            with self.assertRaisesRegex(PatchError,'已取消'):
                mobile.rom_operation('runtime',str(self.work),self.bridge,'/data/DNA/DNA_01','restore')
            apply.assert_not_called()

    def test_write_exception_reenables_cancellation(self):
        self.record()
        with patch('adb_mode.apply_remote',side_effect=PatchError('test')):
            with self.assertRaises(PatchError):
                mobile.rom_operation('runtime',str(self.work),self.bridge,'/data/DNA/DNA_01','restore')
            self.assertEqual(self.bridge.writing.call_args_list[-1].args,(False,))

    def test_missing_record_never_writes(self):
        with patch('adb_mode.apply_remote') as apply:
            with self.assertRaisesRegex(PatchError,'没有该目录'):
                mobile.rom_operation('runtime',str(self.work),self.bridge,'/data/DNA/DNA_01','restore')
            apply.assert_not_called()

    def test_transport_device_mismatch_is_rejected(self):
        from adb_mode import apply_remote
        session=self.record('built',False)
        with self.assertRaisesRegex(PatchError,'序列号'):
            apply_remote(session,transport=Mock(serial='not-local'))

    def test_posix_compiler_errors_not_crashes(self):
        from policy import semantic_failure
        with patch('policy.os.name','posix'):
            self.assertTrue(semantic_failure(255,'Failed to resolve type'))
            self.assertFalse(semantic_failure(-11,'Failed to resolve type'))
            self.assertFalse(semantic_failure(255,'Failed to compile: out of memory'))
        with patch('policy.os.name','nt'):
            self.assertFalse(semantic_failure(255,'Failed to resolve type'))

    def test_cache_keeps_zip_backups_and_records(self):
        session=self.record()
        (session/'original_files').mkdir()
        (session/'original_files/old').write_text('backup')
        job=session.parent.parent
        (job/'rom').mkdir();(job/'rom/input').write_text('cache')
        module=self.work/'Mobile_test/build/Dolby_test'
        (module/'module').mkdir(parents=True)
        (module/'module/temp').write_text('cache')
        (module/'Dolby_C17_KSU.zip').write_bytes(b'zip')
        mobile.cleanup('runtime',str(self.work),self.bridge,'','cache')
        self.assertFalse((job/'rom').exists())
        self.assertFalse((module/'module').exists())
        self.assertTrue((module/'Dolby_C17_KSU.zip').exists())
        self.assertTrue((session/'original_files/old').exists())
        self.assertTrue((session/'adb-session.json').exists())
        self.reader.shell.assert_not_called()

    def test_pending_blocks_cache_and_backup_delete(self):
        self.record('running',False)
        for kind in ('cache','backups'):
            with self.assertRaisesRegex(PatchError,'未完成'):
                mobile.cleanup('runtime',str(self.work),self.bridge,'/data/DNA/DNA_01',kind)
        self.reader.shell.assert_not_called()

    def test_backup_delete_rejects_forged_path(self):
        self.record()
        with self.assertRaisesRegex(PatchError,'路径异常'):
            mobile.cleanup('runtime',str(self.work),self.bridge,'/data/DNA/DNA_01','backups')
        self.reader.shell.assert_not_called()

    def test_backup_delete_only_recorded_uuid_jobs(self):
        session=self.record()
        target='/data/DNA/.dolby-patcher-backups/DNA_01-'+'a'*32
        save_json(session/'adb-session.json',dict(root='/data/DNA/DNA_01',state='complete',job=target))
        unrelated=self.work/'unrelated';unrelated.write_text('keep')
        result=json.loads(mobile.cleanup('runtime',str(self.work),self.bridge,'/data/DNA/DNA_01','backups'))
        self.assertEqual(result['cleaned'],1)
        self.assertFalse(session.exists())
        self.assertTrue(unrelated.exists())
        script=self.reader.shell.call_args_list[-1].args[0]
        self.assertIn('rm -rf -- '+target,script)
        self.assertIn('readlink -f',script)
        self.assertNotIn('rm -rf -- /data/DNA/DNA_01',script)

    def test_private_delete_rejects_boundary_and_outside(self):
        for target in (self.work,self.work.parent):
            with self.assertRaises(PatchError):mobile.remove_private(self.work,target)


if __name__=='__main__':unittest.main()
