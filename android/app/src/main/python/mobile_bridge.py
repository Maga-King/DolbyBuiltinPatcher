"""Android transport for shared module builder and extracted-ROM transactions."""
import json
import os
from pathlib import Path
import sys
import time
import uuid
import re
import shlex
import shutil
from pathlib import PurePosixPath


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


def setup(runtime_dir, work_dir, bridge):
    runtime=Path(str(runtime_dir))
    work=Path(str(work_dir))
    # Configure all shared modules before their first import (no production edits).
    sys._MEIPASS=str(runtime)
    os.environ['LOCALAPPDATA']=str(work)
    from core import PatchError
    from adb_mode import Adb

    def log(message):
        if bridge.isCancelled():raise PatchError('用户取消了本次任务')
        bridge.log(str(message))

    class LocalRoot(Adb):
        def __init__(self):
            self.serial='local-root'
            self.log=log
            self.device={'serial':'local-root','model':str(bridge.model()),'state':'local'}
            if self.shell('id -u').strip()!=b'0':raise PatchError('需要 root 授权')

        def shell(self,script,timeout=120,output=None):
            if bridge.isCancelled():raise PatchError('用户取消了本次任务')
            command='set -eu\n'+script+'\nexit 0\n'
            if output is not None:
                output.flush()
                bridge.execToFile(command,int(timeout),str(Path(output.name).resolve()))
                return b''
            return str(bridge.exec(command,int(timeout))).encode('utf-8')

        def push(self,source,destination):
            source=Path(source).resolve()
            if not source.is_relative_to(work.resolve()):raise PatchError('上传文件不在本应用任务目录内')
            if not re.fullmatch(r'/data/local/tmp/dolby-upload-[0-9a-f]{32}\.tar',destination):
                raise PatchError('拒绝非事务上传路径')
            q=shlex.quote
            self.shell(f'test ! -e {q(destination)}\ntest ! -L {q(destination)}\n'
                       f'umask 077\nset -C\ncat {q(str(source))} > {q(destination)}',timeout=600)

        def validate_root(self,value):
            root=super().validate_root(value)
            forbidden=('/data/adb','/data/user','/data/user_de','/data/data','/data/system',
                       '/data/vendor','/data/misc','/mnt/vendor','/mnt/system')
            if any(root==p or root.startswith(p+'/') for p in forbidden):
                raise PatchError('请选择独立 ROM 解包目录，不能选择系统运行数据目录')
            return root

    work.mkdir(parents=True,exist_ok=True)
    return runtime,work,LocalRoot(),log


def generate(runtime_dir, work_dir, bridge, rom_path=None):
    runtime,work,reader,log=setup(runtime_dir,work_dir,bridge)
    from core import PatchError, save_json
    from ksu_module import ModuleBuild

    payload=runtime/'assets/payload.zip'
    if not payload.is_file():raise PatchError('本 APK 未包含杜比资产，请使用已配套资产的本地构建。公开源码不附带专有库。')
    job=work/('Mobile_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    job.mkdir(parents=True)
    if rom_path is None:
        log('只读取当前系统；不刷模块、不写回分区，不需要策略编译器。')
        root,info=reader.snapshot_live(job)
        info.update(source_kind='android-root-live-readonly',writeback_allowed=False)
    else:
        log('只读手机解包 ROM 生成模块；不会修改所填目录，不需要策略编译器。')
        root,info=reader.snapshot(str(rom_path).strip(),job)
        info.update(source_kind='android-extracted-rom-readonly',writeback_allowed=False)
    save_json(job/'snapshot.json',info)
    if bridge.isCancelled():raise PatchError('用户取消了本次生成')
    log('警告：应要求不按 SDK、机型或设备指纹限制生成；不保证兼容，刷入后果自负。')
    session=ModuleBuild(root,job/'build',log,info['libraries'],info,enforce_sdk=False).run()
    result=session/'Dolby_C17_KSU.zip'
    log('模块已生成。请选择保存位置，再自行交给 KSU 管理器安装。')
    return json.dumps({'zip':str(result),'session':str(session),'installed':False},ensure_ascii=False)


def rom_sessions(work):
    """Records live outside the selected ROM. Never accept arbitrary session paths."""
    from core import read
    records=[]
    for path in work.glob('ROM_*/build/Dolby_*/adb-session.json'):
        if path.is_symlink() or not path.resolve().is_relative_to(work.resolve()):
            raise ValueError('任务记录路径异常')
        records.append((path.parent,json.loads(read(path))))
    return sorted(records,key=lambda row:row[0].stat().st_mtime,reverse=True)


def rom_operation(runtime_dir,work_dir,bridge,rom_path,operation):
    runtime,work,reader,log=setup(runtime_dir,work_dir,bridge)
    from core import Build, PatchError, read, safe, save_json, sha
    from adb_mode import apply_remote, monitor_remote
    if operation not in ('patch','status','restore'):raise PatchError('未知 ROM 操作')
    root=reader.validate_root(str(rom_path).strip())
    records=rom_sessions(work)
    matching=[row for row in records if row[1].get('root')==root]
    pending=('prepared','running','recovery-required')
    if operation=='patch':
        for session,info in records:
            if info.get('state') in pending:
                raise PatchError('还有未解决的事务，请先输入该目录并查询状态：'+info['root'])
        if matching and json.loads(read(matching[0][0]/'report.json')).get('applied'):
            raise PatchError('本应用已修改过该目录；请先回退上次修改，或选全新解包目录。')
        compiler=Path(str(bridge.nativeCompiler()))
        if not compiler.is_file():raise PatchError('本 APK 缺少 ARM64 secilc，请使用完整构建；未修改 ROM')
        if not (runtime/'assets/payload.zip').is_file():raise PatchError('本 APK 缺少配套资产；未修改 ROM')
        job=work/('ROM_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
        job.mkdir()
        log('只修改所填解包目录，不写正在运行的分区、不刷机、不重启。')
        local,info=reader.snapshot(root,job)
        builder=Build(local,job/'build',log)
        builder.policy_compiler=compiler
        builder.library_inventory=info['libraries']
        session=builder.run()
        guards=[dict(path=name,kind='L' if name in info['symlinks'] else 'F',
                     expected=info['symlinks'].get(name) if name in info['symlinks'] else sha(safe(local,name)))
                for name in info['files']]
        save_json(session/'adb-session.json',dict(serial=reader.serial,root=root,state='built',
            device=info['device'],input_guards=guards,source_kind='android-extracted-rom',writeback_allowed=True))
    else:
        if not matching:raise PatchError('本应用没有该目录的修改记录。卸载应用会丢失私有记录，手机外部备份仍保留。')
        session,info=matching[0]
        if operation=='status':
            log('记录：'+str(session)+'\n目标：'+root+'\n状态：'+info.get('state','未知'))
            if info.get('job'):
                log('手机备份：'+info['job'])
                monitor_remote(session,reader,log)
            else:log('尚未启动写入，ROM 未由此任务修改。')
            return json.dumps({'session':str(session),'operation':operation},ensure_ascii=False)
    # Cancellation before writing is safe. Once started, keep the one-shot
    # transaction intact; process death can be reconciled using status next time.
    if bridge.isCancelled():raise PatchError('已取消，尚未写回 ROM')
    bridge.writing(True)
    try:
        apply_remote(session,restore=operation=='restore',log=log,transport=reader)
    finally:
        bridge.writing(False)
    log('记录：'+str(session)+'\n请保留 ROM 同级 .dolby-patcher-backups；不要在确认打包前卸载本应用。')
    return json.dumps({'session':str(session),'operation':operation},ensure_ascii=False)


def remove_private(work,target):
    """No broad path, symlink, or escape may reach recursive deletion."""
    from core import PatchError
    boundary=work.resolve()
    if target.is_symlink() or target.resolve()==boundary or not target.resolve().is_relative_to(boundary):
        raise PatchError('拒绝异常清理路径：'+str(target))
    if not target.exists():return
    for parent in target.parents:
        if parent==work:break
        if parent.is_symlink():raise PatchError('清理路径含符号链接：'+str(parent))
    if target.is_dir():shutil.rmtree(target)
    else:target.unlink()


def cleanup(runtime_dir,work_dir,bridge,rom_path,kind):
    runtime,work,reader,log=setup(runtime_dir,work_dir,bridge)
    from core import PatchError
    if kind not in ('cache','backups'):raise PatchError('未知清理操作')
    records=rom_sessions(work)
    for _,info in records:
        if info.get('state') not in ('built','complete','rolled-back','failed-preflight'):
            raise PatchError('有未完成或状态不明的事务，暂不清理。先查询：'+info.get('root','未知目录'))
    if kind=='cache':
        targets=[]
        for job in work.iterdir():
            if not job.name.startswith(('ROM_','Mobile_')) or not job.is_dir():continue
            targets.extend(job/name for name in ('rom','snapshot.tar','snapshot.tgz','snapshot.tgz.base64')
                           if (job/name).exists())
            if job.name.startswith('Mobile_'):
                for session in (job/'build').glob('Dolby_*'):
                    if (session/'Dolby_C17_KSU.zip').is_file():
                        targets.extend(session/name for name in ('module','patch_tree') if (session/name).exists())
        for target in targets:
            if bridge.isCancelled():raise PatchError('已停止清理；未清理的文件保留')
            remove_private(work,target)
        log(f'已清理 {len(targets)} 处读取/构建缓存；生成 ZIP、ROM 备份和回退记录均保留。')
        return json.dumps({'cleaned':len(targets),'kind':kind})

    root=reader.validate_root(str(rom_path).strip())
    matching=[row for row in records if row[1].get('root')==root]
    if not matching:
        log('此目录没有本应用的备份记录；不会扫描或删除其他工具的文件。')
        return json.dumps({'cleaned':0,'kind':kind})
    # Derive a narrow allowlist from this app's completed records, not a glob
    # over .dolby-patcher-backups (which may contain unrelated desktop backups).
    prefix=str(PurePosixPath(root).parent)+'/.dolby-patcher-backups/'+PurePosixPath(root).name+'-'
    jobs=[]
    for session,info in matching:
        for row in [info,*info.get('previous_jobs',[])]:
            job=row.get('job')
            if not job:continue
            if not job.startswith(prefix) or not re.fullmatch('[0-9a-f]{32}',job[len(prefix):]):
                raise PatchError('备份记录路径异常，拒绝删除：'+job)
            jobs.append(job)
    jobs=list(dict.fromkeys(jobs));q=shlex.quote
    for job in jobs:
        reader.shell(f'if [ -e {q(job)} ] || [ -L {q(job)} ]; then\n'
            f'test ! -L {q(job)}\ntest "$(readlink -f {q(job)})" = {q(job)}\n'
            f'test "$(cat {q(job+"/root.txt")})" = {q(root)}\n'
            f'case "$(cat {q(job+"/status")})" in complete|rolled-back|failed-preflight) ;; *) exit 1;; esac\nfi')
    if bridge.isCancelled():raise PatchError('已取消删除备份')
    bridge.writing(True)
    try:
        for job in jobs:
            # Recheck identity immediately before deletion; never delete the
            # backup parent, user ROM or other sessions based on a wildcard.
            reader.shell(f'if [ -e {q(job)} ] || [ -L {q(job)} ]; then\n'
                f'test ! -L {q(job)}\ntest "$(readlink -f {q(job)})" = {q(job)}\n'
                f'test "$(cat {q(job+"/root.txt")})" = {q(root)}\n'
                f'case "$(cat {q(job+"/status")})" in complete|rolled-back|failed-preflight) ;; *) exit 1;; esac\n'
                f'rm -rf -- {q(job)}\nfi',timeout=120)
        for session,_ in matching:remove_private(work,session.parent.parent)
    finally:bridge.writing(False)
    log(f'已删除此 ROM 的 {len(jobs)} 份事务备份及 {len(matching)} 份构建记录；未修改 ROM。此操作不可恢复。')
    return json.dumps({'cleaned':len(jobs),'kind':kind})
