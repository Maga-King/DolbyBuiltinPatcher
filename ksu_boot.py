"""Early module-only boot packaging. Does not change native ROM patching."""
import re
from core import ASSETS, PatchError, read, xml_parse, xml_bytes

RUNTIME_VERSION='0.6.1-selfmount-preview6'
BIND_KEYS=('ro.system.build.fingerprint','ro.vendor.build.fingerprint','ro.board.platform')

MODULE_README='''KSU 目标 ROM 专用模块（杜比自挂载测试版）

preview6：DMS 启动前修正现有 dax_sqlite3.db 及 WAL/SHM/journal 的属主、权限和标签。
只处理上述普通文件，拒绝符号链接及硬链接；保留数据库内容，不清预设、不重建数据库。
修复旧备份留下 root:root/0600 导致 DMS 注册正常但参数写入返回 -19 的情况；无新增轮询。
preview5：按本次开机实际目录规划最小范围。已有文件单独 bind；新增文件只合并最近已有父目录。
例如 bin/hw 存在时只处理 bin/hw，不再合并整个 bin，也不访问同级 horae。
新增整个目录时仍需合并其已有父目录，不能承诺全部都是单文件挂载。
无需叠 OverlayFS；不跳过原文件保留失败，不更换库布局或启动服务定义。
preview3：刷入时安装同签名 App 更新，保留系统底包及数据；失败时开机完成后补试一次。
preview4：安装后及相同 APK 跳过安装前，按系统包身份恢复杜比 CE/DE 数据目录标签。
修复首次普通安装后晋升为系统 App、DE 目录仍保留旧标签造成设置不能写盘的问题。
data/app 中的系统更新不等于普通用户 App，仍需诊断确认系统身份及参数读写。
不改隐藏设置，不授予 Root，不强制降级。卸载模块不自动删除 App 和用户数据。
单文件 bind 失败时在私有暂存区复制兜底（最多 128 MiB，内存余量 256 MiB）；
目录挂载失败仍停止接入，不能保证所有机型均可开机。音频门控不变，无常驻补挂。

仅修改生成模块，不改输入 ROM、内置补丁合并/标签/SELinux/写回逻辑。
模块直接导出完整杜比相关 sepolicy.rule，不运行 secilc，不替换整份策略。
注入器可能跳过无效规则，但并不保证过滤所有运行或开机问题。
需要支持 initrc 注入及同步 post-mount 的 KernelSU，以及 init 挂载命名空间。
当前 KSU 早期 RC 接口需要开机早期可读的 /metadata；没有 watchdog 目录则使用 /metadata/ksu。
watchdog 只是上游选择的目录，不代表本模块运行看门狗、后台监控或轮询。
无可用 metadata 的设备暂不支持本加载路线，不能把早期文件随意搬到 /data 后继续声称兼容。
杜比文件在 files/，没有标准 system/；skip_mount 和 skip_mountify 用来避免重复挂载。
模块自行合并目录并递归 bind，只处理自己的文件；不接管其他模块的挂载。
无需依赖 OverlayFS 或元模块私有 API，不注入 VFS 驱动，不修改元模块配置。
切换元模块后，请卸载本模块 → 重启 → 重新安装。更换 ROM 后需重新生成。
不支持时拒绝安装/激活，不采用定时猜测或杀 HWS 的后备方案。

早期仅声明 HIDL 支持和 DMS；挂载后保留原有子挂载（包括 C17 OPEX）。
文件与依赖校验通过后，先注册 DMS，再声明并注册 Codec2/default9。
服务就绪后才提交音效与 codec XML，然后放行本次正常音频服务启动。
解码器准备失败时撤回其声明；保留原厂音频，不重启 HWS/音频/媒体服务。
解码服务不使用 oneshot；退出后由 init 恢复，并提供 default9 接口启动映射。
restart_period 3 限制重启频率，不是每 3 秒轮询或定时重启健康进程。
生成时校验恢复配置，避免再次打包出“解码服务退出后永久失联”的 RC。
这些保护不等于修复所有解码库内部崩溃；若反复退出，应停用模块并保留日志。
超时有限，无开机后的常驻轮询。模块 action 只检测一次状态。

这是基于目标快照生成的包，不保证任意 ROM、元模块、机型均兼容。
本次自挂载后端尚未完成 Android 真机验证。旧挂载版实测不能继承到新后端。
Mountify、Hybrid Mount、Magic Mount-rs 等做了源码核对，不等于各版本均实测通过。
VFS/隐藏功能可能改变文件可见性；不会擅自改全局隔离策略或许诺全兼容。
Enforcing 与各机型组合需另行验证，成功生成 ZIP 不等于目标机实测通过。
不替换原厂 libaudioeffecthal.qti.so，不挂载整份 CIL/precompiled_sepolicy。
不会禁用其他应用或接管官方音效开关，保留 Lunaris App 的现有功能。

不再按设备指纹、SDK、架构或原文件哈希拒装；已移除安装冲突名单。
安装放行不等于通刷，仍应按当前 ROM 生成，不建议叠加其他杜比实现。
升级时更新本模块自有早期 metadata；保留必要工具、路径及操作失败处理。
更换 ROM 后重新生成。solidify/ 仅提供固化参考，不会自动写入分区。
检测：Action 中文诊断；最近一份报告保存在 .runtime/diagnostic-last.txt。
单次诊断最多约 47 秒，包含文件大小/挂载、包注册、App 进程视图、服务及相关日志。
不启动 App、不修改应用权限/卸载策略、不持续抓日志，不把服务注册当成播放成功。
自挂载日志：.runtime/self-mount.log；启动日志：gate.log、codec.log、recover.log。
手工修改模块 RC 或启用状态后，须通过 KSU 刷新 initrc 缓存并重启；
只修改磁盘文件不代表当前 init 已加载新定义。正常安装由 KSU 管理缓存。
service.sh 开机一次检查 initrc 缓存；仅发现不一致时限时刷新一次。
刷新只对下一次重启有效，不重启手机或热重启系统服务；失败写日志不重试。
禁用/待卸载/待更新时跳过；action 只读检测，不改缓存。
日志：.runtime/initrc-cache.log。手改 RC 后可在重启前运行：
su -c 'sh /data/adb/modules/mio_dolby_c17_generated/initrc-cache.sh repair'
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
    for name in ('gate.sh','commit.sh','recover.sh','codec.sh','service.sh','install-early.sh','uninstall.sh','initrc-cache.sh','runtime-paths.sh','mount-engine.sh','self-mount.sh','install-app.sh'):
        put(name,(ASSETS/'ksu/boot'/name).read_bytes(),'0755')
    put('post-mount.sh',b'#!/system/bin/sh\nexec /system/bin/sh "${0%/*}/self-mount.sh"\n','0755')
    put('skip_mount',b'Dolby owns its files/ payload; do not mount it twice.\n')
    put('skip_mountify',b'Dolby self-mount\n')
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
                mounting_backend='runtime-minimal file binds / nearest-existing-parent merges; preserves submounts',
                publication_scope='computed at boot; child_mount_roots are search boundaries only',
                tested_reference='self-mount preview: no Android device validation yet',
                universal_compatibility=False)
