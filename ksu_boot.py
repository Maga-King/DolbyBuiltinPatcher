"""Early module-only boot packaging. Does not change native ROM patching."""
import re
from core import ASSETS, PatchError, read, xml_parse, xml_bytes

RUNTIME_VERSION='0.6.1-early4-unpinned'
BIND_KEYS=('ro.system.build.fingerprint','ro.vendor.build.fingerprint','ro.board.platform')

MODULE_README='''KSU 目标 ROM 专用模块（早期加载版）

仅修改生成模块，不改输入 ROM、内置补丁合并/标签/SELinux/写回逻辑。
模块直接导出完整杜比相关 sepolicy.rule，不运行 secilc，不替换整份策略。
注入器可能跳过无效规则，但并不保证过滤所有运行或开机问题。
需要支持 initrc 注入及同步 post-mount 的 KernelSU 和挂载元模块。
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
实测参考：一加13 C17 Android17 DSU + KSU + mountify2.0.3；系统原本为 Permissive。
Enforcing 与其他组合需另行验证，成功生成 ZIP 不等于目标机实测通过。
不替换原厂 libaudioeffecthal.qti.so，不挂载整份 CIL/precompiled_sepolicy。
不会禁用其他应用或接管官方音效开关，保留 Lunaris App 的现有功能。

不再按设备指纹、SDK、架构或原文件哈希拒装；已移除安装冲突名单。
安装放行不等于通刷，仍应按当前 ROM 生成，不建议叠加其他杜比实现。
升级时更新本模块自有早期 metadata；保留必要工具、路径及操作失败处理。
更换 ROM 后重新生成。solidify/ 仅提供固化参考，不会自动写入分区。
检测：action.sh、.runtime/status、gate.log、codec.log、recover.log、preserve.log。
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
    for name in ('gate.sh','commit.sh','recover.sh','codec.sh','preserve.sh','service.sh','install-early.sh','uninstall.sh','initrc-cache.sh'):
        put(name,(ASSETS/'ksu/boot'/name).read_bytes(),'0755')
    for stage,arg in [('post-fs-data','save'),('post-mount','restore')]:
        put(stage+'.sh',f'#!/system/bin/sh\nexec /system/bin/sh "${{0%/*}}/preserve.sh" {arg}\n'.encode(),'0755')
    roots=sorted({'/'+target.strip('/').split('/')[0]+'/'+target.strip('/').split('/')[1] for _,target,_ in mounted})
    if any(not re.fullmatch(r'/(system|system_ext|vendor|odm|product)/[A-Za-z0-9_.-]+',p) for p in roots):
        raise PatchError('模块覆盖目录无法安全表示')
    put('mount-roots.txt',('\n'.join(roots)+'\n').encode())
    put('mode',b'activate\n')
    customize=read(ASSETS/'ksu/customize.sh')
    customize=customize[:customize.index("ui_print 'Target-specific")]
    customize+='\n. "$MODPATH/install-early.sh"\n'
    put('customize.sh',customize.encode(),'0755')
    return dict(runtime_version=RUNTIME_VERSION,early_vintf=early,child_mount_roots=roots,
                hws_restart=False,audio_restart=False,codec_declaration='after payload validation',
                codec_recovery=dict(init_restart=True,interface_start=True,restart_period_seconds=3,
                                    periodic_polling=False,internal_crash_root_cause_fixed=False),
                requires=['KernelSU initrc injection','synchronous post-mount stage','compatible mounting metamodule'],
                tested_reference='OnePlus13 C17 SDK37 DSU / mountify2.0.3 / permissive',
                universal_compatibility=False)
