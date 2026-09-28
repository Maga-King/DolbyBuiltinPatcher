"""Module-only text rule export; never compile or replace the ROM policy."""
import shutil
from core import ASSETS, read, save_json, write
from policy import inputs
from policy_rules import catalog, magisk_rules, select, symbols
from policy_sources import (UPSTREAM, adapt, context_evidence, ensure_contexts,
                            stock_rules, upstream_delta)


def export_rules(build):
    # A module runs against the normal policy. Do not lift debug-only/conditional
    # rules into the normal live policy or copy a ROM's entire policy database.
    original={name:read(build.rom.path(name)) for name in inputs(build,False)}
    branches={'normal':symbols('\n'.join(original.values()))}
    upstream=upstream_delta(branches)
    branches={'normal':symbols('\n'.join(original.values())+'\n'+upstream)}
    rows,remapped=adapt(catalog(),branches,context_evidence(build))
    _,unresolved=select(rows,branches)  # report only; keep the full Dolby catalog
    stock,reference=stock_rules(original)
    delta=read(ASSETS/'dolby.cil').strip()+'\n'+upstream+'\n'
    delta+='\n; Complete Dolby compatibility catalog; NOT compiler-filtered\n'
    delta+='\n'.join(row['cil'] for row in rows)+'\n'
    delta+='\n; Existing normal-policy top-level Dolby grants\n'
    delta+='\n'.join(rule for group in stock.values() for rule in group)+'\n'
    rule=magisk_rules(delta)
    rule='# Dolby module rules; NOT compiled; injection success is NOT a boot safety guarantee.\n'+ '\n'.join(rule.splitlines()[1:])+'\n'
    contexts=ensure_contexts(build)
    shutil.copytree(ASSETS/'upstream-lunaris',build.session/'upstream-lunaris')
    write(build.session/'dolby.cil',delta)
    write(build.session/'sepolicy.rule',rule)
    save_json(build.session/'stock-dolby-reference.json',reference)
    save_json(build.session/'policy-rules-report.json',dict(mode='module-text-rules',compiled=False,
        upstream=UPSTREAM,catalog_count=len(rows),context_remapped=remapped,contexts=contexts,
        unresolved_but_included=unresolved,compiler_rejected=[],stock_policy_modified=False,
        boot_safety_guaranteed=False))
    build.log(f'模块 SELinux：直接导出完整杜比规则集 {len(rows)} 条扩展，不调用策略编译器；'
              f'{len(unresolved)} 条目标声明不匹配仍保留并记录，注入与开机效果需实测')
