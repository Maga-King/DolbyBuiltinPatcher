"""Read-only verification of two ROM layouts and their generated outputs.

No hashes, device access, image unpacking or writes to either ROM.
"""
import argparse
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import Rom
from discovery import discover

DOLBY={'c2.dolby.eac3.decoder','c2.dolby.ac4.decoder'}


def signature(node):
    return (node.tag,sorted(node.attrib.items()),(node.text or '').strip(),
            [signature(n) for n in node if isinstance(n.tag,str)])


def check(rom_path,module_path,native_path,new):
    rom=Rom(rom_path)
    info=discover(rom)
    assert bool(info['codec_created_files'])==new,info
    assert len(info['codecs'])==1,info
    target=info['codecs'][0]
    native=Path(native_path)
    relative=rom.rel(target)
    with zipfile.ZipFile(module_path) as archive:
        payload=archive.read('system/'+target)
        root=ET.fromstring(payload)
        codecs=root.findall('./Decoders/MediaCodec')
        dolby=[n.get('name') for n in codecs if n.get('name','').startswith('c2.dolby.')]
        assert len(dolby)==2 and set(dolby)==DOLBY,dolby
        assert payload==(native/'patch_tree'/relative).read_bytes(),'Native/module XML differs'
        assert not {'skip_mount','skip_mountify'} & set(archive.namelist())
        assert '/system/bin/sh "$MODPATH/freeze-audioeffectcenter.sh"' in archive.read('install-early.sh').decode()
        assert '. "$MODPATH/install-early.sh"' in archive.read('customize.sh').decode()
        labels=archive.read('labels.tsv').decode().splitlines()
        assert 'system/'+target+'\t0644\tu:object_r:vendor_configs_file:s0' in labels
        manifest=json.loads(archive.read('module-report.json'))
        assert manifest['rom_info']['configuration']==info
    fs=(native/'patch_tree/config/vendor_fs_config').read_text(encoding='utf-8').splitlines()
    contexts=(native/'patch_tree/config/vendor_file_contexts').read_text(encoding='utf-8').splitlines()
    assert target+' 0 0 0644' in fs
    assert '/'+target.replace('.','\\.')+' u:object_r:vendor_configs_file:s0' in contexts
    if new:
        assert len(codecs)==2
        assert root.find('Encoders') is None
        assert not rom.path(target).exists(),'New source ROM was modified'
    else:
        before=ET.fromstring(rom.path(target).read_bytes())
        for node in list(root.find('Decoders')):
            if node.get('name','').startswith('c2.dolby.'):root.find('Decoders').remove(node)
        assert signature(before)==signature(root),'Original codec settings changed'
    return dict(rom=str(rom_path),profile='new' if new else 'old',entry_count=len(info['codec_entry_coverage']),
                decoder_count=len(codecs),module_native_equal=True,packing_label='vendor_configs_file',
                source_readonly=True,boot_tested=False)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for kind in ('new','old'):
        for item in ('rom','module','native'):parser.add_argument('--'+kind+'-'+item,required=True)
    args=parser.parse_args()
    output=[check(getattr(args,k+'_rom'),getattr(args,k+'_module'),getattr(args,k+'_native'),k=='new')
            for k in ('new','old')]
    print(json.dumps(output,ensure_ascii=False,indent=2))
