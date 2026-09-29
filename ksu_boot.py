# Shared module-only boot packaging for desktop and Android.
"""Early module-only boot packaging. Does not change native ROM patching."""
import re
from core import ASSETS, PatchError, read, xml_parse, xml_bytes

RUNTIME_VERSION='0.6.1-meta-repair-preview1'
BIND_KEYS=('ro.system.build.fingerprint','ro.vendor.build.fingerprint','ro.board.platform')

MODULE_README='''KSU 元模块承载＋缺失项补挂（电脑 1.0.3 / Android 0.2.4 测试版）
方案基于 GitHub 首个公开版本 e09bb23，不是双份载荷自挂载版。
普通文件只有 system/ 一份；不生成 files/、self-mount.sh 或正常跳过元模块标记。
挂载前保存原系统子挂载，元模块挂载后恢复，再补挂缺失或内容/权限/标签不符的项。
已有文件独立绑定；缺失路径只合并必要的最小父目录，保留当前可见子挂载。
没有相关元模块挂载或一项正确载荷都没有时停止，不自动以整包自挂载接管。
需要支持 initrc 注入、同步 post-mount 的 KSU 和可用元模块；建议先验证 Mountify。
切换元模块：卸载杜比模块 → 完整重启 → 重新安装；不能只热重启框架。
不修改元模块全局设置、不取消防卡保护、不杀 HWS、不重启音频，不新增常驻轮询。
子挂载恢复失败不能保证系统正常；不会卸载元模块共享父目录，请禁用杜比并保留日志。
只影响生成模块，不改变 ROM 原生内置事务、标签或策略编译流程。
保留 87b4cbb 的数据库权限兜底、同签名 App 更新安装与数据标签修复。
数据库内容和用户预设不删除；服务初始定义与 Codec2 接口/恢复间隔保留。
仍需开机早期可读 /metadata；watchdog 目录非必需；没有可用早期接口不能强行跳过。
不按 SDK、机型和指纹拒装不代表通刷。PLQ110 Enforcing + Mountify 2.0.3 已验证开机及服务注册。
该次 82/82 项直接挂齐，补挂 0 次；不能当作手机补挂或各格式实际解码验证。
共享 metadata 的 DSU 仍可能读到主系统早期注入；测试已内置杜比的 ROM 前须禁用旧模块并确认缓存解除。
操作按钮单次中文诊断；日志：preserve.log、.runtime/repair.log、gate.log、codec.log。
补挂成功不代表服务注册或实际解码成功。请回传完整诊断，确认元模块未被自动禁用。
其他模块更晚覆盖或故意修改同一子挂载仍可能冲突；不保证各分支/元模块均兼容。
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
        raise PatchError('解码服务缺少启动门禁、default9 接口映射或恢复间隔，拒绝出包')
    if any(line.split()[0] in ('oneshot','critical','reboot_on_failure','onrestart') for line in options):
        raise PatchError('解码服务含不安全的退出/重启选项，拒绝出包')


def target_bindings(build):
    # Stable packaging API; no install/runtime identity pinning.
    return {}


def export_boot(build,folder,put,late,mounted,bindings,device_target):
    runtime_rc=read(ASSETS/'ksu/boot/init.rc')
    validate_codec_recovery(runtime_rc)
    # This gate depends on this actual init service name, not a guessed delay.
    rcdir=build.rom.parts['vendor']/'etc/init'
    if not any(re.search(r'^service\s+vendor\.audio-hal-aidl\s',read(p),re.M)
               for p in rcdir.rglob('*.rc')):
        raise PatchError('模块早期门禁暂不支持此音频启动服务；不会使用定时碰运气的后备方案')
    early=[]
    full_codec=None
    for phase,source,target,expected in late:
        if phase!='vintf':continue
        data=(folder/source).read_bytes()
        root=xml_parse(data)
        for hal in list(root.findall('hal')):
            if hal.findtext('name')=='android.hardware.media.c2':
                if target!=device_target:raise PatchError('发现多个 Codec2 声明目标，拒绝不完整回退')
                full_codec=data
                root.remove(hal)
        label='u:object_r:vendor_configs_file:s0' if target.startswith(('/vendor/','/odm/')) else 'u:object_r:system_file:s0'
        put('early/'+source,xml_bytes(root,data),label=label)
        early.append((source,target,expected,label))
    if full_codec is None:raise PatchError('模块缺少可延迟发布的 Dolby Codec2 声明')
    put('codec-target',(device_target+'\n').encode())
    put('codec-manifest.xml',full_codec,label='u:object_r:vendor_configs_file:s0')
    put('early/vintf.tsv',''.join('\t'.join(row)+'\n' for row in early).encode())
    put('early/target.tsv',''.join(k+'\t'+v+'\n' for k,v in bindings.items()).encode())
    put('early/early.sh',(ASSETS/'ksu/boot/early.sh').read_bytes(),'0755')
    put('initrc/dolby.rc',runtime_rc.encode())
    for name in ('gate.sh','commit.sh','recover.sh','codec.sh','service.sh','install-early.sh','uninstall.sh','initrc-cache.sh','runtime-paths.sh','mount-engine.sh','preserve.sh','repair-mounts.sh','install-app.sh'):
        put(name,(ASSETS/'ksu/boot'/name).read_bytes(),'0755')
    for stage in ('post-fs-data.sh','post-mount.sh'):
        put(stage,(ASSETS/'ksu'/stage).read_bytes(),'0755')
    # Only search boundaries: runtime walks down these payload branches to
    # discover minimal publication targets (offline snapshots omit directories).
    roots=sorted({'/'+target.strip('/').split('/')[0]+'/'+target.strip('/').split('/')[1] for _,target,_ in mounted})
    if any(not re.fullmatch(r'/(system|system_ext|vendor|odm|product)/[A-Za-z0-9_.-]+',p) for p in roots):
        raise PatchError('模块覆盖目录无法安全表示')
    put('mount-roots.txt',('\n'.join(roots)+'\n').encode())
    put('mode',b'activate\n')
    customize=read(ASSETS/'ksu/customize.sh')
    customize=customize.split('# RUNTIME_INSTALL',1)[0]
    customize+='\n. "$MODPATH/install-early.sh"\n'
    put('customize.sh',customize.encode(),'0755')
    return dict(runtime_version=RUNTIME_VERSION,early_vintf=early,child_mount_roots=roots,
                hws_restart=False,audio_restart=False,codec_declaration='after payload validation',
                codec_recovery=dict(init_restart=True,interface_start=True,restart_period_seconds=3,
                                    periodic_polling=False,internal_crash_root_cause_fixed=False),
                requires=['KernelSU initrc injection','synchronous post-mount stage','init mount namespace'],
                mounting_backend='original metamodule with bounded missing-item repair',
                publication_scope='computed at boot; child_mount_roots are search boundaries only',
                tested_reference='PLQ110 Enforcing + Mountify 2.0.3: boot/services/82 payloads, zero repairs; playback route not universal',
                universal_compatibility=False)
