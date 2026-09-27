"""Library-name dependency checks. This is not a proof of linker namespace/ABI compatibility."""
import io
import json
import zipfile
from elftools.elf.elffile import ELFFile
from core import ASSETS, PatchError, save_json

def audit(build):
    rows=json.loads((ASSETS/'payload.json').read_text(encoding='utf-8'))
    embedded={r['canonical'].rsplit('/',1)[-1] for r in rows}
    inventory=getattr(build,'library_inventory',None)
    inventory_source='selected ADB ROM directory listing' if inventory is not None else 'local ROM directory listing'
    if inventory is None:
        inventory={}
        for part,root in build.rom.parts.items():
            for directory in (root/'lib64',root/'apex'):
                if not directory.is_dir():continue
                for p in directory.rglob('*.so'):
                    inventory.setdefault(p.name,[]).append(str(p.relative_to(build.rom.root)))
    # Bionic libraries can be hidden inside binary APEX containers, rather than extracted directories.
    bionic={'libc.so','libm.so','libdl.so'}
    report=[];missing={}
    with zipfile.ZipFile(ASSETS/'payload.zip') as z:
        for row in rows:
            name=row['canonical'];data=z.read(name)
            if not data.startswith(b'\x7fELF'):continue
            elf=ELFFile(io.BytesIO(data))
            if elf.elfclass!=64 or elf['e_machine']!='EM_AARCH64':
                raise PatchError('内置资产不是 ARM64 ELF：'+name)
            dynamic=elf.get_section_by_name('.dynamic')
            needed=[]
            if dynamic:
                for tag in dynamic.iter_tags():
                    if tag.entry.d_tag=='DT_NEEDED':needed.append(tag.needed)
            unresolved=[n for n in needed if n not in embedded and n not in inventory and n not in bionic]
            if unresolved:missing[name]=unresolved
            report.append({'file':name,'needed':needed,'missing_names':unresolved})
    save_json(build.session/'dependency-report.json',{
        'kind':'ELF dependency filename presence, NOT symbol or namespace compatibility',
        'inventory_source':inventory_source,
        'bionic_apex_assumed':sorted(bionic),'files':report,'missing':missing})
    if missing:
        lines=[name+' -> '+', '.join(deps) for name,deps in missing.items()]
        raise PatchError('目标 ROM 缺少杜比依赖库；不能直接套用当前资产：\n'+'\n'.join(lines[:12]))
