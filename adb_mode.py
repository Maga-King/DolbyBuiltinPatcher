"""Explicit-device ADB transport for extracted ROMs, never live system partitions."""
import io
import base64
import gzip
import json
import re
import shlex
import shutil
import subprocess
import tarfile
import time
import uuid
from pathlib import Path, PurePosixPath
from core import ASSETS, Build, PatchError, inspect_rom, read, safe, save_json, sha, write
from patcher_workflow import history_root


def adb_path():
    bundled=ASSETS/'adb/adb.exe'
    found=str(bundled) if bundled.is_file() else shutil.which('adb')
    if not found:raise PatchError('找不到 adb；请保留完整工具目录或安装 Android Platform Tools')
    return found


def execute(args,**kwargs):
    return subprocess.run(args,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),**kwargs)


def devices():
    process=execute([adb_path(),'devices','-l'],capture_output=True,timeout=20)
    if process.returncode:raise PatchError(process.stderr.decode(errors='replace'))
    rows=[]
    for line in process.stdout.decode('utf-8',errors='replace').splitlines():
        fields=line.split()
        if len(fields)<2 or fields[0] in ('List','*'):continue
        info=dict(f.split(':',1) for f in fields[2:] if ':' in f)
        rows.append(dict(serial=fields[0],state=fields[1],model=info.get('model','未知机型')))
    return rows


def remote_root(value):
    if not value or any(ord(c)<32 for c in value) or '\\' in value:
        raise PatchError('请输入手机内的绝对解包目录，不得包含控制字符或反斜杠')
    path=PurePosixPath(value)
    minimum=3 if len(path.parts)>1 and path.parts[1]=='sdcard' else 4
    if not path.is_absolute() or '..' in path.parts or len(path.parts)<minimum:
        raise PatchError('不能选择分区根目录或使用 ..；请输入完整解包目录，例如 /data/DNA/DNA_AB')
    if path.parts[1] not in ('data','sdcard','storage','mnt'):
        raise PatchError('ADB 只处理数据目录中的解包 ROM，拒绝 /system、/vendor 等正在运行的分区')
    if str(path) in ('/data/local/tmp','/storage/emulated/0','/data/adb/modules'):
        raise PatchError('目标范围过宽，请选择具体 ROM 解包目录')
    return str(path)


def relative_path(value):
    # Windows-side cache must represent the Android path without interpretation.
    if any(ord(c)<32 for c in value) or any(c in value for c in ':\\*?"<>|'):
        raise PatchError('解包文件名无法安全映射到 Windows：'+repr(value))
    p=PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or not p.parts or value.startswith('-'):
        raise PatchError('非法解包文件路径：'+repr(value))
    for component in p.parts:
        if component.endswith((' ','.')) or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?',component):
            raise PatchError('文件名在 Windows 下会产生歧义：'+repr(value))
    return p.as_posix()


class Adb:
    def __init__(self,serial,log=lambda s:None):
        if not serial or re.search(r'\s',serial):raise PatchError('必须手动选择一个有效设备序列号')
        self.serial=serial;self.log=log;self.root_command='sh -s'
        matches=[d for d in devices() if d['serial']==serial and d['state']=='device']
        if len(matches)!=1:raise PatchError('所选设备未连接或未授权：'+serial)
        self.device=matches[0]
        if self.shell('id -u').strip()!=b'0':
            self.root_command="su -c 'sh -s'"
            if self.shell('id -u').strip()!=b'0':raise PatchError('ADB 模式需要 root adbd 或已授权的 su，未尝试重启 adbd')

    def shell(self,script,timeout=120,output=None):
        # Entire script goes through stdin; selected serial is present on every command.
        # Shell-v2 preserves exit status and script stdin. Binary downloads use base64
        # framing separately: patched adbd builds can still translate LF even with -T.
        args=[adb_path(),'-s',self.serial,'shell','-T',self.root_command]
        result=execute(args,input=('set -eu\n'+script+'\nexit 0\n').encode(),
                       stdout=output if output else subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
        if result.returncode:raise PatchError('ADB 操作失败：'+result.stderr.decode('utf-8',errors='replace')[-2200:])
        return result.stdout or b''

    def validate_root(self,value):
        requested=remote_root(value)
        actual=self.shell('readlink -f '+shlex.quote(requested)).decode().strip()
        root=remote_root(actual)
        self.shell('test -d '+shlex.quote(root+'/config')+'\ntest ! -L '+shlex.quote(root+'/config'))
        return root

    def layout(self,root):
        result={}
        for part in ('system','system_ext','vendor','odm','product'):
            candidates=([f'system/system',f'system_a/system'] if part=='system' else [])
            candidates += [part,part+'_a',f'system/system/{part}',f'system/{part}']
            script='cd '+shlex.quote(root)+'\n'
            for p in candidates:
                script+=f'if [ -d {shlex.quote(p+"/etc")} ] && [ ! -L {shlex.quote(p)} ]; then printf "%s\\n" {shlex.quote(p)}; exit 0; fi\n'
            script+='exit 1'
            result[part]=relative_path(self.shell(script).decode().strip())
        return result

    def snapshot(self,path,logdir):
        return self._snapshot(path,logdir,live=False)

    def snapshot_live(self,logdir):
        """Fixed read-only partition allowlist. No remote path or write-back record."""
        return self._snapshot('/',logdir,live=True)

    def _snapshot(self,path,logdir,live=False):
        if live:
            root='/';layout={p:p for p in ('system','system_ext','vendor','odm','product')}
            self.shell('\n'.join('test -d /'+p+'/etc' for p in layout))
        else:
            root=self.validate_root(path);layout=self.layout(root)
        self.log('所选设备：'+self.serial+' / '+self.device['model'])
        self.log('只读分析当前系统分区（不读取 /data，不可写回）' if live else '只读分析手机解包目录：'+root)
        prefixes=list(dict.fromkeys([*layout.values(),*([] if live else ['config'])]))
        command='cd '+shlex.quote(root)+'\nfind '+('-H ' if live else '')+' '.join(map(shlex.quote,prefixes))
        regular=self.shell(command+' -type f -print0').decode('utf-8').split('\0')
        links=self.shell(command+' -type l -print0').decode('utf-8').split('\0')
        all_paths=set(filter(None,regular+links));selected=set();libraries={}
        embedded=json.loads(read(ASSETS/'payload.json'))
        existing_payload={layout[r['canonical'].split('/')[0]]+'/'+r['canonical'].split('/',1)[1] for r in embedded}
        for name in sorted(all_paths):
            if name.startswith('config/'):
                selected.add(name);continue
            for part,prefix in layout.items():
                if not name.startswith(prefix+'/'):continue
                rel=name[len(prefix)+1:]
                if (rel.startswith('lib64/') or rel.startswith('apex/')) and name.endswith('.so'):
                    libraries.setdefault(PurePosixPath(name).name,[]).append(name)
                if (rel.startswith(('etc/selinux/','etc/vintf/','etc/init/')) or
                    rel in ('build.prop','etc/build.prop','bin/hwservicemanager',
                            'lib64/hw/libaudioeffecthal.qti.so','lib64/libaudioeffecthal.qti.so') or
                    (part in ('vendor','odm') and rel.startswith('etc/') and name.endswith('.xml')) or
                    name in existing_payload):selected.add(name)
        selected=sorted(relative_path(n) for n in selected)
        if not selected:raise PatchError('手机目录中没有可用配置文件')
        if len({n.casefold() for n in selected})!=len(selected):
            raise PatchError('所选 ROM 存在仅大小写不同的输入路径，无法安全缓存到 Windows')
        save_json(logdir/'snapshot-plan.json',dict(root=root,layout=layout,files=selected,libraries=libraries))
        local=logdir/'rom';local.mkdir(parents=True,exist_ok=False)
        for prefix in layout.values():(local/prefix/'etc').mkdir(parents=True,exist_ok=True)
        # Preserve whether the init directory actually exists; never fake required input.
        self.shell('test -d '+shlex.quote(root.rstrip('/')+'/'+layout['system']+'/etc/init'))
        (local/layout['system']/'etc/init').mkdir(parents=True,exist_ok=True)
        archive=logdir/'snapshot.tar'
        encoded=logdir/'snapshot.tgz.base64';compressed=logdir/'snapshot.tgz'
        self.log(f'读取 {len(selected)} 个配置/策略/相关文件；其他库仅读取文件名清单，不下载整包 ROM')
        script='cd '+shlex.quote(root)+"\nprintf '%s\\n' "+' '.join(map(shlex.quote,selected))+" | tar -czf - -T - | base64"
        with encoded.open('wb') as out:self.shell(script,timeout=600,output=out)
        with encoded.open('rb') as src,compressed.open('wb') as dst:
            for line in src:
                if line.strip():dst.write(base64.b64decode(line.strip(),validate=True))
        # Fully decompress before extraction, validating the complete gzip CRC/trailer.
        with gzip.open(compressed,'rb') as src,archive.open('wb') as dst:shutil.copyfileobj(src,dst)
        expected=set(selected);seen=set();symlinks={}
        with tarfile.open(archive,'r:') as tar:
            for member in tar:
                name=relative_path(member.name)
                if name not in expected or name in seen:raise PatchError('ADB 归档包含非预期/重复路径：'+name)
                seen.add(name);dest=safe(local,name);dest.parent.mkdir(parents=True,exist_ok=True)
                if member.isfile():
                    with tar.extractfile(member) as src,dest.open('wb') as dst:shutil.copyfileobj(src,dst)
                elif member.issym():
                    # Do not follow phone symlinks into host or running phone partitions.
                    dest.write_bytes(b'!<symlink>'+member.linkname.encode()+b'\0')
                    if any(ord(c)<32 for c in member.linkname):raise PatchError('链接目标含控制字符：'+name)
                    symlinks[name]=member.linkname
                else:raise PatchError('不支持的归档项（目录/硬链接/设备节点）：'+name)
        if seen!=expected:raise PatchError('ADB 读取不完整，未修改手机；缺少：'+', '.join(sorted(expected-seen)[:12]))
        for temporary in (archive,encoded,compressed):temporary.unlink()
        info=dict(serial=self.serial,device=self.device,root=root,layout=layout,files=selected,libraries=libraries,symlinks=symlinks,
                  source_kind='adb-live-readonly' if live else 'adb-extracted-rom',writeback_allowed=not live)
        if live:
            info['warning']='读取的是当前可见系统，可能包含其他模块挂载；不是保证纯净的出厂分区。'
        save_json(logdir/'snapshot.json',info)
        return local,info


def make_upload(session,restore=False):
    session=Path(session);report=json.loads(read(session/'report.json'))
    rows=report['files'];data=[]
    for row in rows:
        relative_path(row['path'])
        if not re.fullmatch(r'[0-7]{3,4}',row['mode']):raise PatchError('非法文件权限：'+row['path'])
        if any(value is not None and not re.fullmatch(r'[0-9a-f]{64}',value) for value in (row['before'],row['after'])):
            raise PatchError('备份清单摘要不合法：'+row['path'])
        before=row['after'] if restore else row['before']
        after=row['before'] if restore else row['after']
        data.append('\t'.join((row['path'],before or '-',after or '-',row['mode'])))
    archive=session/('adb-restore.tar' if restore else 'adb-apply.tar')
    with tarfile.open(archive,'w') as tar:
        def put(name,value):
            entry=tarfile.TarInfo(name);entry.size=len(value);entry.mode=0o600
            tar.addfile(entry,io.BytesIO(value))
        put('manifest.tsv',('\n'.join(data)+'\n').encode())
        put('transaction.sh',(ASSETS/'adb-transaction.sh').read_bytes())
        put('operation.txt',b'restore\n' if restore else b'apply\n')
        connection_file=session/'adb-session.json'
        guards=[]
        if connection_file.is_file():
            connection=json.loads(read(connection_file))
            targets={row['path'] for row in rows}
            for guard in connection.get('input_guards',[]):
                if restore and guard['path'] in targets:continue
                relative_path(guard['path'])
                if any(ord(c)<32 for c in guard['expected']):raise PatchError('非法输入校验记录')
                guards.append('\t'.join((guard['path'],guard['kind'],guard['expected'])))
        put('guards.tsv',('\n'.join(guards)+'\n' if guards else '').encode())
        folder='original_files' if restore else 'patch_tree'
        for row in rows:
            expected=row['before'] if restore else row['after']
            if expected is None:continue
            source=safe(session/folder,row['path'])
            if not source.is_file() or sha(source)!=expected:raise PatchError('本机补丁/备份已变化：'+row['path'])
            tar.add(source,arcname='patch_tree/'+row['path'],recursive=False)
    return archive


def apply_remote(session,restore=False,log=lambda s:None):
    session=Path(session);connection=json.loads(read(session/'adb-session.json'))
    if connection.get('source_kind')=='adb-live-readonly' or connection.get('writeback_allowed') is False:
        raise PatchError('实时系统快照禁止写回')
    report=json.loads(read(session/'report.json'))
    if connection.get('state') in ('prepared','running','recovery-required'):
        raise PatchError('此任务状态尚未解决，请先恢复任务状态，不要重复写入：'+str(session))
    if bool(report.get('applied'))==bool(not restore):raise PatchError('该构建已应用' if not restore else '该构建尚未应用')
    adb=Adb(connection['serial'],log);root=adb.validate_root(connection['root'])
    if root!=connection['root']:raise PatchError('手机解包目录指向已改变，拒绝修改')
    archive=make_upload(session,restore)
    token=uuid.uuid4().hex
    parent=str(PurePosixPath(root).parent)
    job=parent+'/.dolby-patcher-backups/'+PurePosixPath(root).name+'-'+token
    upload='/data/local/tmp/dolby-upload-'+token+'.tar'
    adb.shell('test ! -e '+shlex.quote(upload)+'\ntest ! -e '+shlex.quote(job))
    log('推送改动到设备 '+adb.serial+'，手机备份：'+job)
    result=execute([adb_path(),'-s',adb.serial,'push',str(archive),upload],capture_output=True,timeout=600)
    if result.returncode:raise PatchError('ADB 推送失败：'+result.stderr.decode(errors='replace'))
    q=shlex.quote
    # Restrict the backup location as carefully as the ROM destination.
    backup_parent=parent+'/.dolby-patcher-backups'
    adb.shell(f'test ! -L {q(backup_parent)}\nmkdir -p {q(backup_parent)}\n'
              f'test "$(readlink -f {q(backup_parent)})" = {q(backup_parent)}\n'
              f'mkdir {q(job)}\nchmod 700 {q(job)}\ntar -xf {q(upload)} -C {q(job)}\n'
              f'printf "%s\\n" {q(root)} > {q(job+"/root.txt")}\nrm -f {q(upload)}')
    if connection.get('job'):
        connection.setdefault('previous_jobs',[]).append({key:connection.get(key) for key in ('job','operation','state')})
    connection.update(job=job,operation='restore' if restore else 'apply',state='prepared')
    save_json(session/'adb-session.json',connection)
    # A detached one-shot process completes/rolls back even if the cable disconnects.
    adb.shell(f'command -v nohup >/dev/null\ncommand -v tac >/dev/null\n'
              f'nohup sh {q(job+"/transaction.sh")} {q(job)} > {q(job+"/run.log")} 2>&1 < /dev/null &')
    connection['state']='running';save_json(session/'adb-session.json',connection)
    return monitor_remote(session,adb,log)


def monitor_remote(session,adb=None,log=lambda s:None):
    session=Path(session);connection=json.loads(read(session/'adb-session.json'))
    adb=adb or Adb(connection['serial'],log)
    if adb.serial!=connection['serial']:raise PatchError('设备序列号不一致')
    if not connection.get('job'):raise PatchError('此构建尚未启动手机写回事务，无需恢复状态')
    job=connection['job'];last='';q=shlex.quote
    for attempt in range(300):
        try:
            state=adb.shell('if [ -f '+q(job+'/status')+' ]; then cat '+q(job+'/status')+'; else echo starting; fi',timeout=20).decode().strip()
        except Exception as e:
            raise PatchError('ADB 中断；手机端一次性事务可能仍在完成/回退，请重连同一设备后用“恢复任务状态”，不要重新点安装。记录：'+str(session)) from e
        if state!=last:log('手机事务：'+state);last=state
        if state in ('complete','rolled-back','failed-preflight','recovery-required'):
            connection['state']=state;save_json(session/'adb-session.json',connection)
            transaction_log=adb.shell('cat '+q(job+'/run.log')).decode('utf-8',errors='replace')
            write(session/'adb-transaction.log',transaction_log)
            if state=='complete':
                report=json.loads(read(session/'report.json'))
                report['applied']=connection['operation']=='apply'
                save_json(session/'report.json',report)
                log(('已回退手机内解包 ROM' if connection['operation']=='restore' else '已修改手机内解包 ROM')+'；未刷分区、未重启。PC 与手机备份均保留。')
                return session
            detail={'failed-preflight':'写入前检查失败，未写入 ROM 文件',
                    'rolled-back':'写入失败，已回退本次文件修改',
                    'recovery-required':'回退未完成，请保留备份，不要重复安装'}[state]
            tail='\n'.join(transaction_log.strip().splitlines()[-8:])
            raise PatchError(detail+'（'+state+'）\n'+tail+'\n日志：'+str(session/'adb-transaction.log')+'。手机任务/备份：'+job)
        time.sleep(1)
    raise PatchError('等待手机事务超时，未判定成功。请稍后恢复任务状态：'+str(session))


def run_adb(serial,root,log=lambda s:None,inspect_only=False,build_only=False,output=None):
    base=Path(output) if output else history_root()/'adb'
    jobdir=base/('ADB_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    jobdir.mkdir(parents=True,exist_ok=False)
    log('电脑自动缓存/记录：'+str(jobdir))
    adb=Adb(serial,log);local,info=adb.snapshot(root,jobdir)
    _,inspection=inspect_rom(local)
    log('结构检查通过：'+inspection['model']+' / SDK '+inspection['sdk'])
    if inspect_only:return jobdir
    builder=Build(local,jobdir/'build',log)
    builder.library_inventory=info['libraries']
    session=builder.run()
    guards=[dict(path=name,kind='L' if name in info['symlinks'] else 'F',
                 expected=info['symlinks'].get(name) if name in info['symlinks'] else sha(safe(local,name))) for name in info['files']]
    save_json(session/'adb-session.json',dict(serial=serial,root=info['root'],state='built',device=info['device'],input_guards=guards))
    save_json(base/'最新构建.json',dict(session=str(session),mode='adb',serial=serial,root=info['root']))
    if not build_only:apply_remote(session,log=log)
    return session
