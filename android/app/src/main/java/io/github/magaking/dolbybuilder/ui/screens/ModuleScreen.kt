package io.github.magaking.dolbybuilder.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.magaking.dolbybuilder.ui.EnvStatus
import io.github.magaking.dolbybuilder.ui.GlassCard
import io.github.magaking.dolbybuilder.ui.GlassFilterTabs
import io.github.magaking.dolbybuilder.ui.LocalDarkTheme
import io.github.magaking.dolbybuilder.ui.ModuleSourceMode
import io.github.magaking.dolbybuilder.ui.PatcherPage
import io.github.magaking.dolbybuilder.ui.PatcherUiState
import io.github.magaking.dolbybuilder.ui.TaskStateKind
import io.github.magaking.dolbybuilder.ui.components.AppIcons
import io.github.magaking.dolbybuilder.ui.components.LiveTaskGlassCard
import io.github.magaking.dolbybuilder.ui.components.RomPathInputSection
import io.github.magaking.dolbybuilder.ui.components.StatusBadge
import io.github.magaking.dolbybuilder.ui.components.ToolbarButton
import io.github.magaking.dolbybuilder.ui.components.formatFileSize
import io.github.magaking.dolbybuilder.ui.components.formatTimestamp
import top.yukonga.miuix.kmp.basic.ButtonDefaults
import top.yukonga.miuix.kmp.basic.Icon
import top.yukonga.miuix.kmp.basic.SmallTitle
import top.yukonga.miuix.kmp.basic.Text
import top.yukonga.miuix.kmp.basic.TextButton
import top.yukonga.miuix.kmp.theme.MiuixTheme

@Composable
internal fun ModuleScreen(
    state: PatcherUiState,
    bottom: Dp,
    onCheckEnv: () -> Unit,
    onSelectSourceMode: (ModuleSourceMode) -> Unit,
    onRomPathChange: (String) -> Unit,
    onRequestBuildModule: () -> Unit,
    onSaveZip: () -> Unit,
    onOpenAppearance: () -> Unit,
    onOpenGuide: () -> Unit,
    onOpenConsoleTab: () -> Unit,
    onCancelTask: () -> Unit,
) {
    val colors = MiuixTheme.colorScheme

    PatcherPage(
        title = "模块生成",
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
            item(key = "live-task-banner") {
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

        // 1. SukiSU / Nyako 2-Column Hero Status Row
        item(key = "hero-status") {
            ModuleHeroStatusRow(
                state = state,
                onCheckEnv = onCheckEnv,
                onToggleSource = {
                    val next = if (state.moduleSourceMode == ModuleSourceMode.LIVE_SYSTEM) {
                        ModuleSourceMode.EXTRACTED_ROM
                    } else {
                        ModuleSourceMode.LIVE_SYSTEM
                    }
                    onSelectSourceMode(next)
                },
                onSaveZip = onSaveZip,
            )
        }

        // 2. Environment Summary & Check Action Card
        item(key = "env-detail-card") {
            GlassCard(insideMargin = PaddingValues(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = if (state.deviceModel.isNotBlank()) {
                                "运行环境 · ${state.deviceModel}"
                            } else {
                                "Python / RC 模板 / ROOT 环境检测"
                            },
                            fontSize = 15.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = colors.onSurface,
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(
                            text = state.envSummary,
                            fontSize = 13.sp,
                            lineHeight = 18.sp,
                            color = colors.onSurfaceVariantSummary,
                        )
                    }
                }
                Spacer(Modifier.height(12.dp))
                TextButton(
                    text = if (state.envStatus == EnvStatus.UNCHECKED) {
                        "立即检测环境与 ROOT"
                    } else {
                        "重新检测环境与 ROOT"
                    },
                    onClick = onCheckEnv,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !state.busy,
                )
            }
        }

        // 3. Source Selection + Module Build Card
        item(key = "source-header") {
            SmallTitle("输入源")
        }

        item(key = "source-build-card") {
            GlassCard(insideMargin = PaddingValues(16.dp)) {
                GlassFilterTabs(
                    titles = listOf("读取当前系统", "从解包 ROM 生成"),
                    selectedIndex = if (state.moduleSourceMode == ModuleSourceMode.LIVE_SYSTEM) 0 else 1,
                    enabled = !state.busy,
                    onTabSelected = { idx ->
                        onSelectSourceMode(
                            if (idx == 0) ModuleSourceMode.LIVE_SYSTEM else ModuleSourceMode.EXTRACTED_ROM
                        )
                    },
                )

                AnimatedVisibility(
                    visible = state.moduleSourceMode == ModuleSourceMode.EXTRACTED_ROM,
                    enter = fadeIn() + expandVertically(),
                    exit = fadeOut() + shrinkVertically(),
                ) {
                    Column {
                        Spacer(Modifier.height(14.dp))
                        RomPathInputSection(
                            romPath = state.romPath,
                            romPathError = state.romPathError,
                            enabled = !state.busy,
                            onRomPathChange = onRomPathChange,
                        )
                    }
                }

                Spacer(Modifier.height(16.dp))

                TextButton(
                    text = "生成模块",
                    onClick = onRequestBuildModule,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !state.busy,
                    colors = ButtonDefaults.textButtonColorsPrimary(),
                )
            }
        }

        // 4. Export Module ZIP Card
        item(key = "export-header") {
            SmallTitle("模块包导出")
        }

        item(key = "export-card") {
            val zip = state.lastZip
            val hasZip = zip != null
            GlassCard(insideMargin = PaddingValues(16.dp)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        imageVector = AppIcons.DownloadSave,
                        contentDescription = null,
                        tint = if (hasZip) colors.primary else colors.onSurfaceVariantSummary,
                        modifier = Modifier.size(22.dp),
                    )
                    Spacer(Modifier.width(10.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "导出 ZIP",
                            fontSize = 16.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = colors.onSurface,
                        )
                        Text(
                            text = if (hasZip) {
                                "模块包已就绪，导出后请交给 KernelSU 管理器刷入"
                            } else {
                                "完成上方生成后可在此导出保存 杜比全景+解码器_KSU.zip"
                            },
                            fontSize = 12.sp,
                            color = colors.onSurfaceVariantSummary,
                        )
                    }
                    StatusBadge(
                        text = if (hasZip) "可导出" else "待生成",
                        containerColor = if (hasZip) {
                            Color(0xFF36D167).copy(alpha = 0.18f)
                        } else {
                            colors.surfaceContainerHigh
                        },
                        contentColor = if (hasZip) Color(0xFF28B857) else colors.onSurfaceVariantSummary,
                    )
                }

                if (zip != null) {
                    Spacer(Modifier.height(12.dp))
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(colors.surfaceContainerHigh.copy(alpha = 0.6f), RoundedCornerShape(12.dp))
                            .padding(horizontal = 12.dp, vertical = 10.dp),
                    ) {
                        Text(
                            text = zip.fileName,
                            fontSize = 13.sp,
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Medium,
                            color = colors.onSurface,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Spacer(Modifier.height(2.dp))
                        Text(
                            text = "${formatFileSize(zip.sizeBytes)}  ·  生成于 ${formatTimestamp(zip.lastModifiedMillis)}",
                            fontSize = 12.sp,
                            color = colors.onSurfaceVariantSummary,
                        )
                    }
                }

                Spacer(Modifier.height(14.dp))
                TextButton(
                    text = "导出 ZIP",
                    onClick = onSaveZip,
                    modifier = Modifier.fillMaxWidth(),
                    enabled = !state.busy && hasZip,
                    colors = ButtonDefaults.textButtonColorsPrimary(),
                )
            }
        }
    }
}

@Composable
private fun ModuleHeroStatusRow(
    state: PatcherUiState,
    onCheckEnv: () -> Unit,
    onToggleSource: () -> Unit,
    onSaveZip: () -> Unit,
) {
    val colors = MiuixTheme.colorScheme
    val dark = LocalDarkTheme.current

    val heroTint = when (state.envStatus) {
        EnvStatus.READY -> if (dark) Color(0xFF1A3825) else Color(0xFFDFFAE4)
        EnvStatus.NO_PAYLOAD -> if (dark) Color(0xFF382810) else Color(0xFFFFF1D6)
        EnvStatus.ERROR -> if (dark) Color(0xFF310808) else Color(0xFFF8E2E2)
        EnvStatus.UNCHECKED -> null
    }
    val emblemTint = when (state.envStatus) {
        EnvStatus.READY -> Color(0xFF36D167)
        EnvStatus.NO_PAYLOAD -> Color(0xFFF59E0B).copy(alpha = 0.55f)
        EnvStatus.ERROR -> Color(0xFFF72727).copy(alpha = 0.55f)
        EnvStatus.UNCHECKED -> colors.primary.copy(alpha = 0.22f)
    }
    val heroIcon = when (state.envStatus) {
        EnvStatus.READY -> AppIcons.CheckCircleRounded
        EnvStatus.UNCHECKED -> AppIcons.Equalizer
        else -> AppIcons.ShieldAlert
    }
    val heroHeadline = when (state.envStatus) {
        EnvStatus.READY -> "已就绪\n<ROOT · 资产>"
        EnvStatus.NO_PAYLOAD -> "缺少资产\n<仅限检测>"
        EnvStatus.ERROR -> "未授权\n<点击重试>"
        EnvStatus.UNCHECKED -> "待检测\n<点击检测>"
    }
    val heroCaption = when {
        state.deviceModel.isNotBlank() -> state.deviceModel
        state.envStatus == EnvStatus.UNCHECKED -> "检查 ROOT 与杜比载荷"
        else -> "点按重新校验环境"
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .height(IntrinsicSize.Min),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        GlassCard(
            onClick = onCheckEnv,
            enabled = !state.busy,
            modifier = Modifier.weight(1f).fillMaxHeight(),
            insideMargin = PaddingValues(0.dp),
            tint = heroTint,
        ) {
            Box(Modifier.fillMaxSize().clipToBounds()) {
                Icon(
                    imageVector = heroIcon,
                    contentDescription = null,
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .offset(x = 38.dp, y = 44.dp)
                        .size(168.dp),
                    tint = emblemTint,
                )
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                ) {
                    Text(
                        text = heroHeadline,
                        fontSize = 20.sp,
                        lineHeight = 26.sp,
                        fontWeight = FontWeight.SemiBold,
                        color = colors.onSurface,
                    )
                    Spacer(Modifier.height(10.dp))
                    Text(
                        text = heroCaption,
                        fontSize = 12.sp,
                        color = colors.onSurfaceVariantSummary,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }

        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            GlassCard(
                onClick = onToggleSource,
                enabled = !state.busy,
                insideMargin = PaddingValues(16.dp),
            ) {
                Text(
                    text = "生成来源",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium,
                    color = colors.onSurfaceVariantSummary,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = if (state.moduleSourceMode == ModuleSourceMode.LIVE_SYSTEM) "系统直读" else "解包 ROM",
                    fontSize = 22.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = colors.onSurface,
                    maxLines = 1,
                )
            }

            val hasZip = state.lastZip != null
            GlassCard(
                onClick = if (hasZip) onSaveZip else null,
                enabled = !state.busy && hasZip,
                insideMargin = PaddingValues(16.dp),
            ) {
                Text(
                    text = "导出包状态",
                    fontSize = 14.sp,
                    fontWeight = FontWeight.Medium,
                    color = colors.onSurfaceVariantSummary,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = if (hasZip) "可导出" else "待生成",
                    fontSize = 22.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = if (hasZip) colors.primary else colors.onSurface,
                    maxLines = 1,
                )
            }
        }
    }
}
