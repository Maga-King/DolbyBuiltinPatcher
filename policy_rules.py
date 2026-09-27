"""Auditable Dolby-only compatibility grants; the compiler remains authoritative."""
import re


def symbols(text):
    # Ignore comments and quoted strings (e.g. paths); only index declarations.
    text = re.sub(r'"(?:\\.|[^"\\])*"|;[^\n]*', '', text)
    types = set(re.findall(r'\((?:type|typeattribute|typealias)\s+([^\s()]+)\s*\)', text))
    commons = {n: set(p.split()) for n, p in re.findall(r'\(common\s+(\S+)\s+\(([^()]*)\)\s*\)', text)}
    classes = {n: set(p.split()) for n, p in re.findall(r'\(class\s+(\S+)\s+\(([^()]*)\)\s*\)', text)}
    for cls, common in re.findall(r'\(classcommon\s+(\S+)\s+([^\s()]+)\s*\)', text):
        classes.setdefault(cls, set()).update(commons.get(common, set()))
    return types, classes


def catalog():
    rows = []
    seen = set()

    def allow(group, src, dst, cls, perms):
        key = (src, dst, cls, tuple(sorted(perms.split())))
        if key in seen:
            return
        seen.add(key)
        rows.append(dict(group=group, source=src, target=dst, object_class=cls,
                         permissions=perms.split(), cil=f'(allow {src} {dst} ({cls} ({perms})))'))

    def binder(group, a, b):
        # Transactions, callback handles and passed descriptors, not access to peer files.
        for src, dst in ((a, b), (b, a)):
            allow(group, src, dst, 'binder', 'call transfer')
            allow(group, src, dst, 'fd', 'use')

    dms = ('hal_dms_default', 'hal_aidl_dms_default')
    servers = (*dms, 'mediacodec')
    clients = ('audioserver', 'hal_audio_default', 'system_server', 'mediaserver',
               'mediacodec', 'priv_app', 'platform_app', 'system_app')
    dirs = 'search getattr open read'
    files = 'read open getattr map'
    for domain in servers:
        for manager in ('servicemanager', 'hwservicemanager'):
            binder('service-discovery', domain, manager)
            # Service-manager SID inspection, as in binder_use/hwbinder_use macros.
            allow('service-discovery', manager, domain, 'dir', 'search read open getattr')
            allow('service-discovery', manager, domain, 'file', 'read open getattr map')
            allow('service-discovery', manager, domain, 'process', 'getattr')
        for device in ('binder_device', 'hwbinder_device', 'vndbinder_device'):
            allow('binder-devices', domain, device, 'chr_file', 'read write open getattr ioctl map')
        for label in ('system_file', 'system_lib_file', 'vendor_file', 'same_process_hal_file'):
            allow('libraries', domain, label, 'dir', dirs)
            allow('libraries', domain, label, 'file', files + ' execute')
            allow('libraries', domain, label, 'lnk_file', 'read getattr')
        for label in ('vendor_configs_file', 'system_configs_file'):
            allow('configuration', domain, label, 'dir', dirs)
            allow('configuration', domain, label, 'file', files)
            allow('configuration', domain, label, 'lnk_file', 'read getattr')
        # Read selected audio properties only; no global property write access.
        for label in ('audio_prop', 'vendor_audio_prop', 'vendor_dolby_prop', 'dolby_prop',
                      'media_config_prop', 'hwservicemanager_prop', 'servicemanager_prop'):
            allow('property-read', domain, label, 'file', files)
        allow('logging', domain, domain, 'unix_dgram_socket', 'create connect write getattr getopt setopt')
        allow('logging', domain, 'logdw_socket', 'sock_file', 'write')
        allow('logging', domain, 'logd', 'unix_dgram_socket', 'sendto')
        for label in ('null_device', 'zero_device', 'ashmem_device'):
            allow('runtime-memory', domain, label, 'chr_file', 'read write open getattr ioctl map')
        allow('runtime-memory', domain, 'urandom_device', 'chr_file', 'read open getattr')
        allow('runtime-memory', domain, domain, 'memfd_file', 'create read write open getattr setattr map ioctl lock')
        # Inherit init limits/signals and report child exit. Keep actual transitions essential.
        allow('init-transition', domain, 'init', 'process', 'sigchld')
        allow('init-transition', domain, 'init', 'fd', 'use')
        allow('init-transition', 'init', domain, 'process', 'siginh rlimitinh')

    for domain in dms:
        for client in clients:
            binder('dms-audio-clients', client, domain)
        # Existing payload stores profiles in /data/vendor, not arbitrary app data.
        allow('profile-storage', domain, 'vendor_data_file', 'dir',
              'create search read open getattr setattr write add_name remove_name rmdir')
        allow('profile-storage', domain, 'vendor_data_file', 'file',
              'create read open getattr setattr write append map lock rename unlink')
        allow('profile-storage', domain, 'vendor_data_file', 'lnk_file', 'read getattr')
    binder('hidl-aidl-bridge', dms[0], dms[1])
    for client in (*clients, *dms):
        allow('dms-discovery', client, 'hal_dms_hwservice', 'hwservice_manager', 'find')
        allow('dms-discovery', client, 'hal_aidl_dms_service', 'service_manager', 'find')
    allow('dms-discovery', dms[0], 'hidl_base_hwservice', 'hwservice_manager', 'add')
    for client in ('audioserver', 'mediaserver', 'mediaextractor', 'system_server', 'platform_app', 'priv_app'):
        allow('codec-discovery', client, 'hal_codec2_service', 'service_manager', 'find')
        binder('codec-clients', client, 'mediacodec')
    for domain in (*dms, 'mediacodec'):
        allow('audio-discovery', domain, 'audioserver_service', 'service_manager', 'find')
        allow('audio-discovery', domain, 'hal_audio_service', 'service_manager', 'find')
        allow('audio-discovery', domain, 'hal_audio_hwservice', 'hwservice_manager', 'find')
    for domain in ('hal_audio_default', 'audioserver'):
        for label in ('system_lib_file', 'vendor_file', 'same_process_hal_file'):
            allow('dap-loading', domain, label, 'dir', dirs)
            allow('dap-loading', domain, label, 'file', files + ' execute')
        allow('dap-loading', domain, 'vendor_configs_file', 'dir', dirs)
        allow('dap-loading', domain, 'vendor_configs_file', 'file', files)
    return rows


def select(rows, branches):
    """Use a common delta compatible with every normal/debug input chain."""
    accepted, skipped = [], []
    for row in rows:
        reasons = []
        for branch, (types, classes) in branches.items():
            missing = sorted({row['source'], row['target']} - types)
            cls = row['object_class']
            perms = sorted(set(row['permissions']) - classes.get(cls, set()))
            if missing or cls not in classes or perms:
                reasons.append(dict(branch=branch, missing_types=missing,
                                    missing_class=cls if cls not in classes else None, missing_permissions=perms))
        if reasons:
            skipped.append({**row, 'status': 'not-applicable', 'reasons': reasons})
        else:
            accepted.append(row)
    return accepted, skipped


def filter_compilable(rows, trial):
    """Keep all compilable optional grants; never modify mandatory/original rules.

    trial returns None on success or an auditable diagnostic record on semantic
    failure, and must raise on compiler crashes, missing tools, timeouts and I/O.
    Recheck the accepted prefix before rejecting a singleton (not a transient fault).
    """
    accepted, rejected = [], []

    def visit(chunk):
        error = trial(accepted + chunk)
        if error is None:
            accepted.extend(chunk)
        elif len(chunk) == 1:
            if trial(accepted) is not None:
                raise RuntimeError('SELinux 编译器基线复查失败；不能归因于新增规则，停止筛选')
            rejected.append({**chunk[0], 'status': 'compiler-rejected', 'diagnostic': error})
        else:
            mid = len(chunk) // 2
            visit(chunk[:mid])
            visit(chunk[mid:])

    if rows:
        visit(rows)
    return accepted, rejected


def magisk_rules(delta):
    """Export only our known CIL delta syntax, never translate arbitrary stock CIL."""
    from policy_sources import forms
    out = ['# Target-ROM-specific Dolby delta; neverallow checks disabled at build time.']
    for _,form in forms(delta):
        line = re.sub(r'\s+',' ',form).strip()
        allow = re.fullmatch(r'\((allow|dontaudit) (\S+) (\S+) \((\S+) \(([^()]+)\)\)\)', line)
        transition = re.fullmatch(r'\(typetransition (\S+) (\S+) (\S+) (\S+)\)', line)
        attribute = re.fullmatch(r'\(typeattribute (\S+)\)',line)
        membership = re.fullmatch(r'\(typeattributeset (\S+) \(([^()]+)\)\)',line)
        if allow:
            action, src, dst, cls, perms = allow.groups()
            out.append(f'{action} {src} {dst} {cls} {{ {perms.strip()} }}')
        elif transition:
            out.append('type_transition ' + ' '.join(transition.groups()))
        elif attribute:
            out.append('attribute '+attribute.group(1))
        elif membership:
            attr,members=membership.groups()
            out.extend(f'typeattribute {member} {attr}' for member in members.split())
        else:
            raise ValueError('Unsupported generated Dolby CIL: ' + line)
    return '\n'.join(out) + '\n'
