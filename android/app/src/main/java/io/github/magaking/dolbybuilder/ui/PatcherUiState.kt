package io.github.magaking.dolbybuilder.ui

import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import com.kyant.backdrop.Backdrop

enum class AppTab(val index: Int, val label: String, val pageTitle: String) {
    MODULE(0, "模块生成", "杜比模块生成器"),
    ROM(1, "ROM 内置", "ROM 原位内置"),
    MAINTENANCE(2, "维护与日志", "维护与日志");

    companion object {
        fun fromIndex(index: Int): AppTab = entries.firstOrNull { it.index == index } ?: MODULE
    }
}

enum class ModuleSourceMode {
    LIVE_SYSTEM,
    EXTRACTED_ROM
}

enum class EnvStatus {
    UNCHECKED,
    READY,
    NO_PAYLOAD,
    ERROR
}

enum class TaskStateKind {
    IDLE,
    RUNNING,
    SUCCESS,
    ERROR
}

@Immutable
data class ZipArtifactInfo(
    val path: String,
    val fileName: String,
    val sizeBytes: Long,
    val lastModifiedMillis: Long
)

enum class ConfirmAction {
    GENERATE_LIVE_MODULE,
    GENERATE_ROM_MODULE,
    PATCH_ROM,
    RESTORE_ROM,
    CLEAN_CACHE,
    DELETE_BACKUPS
}

/** Tunable liquid-glass parameters surfaced in the appearance subpage. */
@Immutable
data class GlassParams(
    val blur: Float = 2f,
    val range: Float = 20f,
    val intensity: Float = 60f,
    val edgeWidth: Float = 1.5f,
    val edgeTaper: Float = 0.25f,
    val edgeIntensity: Float = 1f,
)

@Immutable
data class PatcherUiState(
    val page: Int = 0,
    val route: String = "",
    val moduleSourceMode: ModuleSourceMode = ModuleSourceMode.LIVE_SYSTEM,
    val romPath: String = "",
    val romPathError: String? = null,
    val envStatus: EnvStatus = EnvStatus.UNCHECKED,
    val deviceModel: String = "",
    val envSummary: String = "检测运行环境",
    val busy: Boolean = false,
    val activeOperationLabel: String = "",
    val statusText: String = "等待操作",
    val taskStateKind: TaskStateKind = TaskStateKind.IDLE,
    val elapsedSeconds: Int = 0,
    val logs: String = "尚无构建记录",
    val lastLogLine: String = "",
    val lastZip: ZipArtifactInfo? = null,
    val pendingConfirm: ConfirmAction? = null,
    val showExitBusyDialog: Boolean = false,
    // Appearance & Liquid Glass preferences
    val colorMode: Int = 0,
    val keyColor: Int = 0,
    val accentIndex: Int = 0,
    val accents: List<Color> = emptyList(),
    val wallpaper: ImageBitmap? = null,
    val wallpaperOpacity: Int = 115,
    val cardOpacity: Int = 224,
    val predictiveBack: Boolean = true,
    val predictiveBackSpeed: Float = 0.35f,
    val glass: Boolean = true,
    val glassAvailable: Boolean = false,
    val glassBlur: Float = 2f,
    val glassRange: Float = 20f,
    val glassIntensity: Float = 60f,
    val glassEdgeWidth: Float = 1.5f,
    val glassEdgeTaper: Float = 0.25f,
    val glassEdgeIntensity: Float = 1f,
) {
    val selectedTab: AppTab get() = AppTab.fromIndex(page)
}

internal val LocalGlass = staticCompositionLocalOf { false }
internal val LocalGlassBackdrop = staticCompositionLocalOf<Backdrop?> { null }
internal val LocalGlassParams = staticCompositionLocalOf { GlassParams() }
internal val LocalCardOpacity = staticCompositionLocalOf { 1f }
internal val LocalHasBackdropContent = staticCompositionLocalOf { true }
internal val LocalDarkTheme = staticCompositionLocalOf { true }
