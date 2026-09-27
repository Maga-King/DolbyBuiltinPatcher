"""Read-only inputs -> target-specific KernelSU module. Never installs a module."""
import copy
import json
import os
import re
import shlex
import shutil
import time
import uuid
import zipfile
from pathlib import Path
from core import ASSETS, VERSION, Build, PatchError, read, save_json, write, sha, xml_parse, xml_bytes
from patcher_workflow import history_root
from ksu_boot import export_boot, target_bindings, RUNTIME_VERSION, MODULE_README

MODULE_ID='mio_dolby_c17_generated'


def inspect_live(serial,log=lambda s:None):
    from adb_mode import Adb
    from core import inspect_rom
    folder=history_root()/'live-inspect'/('READ_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    folder.mkdir(parents=True)
    root,source=Adb(serial,log).snapshot_live(folder)
    _,info=inspect_rom(root,require_metadata=False)
    save_json(folder/'inspection.json',dict(source=source,rom_info=info,readonly=True))
    log('实时只读检查通过：'+info['model']+' / SDK '+info['sdk'])
    return folder


def module_path(canonical):
    part,tail=canonical.split('/',1)
    if part not in ('system','system_ext','vendor','product','odm') or '..' in canonical.split('/'):
        raise PatchError('非法模块路径：'+canonical)
    # ODM is not universally remapped by metamodules. Handle its existing files
    # with late bind mounts; DAX's duplicate vendor config supplies the fallback.
    return 'system/'+tail if part=='system' else 'system/'+part+'/'+tail


def check_destination(destination,source=None):
    target=Path(destination).resolve()
    if target.suffix.lower()!='.zip':raise PatchError('模块保存路径必须以 .zip 结尾')
    if source and target.is_relative_to(Path(source).resolve()):
        raise PatchError('模块 ZIP 请保存到输入 ROM 目录之外，避免被误打入镜像')
    return target


def device_manifest(build):
    """Use an existing device manifest as a late bind target, not a new fragment."""
    fragment=xml_parse(build.get('vendor/etc/vintf/manifest/dolby-native.xml').read_bytes())
    candidates=[build.rom.path('vendor/etc/vintf/manifest.xml')]
    candidates+=sorted((build.rom.parts['vendor']/'etc/vintf/manifest').glob('*.xml'))
    for path in candidates:
        if path.name=='dolby-native.xml' or not path.is_file():continue
        data=path.read_bytes()
        if data.startswith(b'!<symlink>'):continue
        root=xml_parse(data)
        if root.tag!='manifest' or root.get('type')!='device':continue
        for hal in fragment.findall('hal'):root.append(copy.deepcopy(hal))
        name='vendor/'+path.relative_to(build.rom.parts['vendor']).as_posix()
        return name,xml_bytes(root,data)
    raise PatchError('没有可用于延迟挂载的现有 vendor device manifest；停止生成，不替换整目录')


class ModuleBuild(Build):
    def __init__(self,root,output,log=lambda s:None,inventory=None,source_info=None):
        super().__init__(root,output,log,require_metadata=False)
        self.source_info=source_info or {'source_kind':'local-rom','rom_modified':False}
        if inventory is not None:self.library_inventory=inventory

    def run(self):
        try:
            self.log('KSU：只读输入；不写回 ROM，不安装模块')
            # A live snapshot can include an already active module. Do not turn
            # its overlay back into a supposed stock baseline or duplicate HALs.
            for part in ('vendor','odm'):
                for path in (self.rom.parts[part]/'etc/vintf').rglob('*.xml'):
                    data=path.read_bytes()
                    if data.startswith(b'!<symlink>'):continue
                    root=xml_parse(data)
                    if any(h.findtext('name') in ('vendor.dolby.dms','vendor.dolby.hardware.dms') for h in root.findall('hal')):
                        raise PatchError('输入中已存在 Dolby DMS 声明；请关闭现有杜比并重启后读取，或选择未内置杜比的 ROM')
            self.add_payload();self.merge_configs();self.compile_policy()
            self.export_module()
            return self.session
        except Exception as error:
            write(self.session/'FAILED.txt',str(error));raise

    def export_module(self):
        folder=self.session/'module';folder.mkdir()
        late=[];labels=[];mounted=[];excluded=[]
        def put(name,data,mode='0644',label='u:object_r:system_file:s0'):
            path=folder/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            labels.append((name,mode,label));return path
        def private(canonical,data,label,phase):
            if not self.rom.path(canonical).is_file():
                raise PatchError('延迟挂载目标在源 ROM 中不存在：'+canonical)
            name='late/'+canonical;put(name,data,label=label)
            late.append((phase,name,'/'+canonical,sha(self.rom.path(canonical))))
        effects=set(self.info['configuration']['effects']);codecs=set(self.info['configuration']['codecs'])
        native_rc=None
        for rel,row in sorted(self.changes.items()):
            name=row['canonical'];data=(self.tree/rel).read_bytes();label=row['label']
            if name=='system/etc/init/00-dolby-native.rc':
                native_rc=data;excluded.append(name);continue
            if '/etc/selinux/' in name:
                excluded.append(name);continue
            if name=='vendor/etc/vintf/manifest/dolby-native.xml':continue
            if name in effects or name in codecs:
                private(name,data,label,'audio');continue
            if '/etc/vintf/' in name:
                private(name,data,label,'vintf');continue
            if name.startswith('odm/'):
                if self.rom.path(name).is_file():private(name,data,label,'config')
                else:excluded.append(name)  # vendor/etc/dolby has the same DAX config.
                continue
            if 'libaudioeffecthal.qti.so' in name:raise PatchError('禁止将原厂音效 HAL 替换加入模块')
            out=module_path(name);path=put(out,data,row['mode'],label)
            mounted.append((out,'/'+name,sha(path)))
        name,data=device_manifest(self)
        private(name,data,'u:object_r:vendor_configs_file:s0','vintf')
        # export_boot installs and validates the required early init RC below.
        # Never stage the obsolete late-start/oneshot Codec2 template.
        if native_rc:put('solidify/00-dolby-native.rc',native_rc)
        for rel,row in sorted(self.changes.items()):
            if '/etc/vintf/' in row['canonical']:
                put('solidify/'+row['canonical'],(self.tree/rel).read_bytes(),label=row['label'])
        rules=read(self.session/'sepolicy.rule')
        put('sepolicy.rule',rules.encode())
        bindings=target_bindings(self)
        put('target.tsv',''.join(k+'\t'+v+'\n' for k,v in bindings.items() if v).encode())
        put('mounts.tsv',''.join('\t'.join(row)+'\n' for row in mounted).encode())
        put('late.tsv',''.join('\t'.join(row)+'\n' for row in late).encode())
        for filename in ('service.sh','customize.sh','action.sh'):
            put(filename,(ASSETS/'ksu'/filename).read_bytes(),'0755')
        boot_report=export_boot(self,folder,put,late,mounted,bindings,'/'+name)
        # Native domains already present in the source must have the service labels
        # before managers boot; overlaying contexts after their caches load is unsafe.
        requirements=[('vendor/etc/selinux/vendor_hwservice_contexts','vendor.dolby.hardware.dms::IDms','hal_dms_hwservice'),
                      ('vendor/etc/selinux/vendor_service_contexts','vendor.dolby.dms.IDms/default','hal_aidl_dms_service')]
        for filename,key,typename in requirements:
            text=read(self.rom.path(filename))
            if not any(line.split() and line.split()[0]==key and line.split()[-1]=='u:object_r:'+typename+':s0' for line in text.splitlines()):
                raise PatchError('模块无法安全晚加载服务标签，需先原生适配：'+filename+' '+key)
        write(folder/'labels.tsv',''.join('\t'.join(row)+'\n' for row in labels))
        write(folder/'module.prop',f'id={MODULE_ID}\nname=杜比全景+解码器\nversion={RUNTIME_VERSION}\nversionCode=603\nauthor=科比\ndescription=建议KSU+MOUNTIFY\n')
        write(folder/'README.txt',MODULE_README)
        report=dict(version=VERSION,kind='ksu-module',applied=False,install_performed=False,rom_modified=False,
                    source=self.source_info,rom_info=self.info,module_mounts=mounted,late_mounts=late,
                    excluded_from_mount=excluded,boot_tested=False,limitations=['target-specific','metamodule required','bounded HIDL startup may fail safely'])
        report['boot_runtime']=boot_report
        save_json(self.session/'module-report.json',report)
        put('module-report.json',(self.session/'module-report.json').read_bytes())
        output=self.session/'Dolby_C17_KSU.zip'
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED,strict_timestamps=False) as archive:
            for path in sorted(folder.rglob('*')):
                if path.is_file():archive.write(path,path.relative_to(folder).as_posix())
        with zipfile.ZipFile(output) as archive:
            if archive.testzip():raise PatchError('模块 ZIP 损坏')
        self.log('已生成 KSU 模块；尚未安装或做目标机开机验证：'+str(output))


def generate_module(destination,root=None,serial=None,live=False,log=lambda s:None,output=None):
    if live and (not serial or root):raise PatchError('实时模式必须指定设备，且不能指定 ROM 写回路径')
    if not live and not root:raise PatchError('请选择 ROM 解包目录')
    target=check_destination(destination,None if serial else root)
    base=Path(output) if output else history_root()/'ksu'
    job=base/('KSU_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]);job.mkdir(parents=True)
    info={'source_kind':'local-rom'};inventory=None
    if serial:
        from adb_mode import Adb
        adb=Adb(serial,log)
        local,info=adb.snapshot_live(job) if live else adb.snapshot(root,job)
        if live:
            info['runtime_properties']={key:adb.shell('getprop '+key).decode().strip()
                                       for key in ('ro.system.build.fingerprint','ro.vendor.build.fingerprint','ro.board.platform')}
        inventory=info['libraries'];root=local
    session=ModuleBuild(root,job/'build',log,inventory,info).run()
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name(target.name+'.tmp-'+uuid.uuid4().hex[:8])
    try:
        shutil.copy2(session/'Dolby_C17_KSU.zip',temporary)
        with zipfile.ZipFile(temporary) as z:
            if z.testzip():raise PatchError('保存模块时 ZIP 校验失败')
        os.replace(temporary,target)
    finally:
        if temporary.exists():temporary.unlink()
    save_json(session/'saved-module.json',dict(path=str(target),installed=False))
    log('模块已保存：'+str(target))
    return session
