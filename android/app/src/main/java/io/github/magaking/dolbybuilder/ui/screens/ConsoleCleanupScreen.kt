package io.github.magaking.dolbybuilder.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.magaking.dolbybuilder.BuildConfig
import io.github.magaking.dolbybuilder.ui.GlassCard
import io.github.magaking.dolbybuilder.ui.LocalDarkTheme
import io.github.magaking.dolbybuilder.ui.PatcherPage
import io.github.magaking.dolbybuilder.ui.PatcherUiState
import io.github.magaking.dolbybuilder.ui.PreferenceCard
import io.github.magaking.dolbybuilder.ui.TaskStateKind
import io.github.magaking.dolbybuilder.ui.components.AppIcons
import io.github.magaking.dolbybuilder.ui.components.ConsoleTerminalBox
import io.github.magaking.dolbybuilder.ui.components.StatusBadge
import io.github.magaking.dolbybuilder.ui.components.ToolbarButton
import io.github.magaking.dolbybuilder.ui.components.formatElapsedSeconds
import top.yukonga.miuix.kmp.basic.ButtonDefaults
import top.yukonga.miuix.kmp.basic.Icon
import top.yukonga.miuix.kmp.basic.LinearProgressIndicator
import top.yukonga.miuix.kmp.basic.SmallTitle
import top.yukonga.miuix.kmp.basic.Text
import top.yukonga.miuix.kmp.basic.TextButton
import top.yukonga.miuix.kmp.preference.ArrowPreference
import top.yukonga.miuix.kmp.theme.MiuixTheme

@Composable
internal fun ConsoleCleanupScreen(
    state: PatcherUiState,
    bottom: Dp,
    onCopyLogs: () -> Unit,
    onClearLogs: () -> Unit,
    onCancelTask: () -> Unit,
    onRequestCleanCache: () -> Unit,
    onRequestDeleteBackups: () -> Unit,
    onOpenAppearance: () -> Unit,
    onOpenGuide: () -> Unit,
) {
    val colors = MiuixTheme.colorScheme
    val dark = LocalDarkTheme.current

    PatcherPage(
        title = "维护与日志",
        bottom = bottom,
        actions = {
            ToolbarButton(
                icon = AppIcons.Palette,
                description = "外观与液态玻璃",
                onClick = onOpenAppearance,
            )
            ToolbarButton(
                icon = AppIcons.Info,
                description = "关于与关于",
                onClick = onOpenGuide,
            )
        },
    ) {
        // 1. Live Task Progress & Terminal GlassCard
        item(key = "terminal-header") {
            SmallTitle("实时任务进度与运行终端")
        }

        item(key = "terminal-card") {
            val badgeBg = when {
                state.busy -> colors.primary.copy(alpha = 0.18f)
                state.taskStateKind == TaskStateKind.ERROR -> Color(0xFFF72727).copy(alpha = 0.18f)
                state.taskStateKind == TaskStateKind.SUCCESS -> Color(0xFF36D167).copy(alpha = 0.18f)
                else -> colors.surfaceContainerHigh
            }
            val badgeFg = when {
                state.busy -> colors.primary
                state.taskStateKind == TaskStateKind.ERROR -> Color(0xFFF72727)
                state.taskStateKind == TaskStateKind.SUCCESS -> Color(0xFF28B857)
                else -> colors.onSurfaceVariantSummary
            }
            val badgeText = when {
                state.busy -> "执行中"
                state.taskStateKind == TaskStateKind.ERROR -> "未完成"
                state.taskStateKind == TaskStateKind.SUCCESS -> "已完成"
                else -> "空闲"
            }

            GlassCard(insideMargin = PaddingValues(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        imageVector = AppIcons.Terminal,
                        contentDescription = null,
                        tint = colors.primary,
                        modifier = Modifier.size(22.dp),
                    )
                    Spacer(Modifier.width(10.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = if (state.busy && state.activeOperationLabel.isNotBlank()) {
                                state.activeOperationLabel
                            } else {
                                state.statusText
                            },
                            fontSize = 15.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = colors.onSurface,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                        if (state.busy || state.elapsedSeconds > 0) {
                            Spacer(Modifier.height(2.dp))
                            Text(
                                text = "耗时 ${formatElapsedSeconds(state.elapsedSeconds)}",
                                fontSize = 12.sp,
                                fontFamily = FontFamily.Monospace,
                                color = colors.onSurfaceVariantSummary,
                            )
                        }
                    }
                    Spacer(Modifier.width(8.dp))
                    StatusBadge(
                        text = badgeText,
                        containerColor = badgeBg,
                        contentColor = badgeFg,
                    )
                }

                if (state.busy) {
                    Spacer(Modifier.height(12.dp))
                    LinearProgressIndicator(Modifier.fillMaxWidth())
                    Spacer(Modifier.height(10.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            text = "写入/回退阶段将保护一次性事务，不强杀写回进程",
                            fontSize = 11.sp,
                            color = colors.onSurfaceVariantSummary,
                            modifier = Modifier.weight(1f),
                        )
                        Spacer(Modifier.width(8.dp))
                        TextButton(
                            text = "安全取消",
                            onClick = onCancelTask,
                            minHeight = 32.dp,
                            cornerRadius = 10.dp,
                            insideMargin = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                        )
                    }
                }

                Spacer(Modifier.height(12.dp))

                ConsoleTerminalBox(
                    logs = state.logs,
                    busy = state.busy,
                    minHeight = 220.dp,
                    maxHeight = 360.dp,
                )

                Spacer(Modifier.height(12.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    TextButton(
                        text = "复制日志",
                        onClick = onCopyLogs,
                        modifier = Modifier.weight(1f),
                        colors = ButtonDefaults.textButtonColorsPrimary(),
                    )
                    TextButton(
                        text = "清空显示",
                        onClick = onClearLogs,
                        modifier = Modifier.weight(1f),
                        enabled = !state.busy,
                    )
                }
            }
        }

        // 2. Maintenance PreferenceCard + Isolated Red Danger Backup Card
        item(key = "maint-header") {
            SmallTitle("缓存维护与备份管理")
        }

        item(key = "cache-card") {
            PreferenceCard {
                ArrowPreference(
                    title = "清理无用缓存（保留 ZIP / 备份）",
                    summary = "仅删除快照与成功模块构建的中间目录；存在未决事务时自动拒绝清理",
                    enabled = !state.busy,
                    startAction = {
                        Icon(
                            imageVector = AppIcons.CleanSpark,
                            contentDescription = null,
                            modifier = Modifier.padding(end = 14.dp).size(22.dp),
                            tint = colors.primary,
                        )
                    },
                    onClick = onRequestCleanCache,
                )
            }
        }

        item(key = "danger-backup-card") {
            GlassCard(
                insideMargin = PaddingValues(16.dp),
                tint = if (dark) Color(0xFF310808) else Color(0xFFF8E2E2),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = AppIcons.DeleteForever,
                        contentDescription = null,
                        tint = Color(0xFFF72727),
                        modifier = Modifier.size(22.dp),
                    )
                    Spacer(Modifier.width(10.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "危险区域 · 永久删除备份",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = Color(0xFFF72727),
                        )
                        Text(
                            text = "仅移除本应用对指定 ROM 目录创建的已结束事务备份与记录",
                            fontSize = 12.sp,
                            color = colors.onSurfaceVariantSummary,
                        )
                    }
                }

                Spacer(Modifier.height(12.dp))
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .background(
                            colors.surfaceContainerHigh.copy(alpha = if (dark) 0.50f else 0.72f),
                            RoundedCornerShape(10.dp),
                        )
                        .padding(horizontal = 12.dp, vertical = 9.dp),
                ) {
                    Text(
                        text = "当前关联 ROM 目录：",
                        fontSize = 11.sp,
                        color = colors.onSurfaceVariantSummary,
                    )
                    Spacer(Modifier.height(2.dp))
                    Text(
                        text = state.romPath.trim().ifEmpty { "尚未填写（请先在「ROM 内置」页输入目标目录）" },
                        fontSize = 12.sp,
                        fontFamily = FontFamily.Monospace,
                        color = if (state.romPath.isBlank()) colors.onSurfaceVariantSummary else colors.onSurface,
                    )
                }

                Spacer(Modifier.height(12.dp))
                TextButton(
                    text = "永久删除此 ROM 的备份与记录",
                    onClick = onRequestDeleteBackups,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !state.busy,
                    colors = ButtonDefaults.textButtonColors(
                        color = Color(0xFFD93025).copy(alpha = if (dark) 0.34f else 0.16f),
                        textColor = Color(0xFFF72727),
                    ),
                )
            }
        }

        // 3. Settings & Appearance PreferenceCard
        item(key = "settings-header") {
            SmallTitle("设置与关于")
        }

        item(key = "settings-card") {
            PreferenceCard {
                ArrowPreference(
                    title = "外观与液态玻璃设置",
                    summary = "深色模式、动态取色、声学极光背景、壁纸与折射参数调节",
                    startAction = {
                        Icon(
                            imageVector = AppIcons.Palette,
                            contentDescription = null,
                            modifier = Modifier.padding(end = 14.dp).size(22.dp),
                            tint = colors.primary,
                        )
                    },
                    onClick = onOpenAppearance,
                )
                ArrowPreference(
                    title = "关于与关于",
                    summary = "版本 ${BuildConfig.VERSION_NAME} · 科比",
                    startAction = {
                        Icon(
                            imageVector = AppIcons.Info,
                            contentDescription = null,
                            modifier = Modifier.padding(end = 14.dp).size(22.dp),
                            tint = colors.onSurface,
                        )
                    },
                    onClick = onOpenGuide,
                )
            }
        }
    }
}
