package io.github.magaking.dolbybuilder.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.magaking.dolbybuilder.ui.GlassCard
import io.github.magaking.dolbybuilder.ui.LocalDarkTheme
import io.github.magaking.dolbybuilder.ui.PatcherPage
import io.github.magaking.dolbybuilder.ui.PatcherUiState
import io.github.magaking.dolbybuilder.ui.PreferenceCard
import io.github.magaking.dolbybuilder.ui.TaskStateKind
import io.github.magaking.dolbybuilder.ui.components.AppIcons
import io.github.magaking.dolbybuilder.ui.components.LiveTaskGlassCard
import io.github.magaking.dolbybuilder.ui.components.RomPathInputSection
import io.github.magaking.dolbybuilder.ui.components.StatusBadge
import io.github.magaking.dolbybuilder.ui.components.ToolbarButton
import top.yukonga.miuix.kmp.basic.ButtonDefaults
import top.yukonga.miuix.kmp.basic.Icon
import top.yukonga.miuix.kmp.basic.SmallTitle
import top.yukonga.miuix.kmp.basic.Text
import top.yukonga.miuix.kmp.basic.TextButton
import top.yukonga.miuix.kmp.preference.ArrowPreference
import top.yukonga.miuix.kmp.theme.MiuixTheme

@Composable
internal fun RomPatchScreen(
    state: PatcherUiState,
    bottom: Dp,
    onRomPathChange: (String) -> Unit,
    onRequestPatchRom: () -> Unit,
    onQueryStatus: () -> Unit,
    onRequestRestoreRom: () -> Unit,
    onOpenAppearance: () -> Unit,
    onOpenGuide: () -> Unit,
    onOpenConsoleTab: () -> Unit,
    onCancelTask: () -> Unit,
) {
    val colors = MiuixTheme.colorScheme
    val dark = LocalDarkTheme.current

    PatcherPage(
        title = "ROM 原位内置",
        bottom = bottom,
        actions = {
            ToolbarButton(
                icon = AppIcons.Terminal,
                description = "运行日志",
                onClick = onOpenConsoleTab,
                tint = if (state.taskStateKind == TaskStateKind.ERROR) Color(0xFFF72727) else null,
            )
            ToolbarButton(
                icon = AppIcons.Palette,
                description = "外观与液态玻璃",
                onClick = onOpenAppearance,
            )
            ToolbarButton(
                icon = AppIcons.Info,
                description = "关于",
                onClick = onOpenGuide,
            )
        },
    ) {
        if (state.busy || state.taskStateKind != TaskStateKind.IDLE) {
            item(key = "rom-live-task") {
                LiveTaskGlassCard(
                    busy = state.busy,
                    taskStateKind = state.taskStateKind,
                    operationLabel = state.activeOperationLabel,
                    statusText = state.statusText,
                    lastLogLine = state.lastLogLine,
                    elapsedSeconds = state.elapsedSeconds,
                    onOpenConsole = onOpenConsoleTab,
                    onCancel = onCancelTask,
                )
            }
        }

        // 1. Target Extracted ROM GlassCard
        item(key = "rom-dir-header") {
            SmallTitle("目标解包 ROM 目录")
        }

        item(key = "rom-dir-card") {
            GlassCard(insideMargin = PaddingValues(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        imageVector = AppIcons.Folder,
                        contentDescription = null,
                        tint = colors.primary,
                        modifier = Modifier.size(22.dp),
                    )
                    Spacer(Modifier.width(10.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "解包五分区根目录",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = colors.onSurface,
                        )
                        Text(
                            text = "仅操作手机内独立解包目录，绝不写运行中系统分区",
                            fontSize = 12.sp,
                            color = colors.onSurfaceVariantSummary,
                        )
                    }
                }

                Spacer(Modifier.height(14.dp))

                RomPathInputSection(
                    romPath = state.romPath,
                    romPathError = state.romPathError,
                    enabled = !state.busy,
                    onRomPathChange = onRomPathChange,
                )

                Spacer(Modifier.height(12.dp))
                Text(
                    text = "必需分区与元数据目录：",
                    fontSize = 12.sp,
                    color = colors.onSurfaceVariantSummary,
                )
                Spacer(Modifier.height(6.dp))
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    val parts = listOf("system", "system_ext", "vendor", "odm", "product", "config (DNA)")
                    for (part in parts) {
                        Box(
                            modifier = Modifier
                                .background(
                                    colors.surfaceContainerHigh.copy(alpha = 0.72f),
                                    RoundedCornerShape(8.dp),
                                )
                                .padding(horizontal = 9.dp, vertical = 5.dp),
                        ) {
                            Text(
                                text = part,
                                fontSize = 11.sp,
                                fontFamily = FontFamily.Monospace,
                                color = colors.onSurfaceVariantSummary,
                            )
                        }
                    }
                }
            }
        }

        // 2. Primary In-Place Patch GlassCard
        item(key = "patch-header") {
            SmallTitle("原位内置杜比组件")
        }

        item(key = "patch-card") {
            GlassCard(insideMargin = PaddingValues(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        imageVector = AppIcons.RomLayers,
                        contentDescription = null,
                        tint = colors.primary,
                        modifier = Modifier.size(22.dp),
                    )
                    Spacer(Modifier.width(10.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "一次性事务原位修改",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = colors.onSurface,
                        )
                        Text(
                            text = "与电脑端一致：保留原厂 SELinux 标签并编译目标策略",
                            fontSize = 12.sp,
                            color = colors.onSurfaceVariantSummary,
                        )
                    }
                    StatusBadge(
                        text = "自动备份",
                        containerColor = colors.primary.copy(alpha = 0.16f),
                        contentColor = colors.primary,
                    )
                }

                Spacer(Modifier.height(12.dp))

                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    val steps = listOf("① 只读快照", "② 编译 SELinux", "③ 外部备份", "④ 事务写回")
                    steps.forEachIndexed { idx, step ->
                        Box(
                            modifier = Modifier
                                .background(
                                    colors.primary.copy(alpha = 0.12f),
                                    RoundedCornerShape(9.dp),
                                )
                                .padding(horizontal = 10.dp, vertical = 5.dp),
                        ) {
                            Text(
                                text = step,
                                fontSize = 11.sp,
                                fontWeight = FontWeight.Medium,
                                color = colors.primary,
                            )
                        }
                        if (idx < steps.lastIndex) {
                            Text(
                                text = "→",
                                fontSize = 12.sp,
                                color = colors.onSurfaceVariantSummary,
                            )
                        }
                    }
                }

                Spacer(Modifier.height(12.dp))
                Text(
                    text = "调用 APK 内置 ARM64 secilc 编译普通/调试策略，策略编译失败绝不写回 ROM；修改完成后仍需使用 DNA 等工具重新打包镜像。",
                    fontSize = 13.sp,
                    lineHeight = 19.sp,
                    color = colors.onSurfaceVariantSummary,
                )

                Spacer(Modifier.height(16.dp))
                TextButton(
                    text = "备份并一键修改此 ROM",
                    onClick = onRequestPatchRom,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !state.busy,
                    colors = ButtonDefaults.textButtonColorsPrimary(),
                )
            }
        }

        // 3. Transaction Reconciliation & Rollback PreferenceCard
        item(key = "recovery-header") {
            SmallTitle("事务对账与安全回退")
        }

        item(key = "recovery-card") {
            PreferenceCard {
                ArrowPreference(
                    title = "查询 / 恢复上次事务状态",
                    summary = "意外闪退或中断后请先点此查询一次性事务状态，切勿直接重复执行修改",
                    enabled = !state.busy,
                    startAction = {
                        Icon(
                            imageVector = AppIcons.HistoryStatus,
                            contentDescription = null,
                            modifier = Modifier.padding(end = 14.dp).size(22.dp),
                            tint = colors.primary,
                        )
                    },
                    onClick = onQueryStatus,
                )
                ArrowPreference(
                    title = "回退此 ROM 的上次修改",
                    summary = "按最近一次记录与外部备份还原原厂文件及打包标签；若已被外部工具改动则自动停止保护",
                    enabled = !state.busy,
                    startAction = {
                        Icon(
                            imageVector = AppIcons.Restore,
                            contentDescription = null,
                            modifier = Modifier.padding(end = 14.dp).size(22.dp),
                            tint = colors.onSurface,
                        )
                    },
                    onClick = onRequestRestoreRom,
                )
            }
        }

        // 4. Backup Preservation Notice
        item(key = "backup-notice") {
            GlassCard(
                insideMargin = PaddingValues(16.dp),
                tint = if (dark) Color(0xFF2B220F) else Color(0xFFFFF5DE),
            ) {
                Row(verticalAlignment = Alignment.Top) {
                    Icon(
                        imageVector = AppIcons.ShieldAlert,
                        contentDescription = null,
                        tint = Color(0xFFE69316),
                        modifier = Modifier.padding(top = 2.dp).size(20.dp),
                    )
                    Spacer(Modifier.width(10.dp))
                    Text(
                        text = "外部备份位于 ROM 同级 .dolby-patcher-backups/<目录名>-<任务号>，事务记录保存在应用私有目录。确认重新打包刷机正常前，请勿卸载应用、清除数据或移动/删除备份目录。",
                        fontSize = 12.sp,
                        lineHeight = 18.sp,
                        color = colors.onSurface,
                    )
                }
            }
        }
    }
}
