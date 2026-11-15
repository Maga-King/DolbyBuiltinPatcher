"""Discover configuration from ROM content, not device codenames."""
from pathlib import PurePosixPath
import re
from core import PatchError, xml_parse


def include_candidates(name,href):
    relative=str(PurePosixPath(name).parent/href)
    # A local missing C2 audio leaf must not be hidden by an old SKU's root
    # copy. Android resolves Include relative to the current XML directory.
    if href=='media_codecs_c2_audio.xml':return [relative]
    return list(dict.fromkeys([relative,name.split('/')[0]+'/etc/'+href]))


def discover(rom):
    hals=[n for n in ('vendor/lib64/hw/libaudioeffecthal.qti.so',
                      'vendor/lib64/libaudioeffecthal.qti.so') if rom.path(n).is_file()]
    if not hals:raise PatchError('没有 Qualcomm AIDL 音效 HAL；当前二进制资产不支持这个后端')
    names=set()
    for name in hals:
        data=rom.path(name).read_bytes()
        if data[:5]!=b'\x7fELF\x02' or data[18:20]!=b'\xb7\x00':
            raise PatchError(f'音效 HAL 不是 ARM64 ELF：{name}')
        names.update(s.decode('ascii') for s in re.findall(rb'audio_effects[\w.-]*\.xml',data))
    if not names:raise PatchError('无法从原厂音效 HAL 确认配置文件名，需为此后端增加配置定位规则')
    effects=[];ignored=[];docs={};edges={}
    for part in ('vendor','odm'):
        for path in sorted((rom.parts[part]/'etc').rglob('*.xml')):
            canonical=part+'/'+path.relative_to(rom.parts[part]).as_posix()
            is_effect=path.name in names
            is_codec=path.name.startswith('media_codecs') and 'performance' not in path.name
            if not (is_effect or is_codec):continue
            data=path.read_bytes()
            if data.startswith(b'!<symlink>') or path.is_symlink():
                raise PatchError(f'音频 XML 是未展开的符号链接，需先解出实际文件：{canonical}')
            try:root=xml_parse(data)
            except Exception as e:raise PatchError(f'音频 XML 解析失败：{canonical}：{e}') from e
            tag=root.tag.split('}')[-1]
            if is_effect:
                if tag!='audio_effects_conf' or root.find('{*}libraries') is None or root.find('{*}effects') is None:
                    raise PatchError(f'HAL 引用的配置结构尚不支持：{canonical}')
                effects.append(canonical)
            if is_codec and tag in ('MediaCodecs','Included'):docs[canonical]=root
    if not effects:raise PatchError('未找到 HAL 引用的有效音效 XML：'+', '.join(sorted(names)))
    # Includes may use arbitrary filenames; follow them before classifying the graph.
    pending=list(docs)
    visited=set()
    while pending:
        name=pending.pop()
        if name in visited:continue
        visited.add(name)
        for node in docs[name].findall('Include'):
            href=node.get('href','')
            if not href or PurePosixPath(href).is_absolute() or '..' in PurePosixPath(href).parts:
                raise PatchError(f'无法解析的 Codec Include：{name} -> {href}')
            for candidate in include_candidates(name,href):
                if candidate in docs:break
                path=rom.path(candidate)
                if not path.is_file():continue
                data=path.read_bytes()
                if data.startswith(b'!<symlink>') or path.is_symlink():
                    raise PatchError(f'Codec Include 是未展开的链接：{candidate}')
                root=xml_parse(data)
                if root.tag not in ('MediaCodecs','Included'):
                    raise PatchError(f'Codec Include 根节点不受支持：{candidate}')
                docs[candidate]=root;pending.append(candidate);break
    # Resolve Include relative to its source, then the partition's etc search root.
    unresolved=[]
    for name,root in docs.items():
        edges[name]=[]
        for node in root.findall('Include'):
            href=node.get('href','')
            if not href or PurePosixPath(href).is_absolute() or '..' in PurePosixPath(href).parts:
                raise PatchError(f'无法解析的 Codec Include：{name} -> {href}')
            candidates=include_candidates(name,href)
            found=next((n for n in candidates if n in docs),None)
            if not found:
                unresolved.append({'from':name,'href':href});continue
            edges[name].append(found)
    def reachable(name,ancestors=()):
        if name in ancestors:raise PatchError('Codec Include 出现循环：'+' -> '.join((*ancestors,name)))
        result={name}
        for child in edges[name]:result.update(reachable(child,(*ancestors,name)))
        return result
    reach={n:reachable(n) for n in docs}
    def c2_audio(root):
        for n in root.findall('./Decoders/MediaCodec'):
            if not n.get('name','').startswith('c2.') or n.get('name','').startswith('c2.android.'):
                continue
            if n.get('type','').startswith('audio/') or any(t.get('name','').startswith('audio/') for t in n.findall('Type')):
                return True
        return False
    # New Qualcomm layouts may remove the QTI C2 audio service and its XML,
    # while retaining the Include in each video entry. Repair only that proven
    # dangling edge. Never copy old QTI components or fall back on any error.
    created={}
    for item in unresolved:
        name,href=item['from'],item['href']
        root=docs[name]
        if href!='media_codecs_c2_audio.xml' or root.tag!='MediaCodecs':continue
        video=any(n.get('name','').startswith('c2.qti.') and
                  (n.get('type','').startswith('video/') or
                   any(t.get('name','').startswith('video/') for t in n.findall('Type')))
                  for n in root.findall('./Decoders/MediaCodec'))
        audio=any(n.get('name','').startswith(('c2.android.','OMX.google.')) and
                  (n.get('type','').startswith('audio/') or
                   any(t.get('name','').startswith('audio/') for t in n.findall('Type')))
                  for child in reach[name] for n in docs[child].findall('./Decoders/MediaCodec'))
        if not video or not audio:continue
        # Android's Include parser resolves relative to the including file.
        target=str(PurePosixPath(name).parent/href)
        path=rom.path(target)
        if path.exists() or path.is_symlink():
            raise PatchError('缺失 Codec 叶节点的目标不是可新建文件：'+target)
        created.setdefault(target,[]).append(name)
    if created:
        for target in created:
            docs[target]=xml_parse(b'<Included><Decoders/></Included>')
            edges[target]=[]
        remaining=[]
        for item in unresolved:
            target=str(PurePosixPath(item['from']).parent/item['href'])
            if target in created:
                edges[item['from']].append(target)
            else:remaining.append(item)
        unresolved=remaining
        reach={n:reachable(n) for n in docs}
    candidates={n for n,r in docs.items() if c2_audio(r)}
    candidates.update(created)
    incoming={n for values in edges.values() for n in values}
    # Each non-included entry tree is a possible boot-selected platform configuration.
    roots=sorted(n for n in docs if n not in incoming and any(c in reach[n] for c in candidates))
    if not roots:
        raise PatchError('没有找到包含厂商 Codec2 音频解码器的配置引用链；'
                         '也不符合“高通视频入口 + Google 音频 + 缺失 C2 音频 Include”的新版结构，未套用补丁')
    selected=set();coverage={}
    for root in sorted(roots,key=lambda n:(sum(c in reach[n] for c in candidates),n)):
        present=selected & reach[root]
        if len(present)>1:raise PatchError(f'配置链存在多处候选，可能重复注册：{root}')
        if present:continue
        options=candidates & reach[root]
        # Prefer a shared audio leaf. Do not select another node inside an already covered tree.
        options={c for c in options if all(not (selected & reach[r]) or c not in reach[r] for r in roots)}
        if not options:raise PatchError(f'无法为 Codec 引用链选择无重复的插入位置：{root}')
        best=max(sorted(options),key=lambda c:(sum(c in reach[r] for r in roots),not edges[c],len(c)))
        selected.add(best)
    # Every repaired Include must receive a real file, and only the selected
    # insertion sites may contain Dolby entries. Ambiguous mixed trees fail.
    if set(created)-selected:
        raise PatchError('新版 Codec 叶节点与已有插入点冲突：'+', '.join(sorted(set(created)-selected)))
    for root in roots:
        matched=sorted(selected & reach[root])
        if len(matched)!=1:raise PatchError(f'Codec 引用链覆盖异常：{root}')
        existing_dolby={n for n in reach[root] if any(
            c.get('name','').startswith('c2.dolby.') for c in docs[n].findall('./Decoders/MediaCodec'))}
        if existing_dolby-set(matched):
            raise PatchError('Codec 引用链其他位置已有杜比，拒绝重复添加：'+root+' -> '+
                             ', '.join(sorted(existing_dolby-set(matched))))
        # A DAG may include the same selected leaf twice; set reachability alone hides this.
        def occurrences(n,target):return int(n==target)+sum(occurrences(x,target) for x in edges[n])
        if occurrences(root,matched[0])!=1:raise PatchError(f'原配置重复包含音频叶节点：{root} -> {matched[0]}')
        coverage[root]=matched[0]
    for item in unresolved:
        if any(item['from'] in reach[r] for r in roots):
            raise PatchError(f'Codec 引用链缺件，不能确认是否重复注册：{item["from"]} -> {item["href"]}')
    profiles={root:('dolby-only-missing-c2-audio' if leaf in created else 'vendor-c2-audio')
              for root,leaf in coverage.items()}
    return dict(effect_hals=hals,effect_filenames=sorted(names),effects=effects,
                codecs=sorted(selected),codec_entry_coverage=coverage,
                codec_entry_profiles=profiles,codec_created_files=sorted(created),
                codec_repairs=[dict(path=n,reason='dangling-qti-c2-audio-include',
                                    referenced_by=sorted(set(created[n])),contents='c2.dolby.* only')
                               for n in sorted(created)],
                unresolved_unrelated_includes=unresolved)
