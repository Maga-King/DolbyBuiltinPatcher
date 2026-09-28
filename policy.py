"""Rebuild policy from selected ROM inputs, with both normal and debug chains."""
import re
import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from core import ASSETS, PatchError, append_cil, read, save_json, write

def semantic_failure(returncode, log):
    # secilc returns libsepol's negative error values directly. Windows exposes
    # these as unsigned DWORDs; they are not Windows exception/crash statuses.
    normal_error=(returncode & 0xffffffff) in (1,0xffffffff,0xfffffffe,0xfffffffd)
    if os.name!='nt' and returncode in (253,254,255):normal_error=True
    diagnostic=re.search(r'Failed to (?:resolve|compile|build|verify|generate)|Policy must|Invalid ',log)
    resource_error=re.search(r'out of memory|cannot allocate|failed to (?:open|write|read|stat)',log,re.I)
    return normal_error and bool(diagnostic) and not resource_error

def binary_version(path):
    data=path.read_bytes()[:128]
    if len(data)<20 or struct.unpack_from('<I',data)[0]!=0xf97cff8c:
        raise PatchError(f'无效的原厂预编译策略头：{path}')
    size=struct.unpack_from('<I',data,4)[0]
    if size>80:raise PatchError('无效的策略标识长度')
    return struct.unpack_from('<I',data,8+size)[0]

def inputs(build, debug):
    rom=build.rom
    suffix='_debug' if debug else ''
    mapping=read(rom.path('vendor/etc/selinux/plat_sepolicy_vers.txt')).strip()
    if not re.fullmatch(r'[0-9.]+',mapping):raise PatchError('无效的 plat_sepolicy_vers')
    platform='system/etc/selinux/plat_sepolicy.cil'
    if debug:
        for candidate in ('system_ext/etc/selinux/plat_sepolicy_debug.cil','system/etc/selinux/plat_sepolicy_debug.cil'):
            if rom.path(candidate).is_file():platform=candidate;break
    names=[platform,f'system/etc/selinux/mapping/{mapping}.cil']
    for n in names:
        if not rom.path(n).is_file():raise PatchError(f'缺少编译必需输入：{n}')
    optional=[f'system/etc/selinux/mapping/{mapping}.compat.cil']
    for part in ('system_ext','product'):
        normal=f'{part}/etc/selinux/{part}_sepolicy.cil'
        variant=f'{part}/etc/selinux/{part}_sepolicy{suffix}.cil'
        optional += [variant if rom.path(variant).is_file() else normal,
                     f'{part}/etc/selinux/mapping/{mapping}.cil',
                     f'{part}/etc/selinux/mapping/{mapping}.compat.cil']
    for part,name in [('vendor','plat_pub_versioned'),('vendor','vendor_sepolicy'),('odm','odm_sepolicy')]:
        normal=f'{part}/etc/selinux/{name}.cil'
        variant=f'{part}/etc/selinux/{name}{suffix}.cil'
        candidate=variant if rom.path(variant).is_file() else normal
        if part=='vendor' and not rom.path(candidate).is_file():raise PatchError(f'缺少 {candidate}')
        optional.append(candidate)
    genver=rom.path('vendor/etc/selinux/genfs_labels_version.txt')
    if genver.is_file():
        ver=read(genver).strip()
        if not ver.isdigit():raise PatchError('无效 genfs_labels_version')
        if int(ver)>202404:
            candidate=f'system/etc/selinux/plat_sepolicy_genfs_{ver}.cil'
            if not rom.path(candidate).is_file():raise PatchError(f'缺少匹配的 genfs 策略：{candidate}')
            optional.append(candidate)
    names += [n for n in optional if rom.path(n).is_file()]
    return list(dict.fromkeys(names))

def compile_all(build):
    from policy_rules import catalog, filter_compilable, magisk_rules, select, symbols
    from policy_sources import UPSTREAM, adapt, context_evidence, ensure_contexts, stock_rules, upstream_delta
    compiler=Path(getattr(build,'policy_compiler',ASSETS/'native/secilc.exe'))
    if not compiler.is_file():raise PatchError('SELinux 编译器缺失，请保持工具完整：'+str(compiler))
    targets=[]
    for part in ('odm','vendor'):
        for suffix in ('','_debug'):
            name=f'{part}/etc/selinux/precompiled_sepolicy{suffix}'
            if build.rom.path(name).is_file():targets.append((name,bool(suffix)))
    if not targets:
        targets=[('odm/etc/selinux/precompiled_sepolicy',False)]
    jobs={}
    for name,debug in targets:
        old=build.rom.path(name)
        version=binary_version(old) if old.is_file() else 33
        if not 30<=version<=34:raise PatchError(f'尚未支持的策略格式版本：{version}')
        jobs[(debug,version)]=inputs(build,debug)
    # Always validate both fallback chains, including ROMs with only one cache.
    # inputs() falls back to normal CIL wherever a partition has no debug variant.
    for debug in (False,True):
        if not any(key[0]==debug for key in jobs):
            jobs[(debug,next(iter(jobs))[1])]=inputs(build,debug)
    original={n:read(build.rom.path(n)) for names in jobs.values() for n in names}
    vendor_names={n for n in original if re.fullmatch(r'vendor/etc/selinux/vendor_sepolicy(?:_debug)?\.cil',n)}
    stock_repeat={}
    sequence=0

    def compile_one(key, delta, phase):
        nonlocal sequence
        debug,version=key
        names=jobs[key]
        sequence+=1
        logname=f'policy-{phase}-{"debug" if debug else "normal"}-{version}-{sequence:03}.log'
        with tempfile.TemporaryDirectory(prefix='dolby_cil_') as temp:
            tmp=Path(temp)
            filenames=[]
            for i,n in enumerate(names):
                file=f'p{i:03}.cil'
                text=original[n]
                if delta is not None and n in vendor_names:
                    text=append_cil(text,delta+stock_repeat.get(n,''))
                write(tmp/file,text)
                filenames.append(file)
            command=[str(compiler),'-m','-M','true','-G','-N','-c',str(version),*filenames,
                     '-o','policy.bin','-f','file_contexts']
            flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
            process=subprocess.run(command,cwd=tmp,capture_output=True,timeout=180,creationflags=flags)
            log=(process.stdout+process.stderr).decode('utf-8',errors='replace')
            write(build.session/logname,'\n'.join(f'{f} = {n}' for f,n in zip(filenames,names))+'\n\n'+log)
            if process.returncode:
                # Only a normal, diagnosed CIL failure can enter optional-rule filtering.
                # Tool crashes, I/O issues and timeouts must abort, not delete permissions.
                if not semantic_failure(process.returncode,log):
                    raise PatchError(f'SELinux 编译器异常，停止而不筛规则：{log[-1800:]}\n{build.session/logname}')
                return None,dict(log=logname,branch='debug' if debug else 'normal',
                                 returncode=process.returncode,detail=log[-4000:])
            if not (tmp/'policy.bin').is_file() or binary_version(tmp/'policy.bin')!=version:
                raise PatchError('SELinux 编译输出缺失或格式错误；停止而不筛规则')
            return (tmp/'policy.bin').read_bytes(),None

    def required(key,delta,phase):
        data,error=compile_one(key,delta,phase)
        if error:
            raise PatchError(f'SELinux {phase} 编译失败（未修改 ROM，不删原规则/必要规则）：'
                             f'{error["detail"]}\n{build.session/error["log"]}')
        return data

    # Confirm the untouched ROM first. Never blame a pre-existing error on Dolby.
    for key in jobs:
        build.log(f'SELinux 原厂基线：{"debug" if key[0] else "normal"} / policy {key[1]}')
        required(key,None,'baseline')
    branches={f'{"debug" if key[0] else "normal"}-{key[1]}':symbols('\n'.join(original[n] for n in names))
              for key,names in jobs.items()}
    upstream=upstream_delta(branches)
    stock_by_file,stock_records=stock_rules(original)
    stock_by_key={key:[rule for name in names for rule in stock_by_file[name]] for key,names in jobs.items()}
    for name in vendor_names:
        consumers=[key for key,names in jobs.items() if name in names]
        common=set.intersection(*(set(stock_by_key[key]) for key in consumers))
        # Shared vendor CIL may be used by both branches: duplicate only their common
        # grants there. Branch-only originals remain intact and are exported separately.
        rules=[rule for rule in stock_by_key[consumers[0]] if rule in common]
        stock_repeat[name]='\n; Existing target-ROM Dolby/Codec2 grants (intentionally retained)\n'+'\n'.join(rules)+'\n'
    for key,rules in stock_by_key.items():
        label='debug' if key[0] else 'normal'
        write(build.session/f'stock-dolby-{label}-{key[1]}.cil',
              '; Existing target-ROM explicit Dolby/Codec2 allow rules; declarations remain in ROM.\n'+'\n'.join(rules)+'\n')
    save_json(build.session/'stock-dolby-reference.json',stock_records)
    contexts=ensure_contexts(build)
    shutil.copytree(ASSETS/'upstream-lunaris',build.session/'upstream-lunaris')
    save_json(build.session/'upstream-policy-report.json',dict(source=UPSTREAM,contexts=contexts,
              type_declarations='reuse existing required DMS types; create only missing hal_dms attributes',
              effective_rules='all expanded upstream grants are mandatory; no optional filtering'))
    essential=read(ASSETS/'dolby.cil').strip()+'\n\n; Pinned LunarisDolby upstream\n'+upstream
    for key in jobs:
        build.log(f'SELinux 必需规则 + Lunaris 上游 + 原厂重复授权：{"debug" if key[0] else "normal"}')
        required(key,essential,'essential')
    branches={f'{"debug" if key[0] else "normal"}-{key[1]}':symbols('\n'.join(original[n] for n in names)+upstream)
              for key,names in jobs.items()}
    adapted,remapped=adapt(catalog(),branches,context_evidence(build))
    candidates,skipped=select(adapted,branches)
    # Avoid identical rules in the required and optional sets (semantic redundancy is harmless).
    mandatory_lines=set(essential.splitlines())
    candidates=[r for r in candidates if r['cil'] not in mandatory_lines]
    audit=dict(baseline='compiled',essential='compiled',neverallow_assertions=False,
               stock_rules_removed=0,permissive_added=False,scope='Dolby compatibility grants, not AVC-proven minimum',
               note='编译筛选只证明新增规则可编译，不保证开机或杜比功能；缺类型不自动猜别名。',
               upstream=UPSTREAM,context_remapped=remapped,
               stock_grants={f'{"debug" if k[0] else "normal"}-{k[1]}':len(v) for k,v in stock_by_key.items()},
               candidates=len(candidates),not_applicable=skipped,accepted=[],compiler_rejected=[])
    save_json(build.session/'policy-rules-report.json',audit)

    def delta_for(rows):
        return essential+'\n\n; Target ROM adaptive Dolby compatibility grants\n'+'\n'.join(r['cil'] for r in rows)+'\n'

    def trial(rows):
        delta=delta_for(rows)
        if sequence>8 and sequence%8==0:
            build.log(f'SELinux 正在定位不兼容扩展；已执行 {sequence} 次编译')
        for key in jobs:
            _,error=compile_one(key,delta,'candidate')
            if error:return error
        return None

    build.log(f'SELinux 扩展：{len(candidates)} 条待编译，{len(skipped)} 条因目标类型/权限不适用跳过')
    accepted,rejected=filter_compilable(candidates,trial)
    audit.update(accepted=accepted,compiler_rejected=rejected)
    save_json(build.session/'policy-rules-report.json',audit)
    delta=delta_for(accepted)
    cache={}
    results=[]
    for key,names in jobs.items():
        cache[key]=required(key,delta,'final')
        debug,version=key
        results.append(dict(debug=debug,policy_version=version,inputs=names,neverallow_assertions=False,
                            baseline='compiled',essential='compiled',optional_accepted=len(accepted),
                            optional_rejected=len(rejected),optional_not_applicable=len(skipped),
                            result='compiled',compiler='SELinuxProject 3.9 + upstream policycaps + Android netlink flags / MinGW x64'))
    for name in vendor_names:
        exported=delta+stock_repeat[name]
        build.stage(name,append_cil(original[name],exported).encode())
        suffix='-debug' if name.endswith('_debug.cil') else ''
        write(build.session/f'dolby{suffix}.cil',exported)
        write(build.session/('sepolicy-debug.rule' if suffix else 'sepolicy.rule'),magisk_rules(exported))
    build.log(f'SELinux 完成：保留 {len(accepted)} 条扩展，编译筛出 {len(rejected)} 条；原厂规则未删')
    if rejected:
        build.notes.append(f'SELinux 有 {len(rejected)} 条扩展未通过编译，详见 policy-rules-report.json；需真机验证相关功能')
    for name,debug in targets:
        old=build.rom.path(name)
        version=binary_version(old) if old.is_file() else 33
        key=(debug,version)
        # Preserve the input ROM's exact per-file label when it exists.
        label='u:object_r:sepolicy_file:s0' if not debug else 'u:object_r:vendor_configs_file:s0'
        if getattr(build,'require_metadata',True) and old.is_file():
            label=build.rom.existing_file_label(name)
        build.stage(name,cache[key],label=label)
    # A vendor CIL change doesn't alter framework mapping digest inputs.
    # Preserve each existing sidecar verbatim; both cached and fallback CIL now include the delta.
    save_json(build.session/'policy-report.json',results)
