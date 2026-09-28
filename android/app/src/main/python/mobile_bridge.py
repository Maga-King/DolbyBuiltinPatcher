"""Android frontend adapter: root READ ONLY, same ModuleBuild, no ADB or compiler."""
import json
import os
from pathlib import Path
import sys
import time
import uuid


def check_environment(runtime_dir):
    runtime=Path(str(runtime_dir))
    sys._MEIPASS=str(runtime)
    from ksu_boot import validate_codec_recovery
    import ksu_policy
    import ksu_module
    import elftools
    assets=runtime/'assets'
    validate_codec_recovery((assets/'ksu/boot/init.rc').read_text(encoding='utf-8'))
    if not (assets/'payload.zip').is_file():
        return 'Python / 生成器 / RC 恢复模板可用；本构建缺少私有杜比资产，不能生成完整模块。'
    import zipfile
    manifest=json.loads((assets/'payload.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(assets/'payload.zip') as archive:
        missing={row['canonical'] for row in manifest}-set(archive.namelist())
        if missing:raise ValueError('资产清单缺件：'+', '.join(sorted(missing)[:4]))
    return f'Python / 共享生成器 / RC 模板可用，资产清单 {len(manifest)} 项齐全。未生成、未安装模块。'


def generate(runtime_dir, work_dir, bridge):
    runtime=Path(str(runtime_dir))
    work=Path(str(work_dir))
    # Configure all shared modules before their first import (no production edits).
    sys._MEIPASS=str(runtime)
    os.environ['LOCALAPPDATA']=str(work)
    from core import PatchError, save_json
    from adb_mode import Adb
    from ksu_module import ModuleBuild

    def log(message):
        if bridge.isCancelled():raise PatchError('用户取消了本次生成')
        bridge.log(str(message))

    class LocalRoot(Adb):
        def __init__(self):
            self.serial='local-root'
            self.log=log
            self.device={'serial':'local-root','model':str(bridge.model()),'state':'local'}
            if self.shell('id -u').strip()!=b'0':raise PatchError('需要 root 授权')

        def shell(self,script,timeout=120,output=None):
            if bridge.isCancelled():raise PatchError('用户取消了本次生成')
            command='set -eu\n'+script+'\nexit 0\n'
            if output is not None:
                output.flush()
                bridge.execToFile(command,int(timeout),str(Path(output.name).resolve()))
                return b''
            return str(bridge.exec(command,int(timeout))).encode('utf-8')

    payload=runtime/'assets/payload.zip'
    if not payload.is_file():raise PatchError('本 APK 未包含杜比资产，请使用已配套资产的本地构建。公开源码不附带专有库。')
    job=work/('Mobile_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    job.mkdir(parents=True)
    log('只读取当前系统；不刷模块、不写回分区，不需要策略编译器。')
    reader=LocalRoot()
    root,info=reader.snapshot_live(job)
    info.update(source_kind='android-root-live-readonly',writeback_allowed=False)
    save_json(job/'snapshot.json',info)
    if bridge.isCancelled():raise PatchError('用户取消了本次生成')
    session=ModuleBuild(root,job/'build',log,info['libraries'],info).run()
    result=session/'Dolby_C17_KSU.zip'
    log('模块已生成。请选择保存位置，再自行交给 KSU 管理器安装。')
    return json.dumps({'zip':str(result),'session':str(session),'installed':False},ensure_ascii=False)
