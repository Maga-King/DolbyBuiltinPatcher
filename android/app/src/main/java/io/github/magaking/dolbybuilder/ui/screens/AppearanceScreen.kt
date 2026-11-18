package io.github.magaking.dolbybuilder.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.magaking.dolbybuilder.BuildConfig
import io.github.magaking.dolbybuilder.ui.GlassCard
import io.github.magaking.dolbybuilder.ui.PatcherPage
import io.github.magaking.dolbybuilder.ui.PatcherUiState
import io.github.magaking.dolbybuilder.ui.PreferenceCard
import io.github.magaking.dolbybuilder.ui.components.AppIcons
import io.github.magaking.dolbybuilder.ui.components.ToolbarButton
import io.github.magaking.dolbybuilder.ui.theme.PresetAccentPalette
import java.util.Locale
import kotlin.math.roundToInt
import top.yukonga.miuix.kmp.basic.BasicComponent
import top.yukonga.miuix.kmp.basic.Icon
import top.yukonga.miuix.kmp.basic.Slider
import top.yukonga.miuix.kmp.basic.SmallTitle
import top.yukonga.miuix.kmp.basic.Text
import top.yukonga.miuix.kmp.preference.ArrowPreference
import top.yukonga.miuix.kmp.preference.OverlayDropdownPreference
import top.yukonga.miuix.kmp.preference.SwitchPreference
import top.yukonga.miuix.kmp.theme.MiuixTheme

internal data class AppearanceCallbacks(
    val onColorModeChange: (Int) -> Unit,
    val onKeyColorChange: (Int) -> Unit,
    val onAccentIndexChange: (Int) -> Unit,
    val onPickWallpaper: () -> Unit,
    val onClearWallpaper: () -> Unit,
    val onWallpaperOpacityChange: (Int) -> Unit,
    val onCardOpacityChange: (Int) -> Unit,
    val onPredictiveBackChange: (Boolean) -> Unit,
    val onPredictiveBackSpeedChange: (Float) -> Unit,
    val onGlassChange: (Boolean) -> Unit,
    val onGlassBlurChange: (Float) -> Unit,
    val onGlassRangeChange: (Float) -> Unit,
    val onGlassIntensityChange: (Float) -> Unit,
    val onGlassEdgeWidthChange: (Float) -> Unit,
    val onGlassEdgeTaperChange: (Float) -> Unit,
    val onGlassEdgeIntensityChange: (Float) -> Unit,
    val onGlassReset: () -> Unit,
)

@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun AppearanceScreen(
    state: PatcherUiState,
    bottom: Dp,
    onBack: () -> Unit,
    callbacks: AppearanceCallbacks,
) {
    val monet = state.colorMode >= 3
    var cardOpacity by remember(state.cardOpacity) { mutableFloatStateOf(state.cardOpacity.toFloat()) }
    var wallpaperOpacity by remember(state.wallpaperOpacity) { mutableFloatStateOf(state.wallpaperOpacity.toFloat()) }
    var glassBlur by remember(state.glassBlur) { mutableFloatStateOf(state.glassBlur) }
    var glassRange by remember(state.glassRange) { mutableFloatStateOf(state.glassRange) }
    var glassIntensity by remember(state.glassIntensity) { mutableFloatStateOf(state.glassIntensity) }
    var glassEdgeWidth by remember(state.glassEdgeWidth) { mutableFloatStateOf(state.glassEdgeWidth) }
    var glassEdgeTaper by remember(state.glassEdgeTaper) { mutableFloatStateOf(state.glassEdgeTaper) }
    var glassEdgeIntensity by remember(state.glassEdgeIntensity) { mutableFloatStateOf(state.glassEdgeIntensity) }
    var predictiveBackSpeed by remember(state.predictiveBackSpeed) { mutableFloatStateOf(state.predictiveBackSpeed) }

    PatcherPage(
        title = "外观与液态玻璃",
        bottom = bottom,
        back = onBack,
    ) {
        item(key = "theme-mode") {
            PreferenceCard {
                OverlayDropdownPreference(
                    title = "深色模式",
                    items = listOf("跟随系统", "关闭（浅色）", "开启（深色）"),
                    selectedIndex = state.colorMode % 3,
                    onSelectedIndexChange = { idx ->
                        callbacks.onColorModeChange(idx + if (monet) 3 else 0)
                    },
                )
                SwitchPreference(
                    checked = monet,
                    onCheckedChange = { enabled ->
                        callbacks.onColorModeChange((state.colorMode % 3) + if (enabled) 3 else 0)
                    },
                    title = "动态配色 (Monet)",
                    summary = "从自定义壁纸或主题种子色生成动态色板",
                )
            }
        }

        item(key = "accent-header") {
            SmallTitle("主题色")
        }

        item(key = "accent-card") {
            PreferenceCard {
                val useWallpaperAccents = monet && state.accents.isNotEmpty()
                val swatches = if (useWallpaperAccents) {
                    state.accents
                } else {
                    PresetAccentPalette.map { if (it == 0) Color(0xFF2B6EF6) else Color(it) }
                }
                if (monet && state.accents.isEmpty()) {
                    BasicComponent(
                        title = "未选择自定义壁纸",
                        summary = "你也可以在下方直接点选预设种子色驱动动态色板",
                    )
                }
                FlowRow(
                    modifier = Modifier
                        .fillMaxWidth()
                        .selectableGroup()
                        .padding(horizontal = 12.dp, vertical = 10.dp),
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    swatches.forEachIndexed { index, color ->
                        val selected = if (useWallpaperAccents) {
                            index == state.accentIndex
                        } else {
                            PresetAccentPalette[index] == state.keyColor
                        }
                        val label = if (!useWallpaperAccents && index == 0) "默认蓝" else "主题色 ${index + 1}"
                        Box(
                            modifier = Modifier
                                .size(48.dp)
                                .clip(CircleShape)
                                .selectable(
                                    selected = selected,
                                    role = Role.RadioButton,
                                    onClick = {
                                        if (useWallpaperAccents) {
                                            callbacks.onAccentIndexChange(index)
                                        } else {
                                            callbacks.onKeyColorChange(PresetAccentPalette[index])
                                        }
                                    },
                                )
                                .semantics { contentDescription = label },
                            contentAlignment = Alignment.Center,
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(34.dp)
                                    .background(color, CircleShape)
                                    .then(
                                        if (selected) {
                                            Modifier.border(
                                                2.dp,
                                                MiuixTheme.colorScheme.onSurface.copy(alpha = 0.25f),
                                                CircleShape,
                                            )
                                        } else {
                                            Modifier
                                        }
                                    ),
                                contentAlignment = Alignment.Center,
                            ) {
                                if (selected) {
                                    Icon(
                                        imageVector = AppIcons.Check,
                                        contentDescription = null,
                                        modifier = Modifier.size(18.dp),
                                        tint = if (color.luminance() > 0.5f) Color.Black else Color.White,
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }

        item(key = "glass-header") {
            SmallTitle("液态玻璃与导航")
        }

        item(key = "glass-card") {
            PreferenceCard {
                SwitchPreference(
                    checked = state.glass,
                    onCheckedChange = callbacks.onGlassChange,
                    title = "液态玻璃 (Liquid Glass)",
                    summary = if (!state.glassAvailable) {
                        "当前设备不支持（需 Android 13+ 硬件加速且非低内存设备），已自动回退普通样式"
                    } else {
                        "底栏弹簧胶囊、卡片与筛选栏启用实时 AGSL 边缘折射与高光"
                    },
                )
                if (state.glass) {
                    BasicComponent(
                        title = "模糊度",
                        summary = "${glassBlur.roundToInt()} dp",
                        bottomAction = {
                            Slider(
                                value = glassBlur,
                                onValueChange = { glassBlur = it },
                                valueRange = 0f..16f,
                                onValueChangeFinished = { callbacks.onGlassBlurChange(glassBlur) },
                            )
                        },
                    )
                    BasicComponent(
                        title = "折射范围",
                        summary = "${glassRange.roundToInt()} dp",
                        bottomAction = {
                            Slider(
                                value = glassRange,
                                onValueChange = { glassRange = it },
                                valueRange = 0f..48f,
                                onValueChangeFinished = { callbacks.onGlassRangeChange(glassRange) },
                            )
                        },
                    )
                    BasicComponent(
                        title = "折射强度",
                        summary = "${glassIntensity.roundToInt()} dp",
                        bottomAction = {
                            Slider(
                                value = glassIntensity,
                                onValueChange = { glassIntensity = it },
                                valueRange = 0f..120f,
                                onValueChangeFinished = { callbacks.onGlassIntensityChange(glassIntensity) },
                            )
                        },
                    )
                    BasicComponent(
                        title = "边缘高光强度",
                        summary = "${(glassEdgeIntensity * 100).roundToInt()}%",
                        bottomAction = {
                            Slider(
                                value = glassEdgeIntensity,
                                onValueChange = { glassEdgeIntensity = it },
                                valueRange = 0f..2f,
                                onValueChangeFinished = { callbacks.onGlassEdgeIntensityChange(glassEdgeIntensity) },
                            )
                        },
                    )
                    BasicComponent(
                        title = "边缘宽度",
                        summary = String.format(Locale.US, "%.1f dp", glassEdgeWidth),
                        bottomAction = {
                            Slider(
                                value = glassEdgeWidth,
                                onValueChange = { glassEdgeWidth = it },
                                valueRange = 0f..6f,
                                onValueChangeFinished = { callbacks.onGlassEdgeWidthChange(glassEdgeWidth) },
                            )
                        },
                    )
                    BasicComponent(
                        title = "边缘渐变",
                        summary = String.format(Locale.US, "%.2f", glassEdgeTaper),
                        bottomAction = {
                            Slider(
                                value = glassEdgeTaper,
                                onValueChange = { glassEdgeTaper = it },
                                valueRange = 0f..1f,
                                onValueChangeFinished = { callbacks.onGlassEdgeTaperChange(glassEdgeTaper) },
                            )
                        },
                    )
                    BasicComponent(
                        title = "恢复默认光学参数",
                        summary = "重置模糊度 (2dp)、折射范围 (20dp)、强度 (60dp) 与边缘高光",
                        endActions = {
                            ToolbarButton(
                                icon = AppIcons.Refresh,
                                description = "恢复默认值",
                                onClick = callbacks.onGlassReset,
                            )
                        },
                    )
                }
                SwitchPreference(
                    checked = state.predictiveBack,
                    onCheckedChange = callbacks.onPredictiveBackChange,
                    title = "预测性返回手势",
                    summary = "子页面返回时跟随系统边缘滑动手势实时预览",
                )
                if (state.predictiveBack) {
                    BasicComponent(
                        title = "返回动画速度",
                        summary = "${(predictiveBackSpeed * 100).roundToInt()}% · 越低越舒缓",
                        bottomAction = {
                            Slider(
                                value = predictiveBackSpeed,
                                onValueChange = { predictiveBackSpeed = it },
                                valueRange = 0.1f..1f,
                                onValueChangeFinished = { callbacks.onPredictiveBackSpeedChange(predictiveBackSpeed) },
                            )
                        },
                    )
                }
            }
        }

        item(key = "bg-header") {
            SmallTitle("背景与自定义壁纸")
        }

        item(key = "bg-card") {
            PreferenceCard {
                ArrowPreference(
                    title = "选择自定义壁纸",
                    summary = "通过系统相册选择器读取单张图片（零存储权限）",
                    onClick = callbacks.onPickWallpaper,
                )
                if (state.wallpaper != null) {
                    ArrowPreference(
                        title = "移除自定义壁纸",
                        summary = "清除已保存的应用内背景图片",
                        onClick = callbacks.onClearWallpaper,
                    )
                    BasicComponent(
                        title = "壁纸不透明度",
                        summary = "${(wallpaperOpacity / 255f * 100).roundToInt()}%",
                        bottomAction = {
                            Slider(
                                value = wallpaperOpacity,
                                onValueChange = { wallpaperOpacity = it },
                                valueRange = 0f..255f,
                                onValueChangeFinished = { callbacks.onWallpaperOpacityChange(wallpaperOpacity.roundToInt()) },
                            )
                        },
                    )
                }
                BasicComponent(
                    title = "普通卡片不透明度",
                    summary = "${(cardOpacity / 255f * 100).roundToInt()}% · 关闭液态玻璃时的表面透明度",
                    bottomAction = {
                        Slider(
                            value = cardOpacity,
                            onValueChange = { cardOpacity = it },
                            valueRange = 100f..255f,
                            onValueChangeFinished = { callbacks.onCardOpacityChange(cardOpacity.roundToInt()) },
                        )
                    },
                )
            }
        }
    }
}

@Composable
internal fun AboutScreen(
    bottom: Dp,
    onBack: () -> Unit,
) {
    val colors = MiuixTheme.colorScheme

    PatcherPage(
        title = "关于",
        bottom = bottom,
        back = onBack,
    ) {
        item(key = "about-hero") {
            GlassCard(insideMargin = PaddingValues(20.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        imageVector = AppIcons.Equalizer,
                        contentDescription = null,
                        tint = colors.primary,
                        modifier = Modifier.size(32.dp),
                    )
                    Spacer(Modifier.width(12.dp))
                    Column {
                        Text(
                            text = "杜比模块生成器",
                            fontSize = 20.sp,
                            fontWeight = FontWeight.SemiBold,
                            color = colors.onSurface,
                        )
                        Text(
                            text = "v${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE}) · 署名：科比",
                            fontSize = 13.sp,
                            color = colors.onSurfaceVariantSummary,
                        )
                    }
                }
            }
        }

        item(key = "oss-header") {
            SmallTitle("开源致谢与许可")
        }

        item(key = "oss-card") {
            PreferenceCard {
                BasicComponent(
                    title = "MIUIX 0.9.3",
                    summary = "compose-miuix-ui contributors · Apache-2.0",
                )
                BasicComponent(
                    title = "AndroidLiquidGlass 2.0.1",
                    summary = "Kyant · Apache-2.0（许可证随 APK assets/licenses 附带）",
                )
                BasicComponent(
                    title = "SELinuxProject secilc & libsepol / KernelSU",
                    summary = "感谢 SELinuxProject、KernelSU 与 Android/AOSP 开源社区",
                )
            }
        }
    }
}
