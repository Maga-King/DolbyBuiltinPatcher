"""Pinned upstream grants, target-context adaptation and stock Dolby rule exports."""
import json
import re
from core import ASSETS, BEGIN, END, PatchError, read

UPSTREAM='https://github.com/Pong-Development/hardware_dolby/tree/6300a4e30757d5810d62b2df0cff973ec438a70f/sepolicy/vendor'


def forms(text):
    """Yield complete top-level CIL forms; do not lift rules out of conditionals."""
    depth=0;start=0;line=1;startline=1;previous=0
    for match in re.finditer(r'"(?:\\.|[^"\\])*"|;[^\n]*|[()]',text):
        token=match.group()
        line+=text.count('\n',previous,match.start())
        if token=='(':
            if depth==0:start=match.start();startline=line
            depth+=1
        elif token==')':
            depth-=1
            if depth==0:yield startline,text[start:match.end()]
        line+=token.count('\n');previous=match.end()


def stock_rules(original):
    """Retain explicit DMS/Dolby/Codec2 statements with their original provenance.

    Shared base-domain policy remains in the untouched ROM, not a stand-alone policy.
    Only duplicate existing top-level allow rules in the injected/exported delta.
    Other statements (including type declarations/neverallows) are archived verbatim.
    """
    relevant=re.compile(r'\b(?:hal_(?:aidl_)?dms(?:_\w+)?|mediacodec(?:_\w+)?|hal_codec2(?:_\w+)?|\w*dolby(?:_\w+)?)\b')
    records=[];by_file={}
    for name,text in original.items():
        # An earlier tool-generated block is not an original ROM permission source.
        text=re.sub(re.escape(BEGIN)+r'.*?'+re.escape(END),'',text,flags=re.S)
        grants=[]
        for line,form in forms(text):
            if not relevant.search(form):continue
            record=dict(file=name,line=line,cil=form)
            records.append(record)
            if re.fullmatch(r'\(allow\s+[^\s()]+\s+[^\s()]+\s+\([^()]+\([^()]+\)\s*\)\s*\)',form):
                grants.append(form)
        by_file[name]=grants
    return by_file,records


def upstream_delta(branches):
    declarations=[]
    for name in ('hal_dms','hal_dms_client','hal_dms_server'):
        present=[name in types for types,_ in branches.values()]
        if not any(present):declarations.append(f'(typeattribute {name})')
        elif not all(present):
            raise PatchError(f'上游属性 {name} 在普通/debug 分支声明不一致，需单独适配，不能重复硬声明')
    return '\n'.join(declarations)+'\n'+read(ASSETS/'upstream-lunaris/expanded.cil')


def context_evidence(build):
    evidence={'system_configs_file':[], 'urandom_device':[], 'dolby_prop':[], 'vendor_dolby_prop':[]}
    # Use the labels actually assigned to this tool's system-side config assets.
    for row in json.loads(read(ASSETS/'payload.json')):
        path=row['canonical']
        if path.startswith(('system/etc/','system_ext/etc/')) and '/init/' not in path:
            evidence['system_configs_file'].append(dict(target=row['SELinux'].split(':')[2],
                file='assets/payload.json',entry=path,reason='actual system-side configuration asset label'))
    for part,base in build.rom.parts.items():
        directory=base/'etc/selinux'
        for path in sorted(directory.glob('*_contexts')):
            if path.name.endswith('property_contexts'):
                for line in read(path).splitlines():
                    fields=line.split()
                    if len(fields)<2 or fields[0].startswith('#'):continue
                    if not re.search(r'(?:^|\.)(dolby|dax)(?:\.|$)',fields[0]):continue
                    if not fields[1].startswith('u:object_r:'):continue
                    item=dict(target=fields[1].split(':')[2],file=part+'/etc/selinux/'+path.name,
                              entry=line,reason='actual Dolby audio property context (not Dolby Vision)')
                    evidence['dolby_prop'].append(item)
                    if re.search(r'(?:^|\.)vendor\.',fields[0]):evidence['vendor_dolby_prop'].append(item)
            elif path.name.endswith('file_contexts'):
                for line in read(path).splitlines():
                    fields=line.split()
                    if fields and fields[0]=='/dev/urandom' and fields[-1].startswith('u:object_r:'):
                        evidence['urandom_device'].append(dict(target=fields[-1].split(':')[2],
                            file=part+'/etc/selinux/'+path.name,entry=line,reason='actual /dev/urandom label'))
    return evidence


def adapt(rows,branches,evidence):
    """Retarget absent candidate names to evidenced labels, never invent empty types."""
    result=[];remapped=[]
    common=set.intersection(*(types for types,_ in branches.values()))
    for row in rows:
        name=row['target']
        if name in common or name not in evidence:
            result.append(row);continue
        matches=[e for e in evidence[name] if e['target'] in common]
        labels=sorted({e['target'] for e in matches})
        if not labels:
            result.append(row);continue
        adapted=[]
        for label in labels:
            cil=f'(allow {row["source"]} {label} ({row["object_class"]} ({" ".join(row["permissions"])})))'
            new={**row,'target':label,'cil':cil,'adapted_from':row['cil'],
                 'evidence':[e for e in matches if e['target']==label]}
            result.append(new);adapted.append(cil)
        remapped.append(dict(original=row['cil'],replacements=adapted,evidence=matches))
    return result,remapped


def ensure_contexts(build):
    # Keep runtime labels aligned with the upstream rules and current payload paths.
    additions={
        'vendor/etc/selinux/vendor_hwservice_contexts':[
            ('vendor.dolby.hardware.dms::IDms','u:object_r:hal_dms_hwservice:s0')],
        'vendor/etc/selinux/vendor_service_contexts':[
            ('vendor.dolby.dms.IDms/default','u:object_r:hal_aidl_dms_service:s0')],
        'vendor/etc/selinux/vendor_file_contexts':[
            (r'/data/vendor/dolby(/.*)?','u:object_r:vendor_data_file:s0'),
            (r'/vendor/bin/hw/vendor\.dolby\.hardware\.dms@2\.0-service','u:object_r:hal_dms_default_exec:s0')],
    }
    records=[]
    for name,entries in additions.items():
        path=build.get(name)
        if not path.is_file():raise PatchError(f'缺少运行时 SELinux contexts：{name}')
        text=read(path);updated=text
        for key,label in entries:
            existing=[line.split() for line in text.splitlines() if line.split() and line.split()[0]==key]
            if any(fields[-1]!=label for fields in existing):
                raise PatchError(f'现有标签与杜比域不一致，不能盲目覆盖：{name} {key}')
            if not existing:updated=updated.rstrip()+'\n'+key+' '+label+'\n'
            records.append(dict(file=name,entry=key+' '+label,action='already-present' if existing else 'added'))
        if updated!=text:build.stage(name,updated.encode())
    return records
