"""Offline ColorOS Dolby integration; input is read-only until explicit apply."""
from __future__ import annotations
import copy
import csv
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

VERSION = '1.0.3'
ASSETS = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'assets'
BEGIN = '; BEGIN MIO DOLBY NATIVE v1'
END = '; END MIO DOLBY NATIVE v1'

class PatchError(RuntimeError):
    pass


def context_key(path):
    """Regex literal compatible with DNA's exact-key metadata rebuilding."""
    for char in '\\^$.|?*+(){}[]':
        path=path.replace(char,'\\'+char)
    return '/'+path.lstrip('/')


def upsert_context(lines, path, label, is_file=True):
    key=context_key(path)
    aliases={key,'/'+re.escape(path.lstrip('/')),'/'+path.lstrip('/')}
    positions=[i for i,line in enumerate(lines) if line.split() and line.split()[0] in aliases]
    if positions and not is_file:
        labels={lines[i].split()[-1] for i in positions}
        if len(labels)!=1:raise PatchError('目录标签存在冲突：'+path)
        label=labels.pop()
    entry=key+' '+label
    if not positions:return [*lines,entry]
    first=positions[0];duplicates=set(positions[1:])
    return [entry if i==first else line for i,line in enumerate(lines) if i not in duplicates]

def read(path: Path) -> str:
    return path.read_text(encoding='utf-8-sig')

def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace('\r\n', '\n'), encoding='utf-8', newline='\n')

def save_json(path, data):
    write(path, json.dumps(data, ensure_ascii=False, indent=2) + '\n')

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def safe(root: Path, relative: str) -> Path:
    p = PurePosixPath(relative)
    if p.is_absolute() or '..' in p.parts or not p.parts or ':' in relative or '\\' in relative:
        raise PatchError(f'非法相对路径：{relative}')
    result = root.joinpath(*p.parts)
    candidate = result
    while candidate != root:
        if candidate.is_symlink() or (hasattr(candidate, 'is_junction') and candidate.is_junction()):
            raise PatchError(f'修改路径包含链接：{candidate}')
        candidate = candidate.parent
    if not result.resolve().is_relative_to(root.resolve()):
        raise PatchError(f'路径越界：{relative}')
    return result

def xml_parse(data: bytes):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise PatchError('XML 包含不支持的 DTD/实体定义')
    return ET.fromstring(data, parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)))

def xml_bytes(root, original=None):
    ET.indent(root, space='    ')
    output=ET.tostring(root, encoding='utf-8', xml_declaration=True) + b'\n'
    if original:
        # Preserve leading license/comments which ElementTree omits outside the root.
        text=original.decode('utf-8-sig')
        preamble=re.match(r'\s*(?:<\?xml.*?\?>\s*)?((?:<!--.*?-->\s*)*)',text,re.S)
        if preamble and preamble.group(1):
            declaration,body=output.split(b'\n',1)
            output=declaration+b'\n'+preamble.group(1).encode('utf-8')+body
    return output

def merge_effects(data: bytes, reference: bytes):
    root, ref = xml_parse(data), xml_parse(reference)
    if root.tag.split('}')[-1] != 'audio_effects_conf':
        raise PatchError('不支持的音效 XML 根节点')
    namespace = root.tag.split('}')[0]+'}' if root.tag.startswith('{') else ''
    if namespace:ET.register_namespace('',namespace[1:-1])
    for section, node, key in [('libraries', ref.find("./{*}libraries/{*}library[@name='dolby_dap_lab']"), 'name'),
                               ('effects', ref.find("./{*}effects/{*}effect[@name='dap']"), 'uuid')]:
        parent = root.find('{*}'+section)
        if parent is None or node is None:
            raise PatchError(f'音效 XML 缺少 {section}')
        existing = [n for n in parent if n.get(key) == node.get(key) or n.get('name') == node.get('name')]
        if existing:
            if len(existing) != 1 or existing[0].attrib != node.attrib:
                raise PatchError('已有不同的 DAP 配置；请先使用未修改的原包')
        else:
            added=copy.deepcopy(node)
            for child in added.iter():
                if isinstance(child.tag,str):child.tag=namespace+child.tag.split('}')[-1]
            parent.append(added)
    return xml_bytes(root,data)

def merge_codecs(data: bytes, reference: bytes):
    root, ref = xml_parse(data), xml_parse(reference)
    decoders = root.find('Decoders')
    if root.tag not in ('MediaCodecs','Included') or decoders is None:
        raise PatchError('Codec XML 缺少 MediaCodecs/Included 下的 Decoders')
    for node in ref.findall('./Decoders/MediaCodec'):
        name = node.get('name', '')
        if not name.startswith('c2.dolby.'):
            continue
        existing = [n for n in decoders if n.get('name') == name]
        if existing:
            def signature(n):
                return (n.tag, sorted(n.attrib.items()), (n.text or '').strip(), [signature(c) for c in n if isinstance(c.tag, str)])
            if len(existing) != 1 or signature(existing[0]) != signature(node):
                raise PatchError(f'已有不同的解码器配置：{name}')
        else:
            decoders.append(copy.deepcopy(node))
    return xml_bytes(root,data)

def merge_framework(data, names=None):
    root = xml_parse(data)
    if root.tag != 'manifest' or root.get('type') != 'framework':
        raise PatchError('目标不是 framework VINTF manifest')
    for name, version, interface in [('android.hidl.manager', '1.2', 'IServiceManager'),
                                     ('android.hidl.token', '1.0', 'ITokenManager')]:
        if names is not None and name not in names:continue
        matches = [n for n in root.findall('hal') if n.findtext('name') == name]
        if len(matches) > 1:
            raise PatchError(f'重复的 framework HAL：{name}')
        if matches:
            hal = matches[0]
            if hal.get('format') != 'hidl':
                raise PatchError(f'非 HIDL 的 {name}')
            hal.attrib.pop('max-level', None)
        else:
            hal = ET.SubElement(root, 'hal', {'format': 'hidl'})
            ET.SubElement(hal, 'name').text = name
            ET.SubElement(hal, 'transport').text = 'hwbinder'
            ET.SubElement(hal, 'fqname').text = f'@{version}::{interface}/default'
    return xml_bytes(root,data)

def append_cil(original, delta):
    if BEGIN in original or END in original:
        if original.count(BEGIN) != 1 or original.count(END) != 1:
            raise PatchError('Dolby 策略标记不完整或重复')
        original = re.sub(re.escape(BEGIN) + r'.*?' + re.escape(END) + r'\s*', '', original, flags=re.S)
    return original.rstrip() + '\n\n' + BEGIN + '\n' + delta.strip() + '\n' + END + '\n'

class Rom:
    def __init__(self, root, require_metadata=True):
        self.root = Path(root).resolve()
        self.parts = {}
        if not self.root.is_dir():
            raise PatchError('请选择已解包的 ROM 目录')
        for part in ('system', 'system_ext', 'vendor', 'odm', 'product'):
            candidates = ([self.root/'system/system', self.root/'system_a/system'] if part == 'system' else [])
            candidates += [self.root/part, self.root/(part+'_a')]
            candidates += [self.root/'system/system'/part, self.root/'system'/part]
            for p in candidates:
                if (p/'etc').is_dir():
                    if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):
                        continue
                    self.parts[part] = p
                    break
        missing = {'system','system_ext','vendor','odm','product'} - self.parts.keys()
        if missing:
            raise PatchError('ROM 分区不完整，缺少：' + ', '.join(sorted(missing)))
        if require_metadata and not (self.root/'config').is_dir():
            raise PatchError('缺少 config 目录；请选择 MIO/DNA 解包后带 fs_config、file_contexts 的目录')

    def path(self, canonical):
        part, sub = canonical.split('/', 1)
        return safe(self.root, (self.parts[part]/sub).relative_to(self.root).as_posix())

    def rel(self, canonical):
        return self.path(canonical).relative_to(self.root).as_posix()

    def metadata(self, part, suffix):
        for prefix in (part, part+'_a'):
            p = self.root/'config'/f'{prefix}_{suffix}'
            if p.is_file():
                return p
        raise PatchError(f'缺少 {part}_{suffix}')

    def packing_prefix(self, part, suffix):
        """Infer the unpacker's key prefix; slot directory names needn't equal image keys."""
        directory=self.parts[part].relative_to(self.root).as_posix()
        candidates=[directory,re.sub(r'^([^/]+)_a(?=/|$)',r'\1',directory),part]
        keys=[line.split()[0] for line in read(self.metadata(part,suffix)).splitlines()
              if line.split() and not line.lstrip().startswith('#')]
        counts={c:sum(k.lstrip('/').startswith(c+'/etc/') for k in keys) for c in set(candidates)}
        best=max(counts,key=counts.get)
        if not counts[best]:raise PatchError(f'无法识别 {part}_{suffix} 的打包路径前缀')
        return directory,best

    def props(self):
        result = {}
        for base in self.parts.values():
            for p in (base/'build.prop', base/'etc/build.prop'):
                if p.is_file():
                    for line in read(p).splitlines():
                        if '=' in line and not line.lstrip().startswith('#'):
                            k,v = line.split('=',1); result[k.strip()] = v.strip()
        return result

    def existing_file_label(self, canonical):
        """Read the unpacker's exact regular-file label, never guess a default.

        This is packing metadata, not the host filesystem's /data label. Accept
        DNA, legacy Python escaping and literal keys, including slot/SAR prefixes.
        Ambiguous or missing entries require an explicit label from the caller.
        """
        part=canonical.split('/',1)[0]
        directory,prefix=self.packing_prefix(part,'file_contexts')
        packpath=prefix+self.rel(canonical)[len(directory):]
        aliases={context_key(packpath),'/'+re.escape(packpath),'/'+packpath}
        labels=set()
        for line in read(self.metadata(part,'file_contexts')).splitlines():
            fields=line.split()
            if not fields or fields[0] not in aliases:continue
            if len(fields)==3 and fields[1]!='--':continue
            if len(fields) not in (2,3) or not re.fullmatch(r'u:object_r:[A-Za-z0-9_]+:s0(?::[A-Za-z0-9_,.]+)?',fields[-1]):
                raise PatchError('已有文件的打包标签格式不明确：'+canonical)
            labels.add(fields[-1])
        if len(labels)!=1:
            raise PatchError('已有文件缺少唯一打包标签，拒绝用默认值覆盖：'+canonical)
        return labels.pop()

def inspect_rom(root, require_metadata=True, enforce_sdk=True):
    rom = Rom(root,require_metadata=require_metadata)
    props = rom.props()
    sdk = props.get('ro.system.build.version.sdk', props.get('ro.build.version.sdk', ''))
    if enforce_sdk and sdk != '37':
        raise PatchError(f'此版针对 Android 17 / SDK 37，所选 ROM SDK 为 {sdk or "未知"}')
    if props.get('hwservicemanager.disabled')=='true':
        raise PatchError('ROM 属性显式禁用了 hwservicemanager，需要先处理启动配置')
    for p in ('system/etc/init',
              'system_ext/etc/selinux/system_ext_file_contexts',
              'vendor/etc/selinux/plat_sepolicy_vers.txt','vendor/etc/selinux/vendor_sepolicy.cil',
              'system/etc/selinux/plat_sepolicy.cil'):
        if not rom.path(p).exists():
            raise PatchError(f'缺少必需文件/目录：{p}')
    if require_metadata:
        for part in ('system','system_ext','vendor','odm'):
            for suffix in ('fs_config','file_contexts'):
                rom.metadata(part,suffix)
    # A pre-existing HWS must be present in the ROM; changing VINTF cannot supply its executable.
    if not any(rom.path(p).is_file() for p in ('system_ext/bin/hwservicemanager','system/bin/hwservicemanager')):
        raise PatchError('ROM 缺少 hwservicemanager 可执行文件，需要另行适配')
    from discovery import discover
    config=discover(rom)
    # These are existing service domains in supported vendor policy, not invented aliases.
    vendor_policy=read(rom.path('vendor/etc/selinux/vendor_sepolicy.cil'))
    required=('hal_dms_default','hal_dms_default_exec','hal_dms_hwservice',
              'hal_aidl_dms_default','hal_aidl_dms_default_exec','hal_aidl_dms_service')
    missing=[n for n in required if not re.search(r'\(type\s+'+re.escape(n)+r'\s*\)',vendor_policy)]
    if missing:raise PatchError('此 vendor 缺少杜比 HAL 策略域，需单独适配：'+', '.join(missing))
    return rom, {'sdk':sdk, 'fingerprint':props.get('ro.system.build.fingerprint',''),
                 'model':props.get('ro.product.vendor.model',props.get('ro.product.model','未知')),
                 'mapping_version':read(rom.path('vendor/etc/selinux/plat_sepolicy_vers.txt')).strip(),
                 'partitions':{k:str(v) for k,v in rom.parts.items()},'configuration':config,
                 'support_scope':'ARM64 Qualcomm AIDL audio + existing Dolby SELinux domains; no device-name lock'}

class Build:
    def __init__(self, root, output, log=lambda s: None, require_metadata=True, enforce_sdk=True):
        self.rom,self.info = inspect_rom(root,require_metadata=require_metadata,enforce_sdk=enforce_sdk)
        self.require_metadata=require_metadata
        output = Path(output).resolve()
        if output.is_relative_to(self.rom.root) or self.rom.root.is_relative_to(output):
            raise PatchError('输出目录请放在 ROM 目录之外，且不要选择 ROM 的上级目录')
        self.session = output / ('Dolby_' + time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:6])
        self.tree = self.session/'patch_tree'
        self.tree.mkdir(parents=True)
        self.log = log
        self.changes = {}
        self.notes = []

    def stage(self, canonical, data, mode='0644', label=None):
        part = canonical.split('/')[0]
        rel = self.rom.rel(canonical)
        if label is None:
            if rel in self.changes:
                label=self.changes[rel]['label']
            elif self.require_metadata and self.rom.path(canonical).is_file():
                label=self.rom.existing_file_label(canonical)
            else:
                label = 'u:object_r:vendor_configs_file:s0' if part in ('vendor','odm') else 'u:object_r:system_file:s0'
        path = safe(self.tree,rel)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
        self.changes[rel] = dict(path=rel,canonical=canonical,partition=part,mode=mode,label=label)

    def get(self, canonical):
        rel = self.rom.rel(canonical)
        p = self.tree/rel
        return p if p.is_file() else self.rom.path(canonical)

    def add_payload(self):
        rows = json.loads(read(ASSETS/'payload.json'))
        with zipfile.ZipFile(ASSETS/'payload.zip') as z:
            for row in rows:
                name = row['canonical']
                data = z.read(name)
                target = self.rom.path(name)
                if target.exists() and target.read_bytes() != data:
                    raise PatchError(f'已有不同的同名杜比文件：{name}；未修改输入 ROM')
                self.stage(name,data,row['Mode'],row['SELinux'])
        from elf_audit import audit
        audit(self)

    def merge_configs(self):
        config=self.info['configuration']
        save_json(self.session/'configuration-report.json',config)
        for name in config['effects']:
            self.log('音效配置：'+name)
            self.stage(name,merge_effects(self.get(name).read_bytes(),(ASSETS/'effects-reference.xml').read_bytes()))
        for name in config['codecs']:
            self.log('解码器配置：'+name)
            self.stage(name,merge_codecs(self.get(name).read_bytes(),(ASSETS/'codecs-reference.xml').read_bytes()))
        # Fail on another fragment declaring the same service, instead of silently adding duplicates.
        framework_nodes={}
        for part in ('vendor','odm','system','system_ext'):
            directory = self.rom.parts[part]/'etc/vintf'
            manifests = list(directory.glob('manifest*.xml')) + list((directory/'manifest').rglob('*.xml'))
            for path in manifests:
                if path == self.rom.path('vendor/etc/vintf/manifest/dolby-native.xml'):
                    continue
                data=path.read_bytes()
                if data.startswith(b'!<symlink>'):
                    tail=data[len(b'!<symlink>'):].rstrip(b'\x00')
                    # Cygwin's extraction placeholder for a kernel-generated OPlus manifest.
                    raw=data[len(b'!<symlink>'):]
                    link=raw.decode('utf-16',errors='replace').rstrip('\x00') if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else tail.decode('utf-8',errors='replace')
                    if link.lstrip('/').startswith('proc/oplusManifest/'):
                        note=f'保留内核动态 VINTF 链接（离线无法展开）：{path.relative_to(self.rom.root)} -> {link}'
                        self.notes.append(note);self.log(note);continue
                    raise PatchError(f'VINTF 使用未展开的符号链接，请提供实际 XML：{path} -> {link}')
                try:
                    root = xml_parse(data)
                except ET.ParseError as e:
                    raise PatchError(f'VINTF XML 无法解析：{path}：{e}') from e
                if root.tag == 'manifest':
                    for hal in root.findall('hal'):
                        name = hal.findtext('name','')
                        if name in ('vendor.dolby.dms','vendor.dolby.hardware.dms') or (name == 'android.hardware.media.c2' and any('default9' in (n.text or '') for n in hal.iter())):
                            raise PatchError(f'另一份 VINTF 已声明相同 Dolby 服务：{path}')
                        if root.get('type')=='framework' and name in ('android.hidl.manager','android.hidl.token'):
                            if name in framework_nodes:raise PatchError(f'重复的 HIDL framework 声明：{name}')
                            framework_nodes[name]=part+'/'+path.relative_to(self.rom.parts[part]).as_posix()
        default='system_ext/etc/vintf/manifest.xml'
        for hal in ('android.hidl.manager','android.hidl.token'):
            name=framework_nodes.get(hal,default)
            data=self.get(name).read_bytes() if self.get(name).is_file() else b'<manifest version="1.0" type="framework"/>'
            self.stage(name,merge_framework(data,names={hal}))
        name = 'system_ext/etc/selinux/system_ext_file_contexts'
        text = read(self.get(name))
        entries = [(r'/system_ext/bin/hw/vendor\.dolby\.dms\.service','hal_aidl_dms_default_exec'),
                   (r'/system_ext/bin/hw/dolbycodecservice','mediacodec_exec')]
        for pattern,typename in entries:
            line = f'{pattern} u:object_r:{typename}:s0'
            old = [l for l in text.splitlines() if l.split() and l.split()[0] == pattern]
            if old and any(l.strip() != line for l in old):
                raise PatchError(f'已有不同的可执行文件标签：{pattern}')
            if not old:
                text = text.rstrip() + '\n' + line + '\n'
        self.stage(name,text.encode())

    def compile_policy(self):
        from policy import compile_all
        compile_all(self)

    def metadata(self):
        for part in ('system','system_ext','vendor','odm'):
            files = [r for r in self.changes.values() if r['partition']==part]
            paths = {}
            for row in files:
                paths[row['path']] = (row['mode'],row['label'],True)
                parent = PurePosixPath(row['path']).parent
                limit = self.rom.parts[part].relative_to(self.rom.root).as_posix()
                while str(parent) != limit and str(parent) != '.':
                    directory_label = 'u:object_r:vendor_file:s0' if part in ('vendor','odm') else 'u:object_r:system_file:s0'
                    if '/etc' in str(parent) and part in ('vendor','odm'):
                        directory_label = 'u:object_r:vendor_configs_file:s0'
                    if part=='system_ext' and '/lib64' in str(parent):
                        directory_label = 'u:object_r:system_lib_file:s0'
                    paths.setdefault(str(parent),('0755',directory_label,False))
                    parent = parent.parent
            for suffix in ('fs_config','file_contexts'):
                original = self.rom.metadata(part,suffix)
                directory,prefix=self.rom.packing_prefix(part,suffix)
                lines = read(original).splitlines()
                indices = {}
                for i,line in enumerate(lines):
                    tokens=line.split()
                    if tokens and not line.lstrip().startswith('#'):
                        indices.setdefault(tokens[0],[]).append(i)
                for path,(mode,label,is_file) in sorted(paths.items()):
                    packpath=prefix+path[len(directory):]
                    if suffix=='file_contexts':
                        lines=upsert_context(lines,packpath,label,is_file)
                        continue
                    key = packpath if suffix=='fs_config' else '/'+re.escape(packpath)
                    positions = indices.get(key,[])
                    if not positions and suffix=='file_contexts':
                        positions = indices.get('/'+packpath,[])
                    if positions and not is_file:
                        continue
                    if suffix=='fs_config':
                        # Preserve optional capability/fs-config columns.
                        extra = ' '.join(lines[positions[0]].split()[4:]) if positions else ''
                        new = f'{key} 0 0 {mode}' + (' '+extra if extra else '')
                    else:
                        new = f'{key} {label}'
                    if positions:
                        for i in positions: lines[i] = new
                    else:
                        lines.append(new)
                rel = original.relative_to(self.rom.root).as_posix()
                write(self.tree/rel,'\n'.join(lines)+'\n')
                self.changes[rel] = dict(path=rel,partition='config',canonical=rel,mode='0644',label='packing metadata')

    def package(self):
        records=[]
        for rel,row in sorted(self.changes.items()):
            target=safe(self.rom.root,rel)
            staged=safe(self.tree,rel)
            old_hash=None
            if target.exists():
                if not target.is_file(): raise PatchError(f'目标不是普通文件：{target}')
                old_hash=sha(target)
                dest=safe(self.session/'original_files',rel)
                dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(target,dest)
            records.append({**row,'operation':'replace' if old_hash else 'add',
                            'before':old_hash,'after':sha(staged),'bytes':staged.stat().st_size})
        report=dict(version=VERSION,rom=str(self.rom.root),rom_info=self.info,applied=False,notes=self.notes,
                    policy=json.loads(read(self.session/'policy-report.json')),files=records)
        save_json(self.session/'report.json',report)
        with (self.session/'文件与标签.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(['分区','操作','路径','用户:组','权限','SELinux标签'])
            for r in records:w.writerow([r['partition'],r['operation'],r['path'],'0:0',r['mode'],r['label']])
        write(self.session/'使用说明.txt',
              '这是本次所选 ROM 专用的杜比内置增量包。\n'
              'patch_tree 内的分区目录和 config 按原层级合并到解包目录；config 仅供打包，不写入 Android 运行分区。\n'
              'system/system 是 DNA 的 system-as-root 层级，不能自行少放一层。\n'
              '也可在工具内点击“应用到所选 ROM”，工具会保留备份并记录已应用状态。\n'
              '必须重新打包 system、system_ext、vendor、odm 分区。product 若报告列有预编译摘要更新也需跟随打包。\n'
              'root sepolicy.rule 是增量规则源，不需重复转 CIL；本包已按所选 ROM 编译策略。\n'
              '不要同时启用旧 Dolby Magisk 模块。RC 需要在 init 解析时可见。\n'
              '本工具完成文件与策略部署；新 ROM 的开机、调参、音效链和解码仍需实机验证。\n'
              '原文件在 original_files；回退请用本工具打开本次构建目录并选择回退。\n')
        zip_path=self.session/'Dolby_C17_内置增量.zip'
        with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,strict_timestamps=False) as z:
            for folder in ('patch_tree','original_files','upstream-lunaris'):
                for p in (self.session/folder).rglob('*'):
                    if p.is_file():z.write(p,p.relative_to(self.session).as_posix())
            for name in ('report.json','policy-report.json','policy-rules-report.json','configuration-report.json','dependency-report.json','文件与标签.csv','使用说明.txt','sepolicy.rule','dolby.cil'):
                z.write(self.session/name,name)
            for p in sorted(self.session.glob('policy-*.log')):
                z.write(p,p.name)
            for pattern in ('stock-dolby-*','upstream-policy-report.json','dolby-debug.cil','sepolicy-debug.rule'):
                for p in sorted(self.session.glob(pattern)):
                    if p.is_file():z.write(p,p.name)
        with zipfile.ZipFile(zip_path) as z:
            bad=z.testzip()
            if bad:raise PatchError(f'生成 ZIP 校验失败：{bad}')
        return report

    def run(self):
        try:
            for title,fn in [('部署内置 App / Dolby 服务与私有库',self.add_payload),
                             ('合并音效 / 解码器 XML、VINTF 与标签',self.merge_configs),
                             ('按目标 ROM 编译普通 / 调试 SELinux 策略',self.compile_policy),
                             ('合并各分区打包元数据',self.metadata),
                             ('保存原文件、清单并校验增量包',self.package)]:
                self.log(title); fn()
            self.log('完成：'+str(self.session))
            return self.session
        except Exception as e:
            write(self.session/'FAILED.txt',str(e))
            raise

def apply_session(session, restore=False, log=lambda s: None):
    session=Path(session).resolve()
    report=json.loads(read(session/'report.json'))
    root=Path(report['rom']).resolve()
    if restore and not report.get('applied'):
        raise PatchError('这次构建尚未应用，无需回退')
    if not restore and report.get('applied'):
        raise PatchError('这次构建已经应用')
    rows=report['files']
    # Full preflight before the first mutation; source and backup must also be intact.
    for r in rows:
        target=safe(root,r['path'])
        actual=sha(target) if target.is_file() else None
        expected=r['after'] if restore else r['before']
        if actual != expected:
            raise PatchError(f'目标文件在构建后发生变化，未覆盖：{r["path"]}')
        source=safe(session/('original_files' if restore else 'patch_tree'),r['path'])
        desired=r['before'] if restore else r['after']
        if desired is not None and (not source.is_file() or sha(source)!=desired):
            raise PatchError(f'补丁/备份文件不完整：{source}')
    done=[]
    save_json(session/'transaction.json',dict(restore=restore,state='applying',completed=done))
    try:
        for r in rows:
            target=safe(root,r['path'])
            source=safe(session/('original_files' if restore else 'patch_tree'),r['path'])
            target.parent.mkdir(parents=True,exist_ok=True)
            if restore and r['before'] is None:
                target.unlink()
            else:
                temp=target.with_name(target.name+'.dolby-tmp-'+uuid.uuid4().hex[:8])
                try: shutil.copy2(source,temp); os.replace(temp,target)
                finally:
                    if temp.exists():temp.unlink()
            done.append(r['path'])
            save_json(session/'transaction.json',dict(restore=restore,state='applying',completed=done))
        report['applied']=not restore
        save_json(session/'report.json',report)
        save_json(session/'transaction.json',dict(restore=restore,state='complete',completed=done))
    except Exception:
        # Revert only files this transaction actually touched.
        for r in reversed(rows):
            if r['path'] not in done:continue
            target=safe(root,r['path'])
            source=safe(session/('patch_tree' if restore else 'original_files'),r['path'])
            if not restore and r['before'] is None:
                if target.is_file():target.unlink()
            else:shutil.copy2(source,target)
        save_json(session/'transaction.json',dict(restore=restore,state='rolled-back',completed=done))
        raise
    log('已回退本次修改' if restore else '已应用到所选 ROM；原文件备份保留在构建目录')
    return root
