# Shared module-only boot packaging for desktop and Android.
"""Early module-only boot packaging. Does not change native ROM patching."""
import re
from core import ASSETS, PatchError, read

RUNTIME_VERSION='0.6.3-codec-layout-preview1'
BIND_KEYS=('ro.system.build.fingerprint','ro.vendor.build.fingerprint','ro.board.platform')

MODULE_README='''KSU 标准路径音频配置（电脑 1.0.7 / Android 0.2.8 测试版）
按输入 XML 自动识别新旧 Codec 配置；新版仅补齐已引用的缺失音频 XML，内容只含杜比解码器。
音效 XML、Codec2 XML 与 ODM 配置和库文件一起放在标准 system/ 分区目录中，由元模块加载。
不再生成 late/、late.tsv，也不再通过 gate/commit/recover 延迟挂载音频配置。
开机 early-init 一次性加载完整 VINTF（含 Codec2/default9），early-boot 直接启动杜比服务。
启动不依赖 repair-ok、音频服务名、linker 检查或服务注册轮询；补挂失败不会阻止服务启动。
保留启动前数据库权限修复；修复失败会记录日志，init 仍继续启动服务，不删除数据库或用户预设。
保留元模块挂载前保存/挂载后恢复子挂载，以及有界缺失项补挂；不生成 files/ 或 self-mount.sh。
NoMount 的 VFS 重定向不一定产生挂载记录，repair.log 失败不再表示杜比服务被门控拦截。
没有相关元模块挂载时不自动整包自挂载；元模块仍需正确提供全部文件。
保留 Codec2 default9 接口映射与退出后 3 秒恢复间隔，不新增常驻轮询，不重启系统音频服务。
需要支持 initrc 注入的 KSU、开机早期可读的 /metadata 和可用元模块。
切换元模块：卸载杜比模块 → 完整重启 → 重新安装；不能只热重启框架。
保留同签名 App 更新安装、数据标签修复，以及 OPLUS 音效中心按需停用和卸载恢复。
更新生成器后须重新生成、安装模块并完整重启；旧模块不会被生成器自动修改。
仅修改模块生成流程，ROM 原生内置事务、标签及策略编译流程保持独立。
本版不自动撤回音频配置；文件缺失或服务失败需通过 Action 诊断，必要时禁用模块并重启。
共享 metadata 的 DSU 仍可能读到主系统早期注入；测试已内置杜比的 ROM 前须解除旧模块缓存。
日志：preserve.log、.runtime/repair.log、.runtime/prepare.log；Action 为单次中文诊断。
此前 PLQ110 + Mountify 的开机结果属于旧版，不代表本版已完成 NoMount 开机或实际播放验证。
'''


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
    for name in ('prepare-data.sh','service.sh','install-early.sh','uninstall.sh','initrc-cache.sh','runtime-paths.sh','mount-engine.sh','preserve.sh','repair-mounts.sh','install-app.sh','freeze-audioeffectcenter.sh'):
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
