# Shared module-only boot packaging for desktop and Android.
"""Early module-only boot packaging. Does not change native ROM patching."""
import re
from core import ASSETS, PatchError, read

RUNTIME_VERSION='0.6.7-permissions'
BIND_KEYS=('ro.system.build.fingerprint','ro.vendor.build.fingerprint','ro.board.platform')


def validate_codec_recovery(rc):
    """Reject regressions before exporting a module; never used by native builds."""
    sections=re.findall(r'^service\s+mio-dolby-codec\s+([^\n]+)\n((?:[ \t]+[^\n]*\n|\n)*)',rc+'\n',re.M)
    if len(sections)!=1:
        raise PatchError('模块必须有且只有一个 Dolby Codec2 init 服务')
    executable,body=sections[0]
    options=[line.strip() for line in body.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    required={'disabled','interface aidl android.hardware.media.c2.IComponentStore/default9','restart_period 3'}
    if executable.strip()!='/system_ext/bin/hw/dolbycodecservice' or not required.issubset(options):
        raise PatchError('解码服务缺少显式启动配置、default9 接口映射或恢复间隔，拒绝出包')
    if any(line.split()[0] in ('oneshot','critical','reboot_on_failure','onrestart') for line in options):
        raise PatchError('解码服务含不安全的退出/重启选项，拒绝出包')


def target_bindings(build):
    # Stable packaging API; no install/runtime identity pinning.
    return {}


def export_boot(put,vintf,mounted,bindings):
    runtime_rc=read(ASSETS/'ksu/boot/init.rc')
    validate_codec_recovery(runtime_rc)
    # Publish the complete manifest before service managers cache declarations.
    # There is no second Codec2 declaration, APEX refresh, or audio commit phase.
    put('early/vintf.tsv',''.join('\t'.join(row)+'\n' for row in vintf).encode())
    put('early/target.tsv',''.join(k+'\t'+v+'\n' for k,v in bindings.items()).encode())
    put('early/early.sh',(ASSETS/'ksu/boot/early.sh').read_bytes(),'0755')
    put('initrc/dolby.rc',runtime_rc.encode())
    for name in ('prepare-data.sh','storage-access.sh','service.sh','install-early.sh','uninstall.sh','initrc-cache.sh','runtime-paths.sh','mount-engine.sh','preserve.sh','repair-mounts.sh','install-app.sh','freeze-audioeffectcenter.sh'):
        put(name,(ASSETS/'ksu/boot'/name).read_bytes(),'0755')
    for stage in ('post-fs-data.sh','post-mount.sh'):
        put(stage,(ASSETS/'ksu'/stage).read_bytes(),'0755')
    # Only search boundaries: runtime walks down these payload branches to
    # discover minimal publication targets (offline snapshots omit directories).
    roots=sorted({'/'+target.strip('/').split('/')[0]+'/'+target.strip('/').split('/')[1] for _,target,_ in mounted})
    if any(not re.fullmatch(r'/(system|system_ext|vendor|odm|product)/[A-Za-z0-9_.-]+',p) for p in roots):
        raise PatchError('模块覆盖目录无法安全表示')
    put('mount-roots.txt',('\n'.join(roots)+'\n').encode())
    customize=read(ASSETS/'ksu/customize.sh')
    customize=customize.split('# RUNTIME_INSTALL',1)[0]
    customize+='\n. "$MODPATH/install-early.sh"\n'
    put('customize.sh',customize.encode(),'0755')
    return dict(runtime_version=RUNTIME_VERSION,early_vintf=vintf,child_mount_roots=roots,
                hws_restart=False,audio_restart=False,codec_declaration='complete manifest at early-init',
                startup_gate=False,audio_config_publication='standard metamodule paths',
                automatic_audio_rollback=False,
                codec_recovery=dict(init_restart=True,interface_start=True,restart_period_seconds=3,
                                    periodic_polling=False,internal_crash_root_cause_fixed=False),
                requires=['KernelSU initrc injection','early metadata access','working metamodule'],
                mounting_backend='standard metamodule with independent bounded missing-item repair',
                publication_scope='computed at boot; child_mount_roots are search boundaries only',
                boot_tested=False,universal_compatibility=False)
