package io.github.magaking.dolbybuilder.ui

import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.SaveableStateHolder
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import io.github.magaking.dolbybuilder.ui.components.AppIcons
import io.github.magaking.dolbybuilder.ui.components.BusyBackWindowDialog
import io.github.magaking.dolbybuilder.ui.components.ConfirmOperationWindowDialog
import io.github.magaking.dolbybuilder.ui.components.ToolbarButton
import io.github.magaking.dolbybuilder.ui.screens.AppearanceCallbacks
import io.github.magaking.dolbybuilder.ui.screens.AppearanceScreen
import io.github.magaking.dolbybuilder.ui.screens.AboutScreen
import io.github.magaking.dolbybuilder.ui.screens.ConsoleCleanupScreen
import io.github.magaking.dolbybuilder.ui.screens.ModuleScreen
import io.github.magaking.dolbybuilder.ui.screens.RomPatchScreen
import kotlin.math.absoluteValue
import kotlin.math.pow
import kotlin.math.roundToInt
import kotlin.math.sign
import top.yukonga.miuix.kmp.basic.MiuixScrollBehavior
import top.yukonga.miuix.kmp.basic.NavigationBar
import top.yukonga.miuix.kmp.basic.NavigationBarItem
import top.yukonga.miuix.kmp.basic.Scaffold
import top.yukonga.miuix.kmp.basic.TopAppBar
import com.kyant.backdrop.backdrops.LayerBackdrop
import com.kyant.backdrop.backdrops.layerBackdrop
import com.kyant.backdrop.backdrops.rememberLayerBackdrop
import top.yukonga.miuix.kmp.theme.ColorSchemeMode
import top.yukonga.miuix.kmp.theme.MiuixTheme
import top.yukonga.miuix.kmp.theme.ThemeController
import top.yukonga.miuix.kmp.utils.overScrollVertical

internal data class PatcherCallbacks(
    val onSelectTab: (Int) -> Unit,
    val onNavigate: (String) -> Unit,
    val onBack: () -> Unit,
    val onSelectModuleSource: (ModuleSourceMode) -> Unit,
    val onRomPathChange: (String) -> Unit,
    val onCheckEnv: () -> Unit,
    val onRequestBuildModule: () -> Unit,
    val onSaveZip: () -> Unit,
    val onRequestPatchRom: () -> Unit,
    val onQueryStatus: () -> Unit,
    val onRequestRestoreRom: () -> Unit,
    val onRequestCleanCache: () -> Unit,
    val onRequestDeleteBackups: () -> Unit,
    val onConfirmDialog: (ConfirmAction) -> Unit,
    val onDismissConfirm: () -> Unit,
    val onCancelTask: () -> Unit,
    val onCopyLogs: () -> Unit,
    val onClearLogs: () -> Unit,
    val onDismissBusyBack: () -> Unit,
    val appearance: AppearanceCallbacks,
)

@Composable
internal fun PatcherTheme(
    state: PatcherUiState,
    dark: Boolean,
    content: @Composable () -> Unit,
) {
    val mode = when {
        state.colorMode >= 3 || state.keyColor != 0 -> {
            if (dark) ColorSchemeMode.MonetDark else ColorSchemeMode.MonetLight
        }
        dark -> ColorSchemeMode.Dark
        else -> ColorSchemeMode.Light
    }
    val seed = if (state.colorMode >= 3) {
        state.accents.getOrNull(state.accentIndex)
            ?: state.keyColor.takeIf { it != 0 }?.let { Color(it) }
    } else {
        state.keyColor.takeIf { it != 0 }?.let { Color(it) }
    }
    val controller = remember(mode, seed) {
        ThemeController(colorSchemeMode = mode, keyColor = seed)
    }
    val hasBackdropContent = state.wallpaper != null
    MiuixTheme(controller = controller) {
        CompositionLocalProvider(
            LocalDarkTheme provides dark,
            LocalHasBackdropContent provides hasBackdropContent,
            LocalCardOpacity provides if (hasBackdropContent) (state.cardOpacity / 255f) else 1f,
            LocalGlassParams provides GlassParams(
                blur = state.glassBlur,
                range = state.glassRange,
                intensity = state.glassIntensity,
                edgeWidth = state.glassEdgeWidth,
                edgeTaper = state.glassEdgeTaper,
                edgeIntensity = state.glassEdgeIntensity,
            ),
            content = content,
        )
    }
}

@Composable
internal fun PatcherApp(
    state: PatcherUiState,
    callbacks: PatcherCallbacks,
    backProgress: Float = 0f,
    previousDestination: String? = null,
) {
    val backdrop = rememberLayerBackdrop()
    val glass = state.glass && state.glassAvailable
    val keyboardOpen = WindowInsets.ime.getBottom(LocalDensity.current) > 0
    val savedPages = rememberSaveableStateHolder()

    CompositionLocalProvider(
        LocalGlass provides glass,
        LocalGlassBackdrop provides backdrop,
    ) {
        Scaffold(
            modifier = Modifier.fillMaxSize(),
            contentWindowInsets = WindowInsets(0, 0, 0, 0),
            bottomBar = {
                if (state.route.isEmpty() && !keyboardOpen) {
                    val palette = MiuixTheme.colorScheme
                    if (glass) {
                        GlassNavigationBar(
                            selected = state.page,
                            backdrop = backdrop,
                            busy = state.busy,
                            hasError = state.taskStateKind == TaskStateKind.ERROR,
                            hasExportableZip = state.lastZip != null,
                            onSelected = callbacks.onSelectTab,
                        )
                    } else {
                        NavigationBar(
                            color = if (LocalHasBackdropContent.current) {
                                palette.surface.copy(alpha = LocalCardOpacity.current)
                            } else {
                                palette.surface
                            },
                            showDivider = true,
                            defaultWindowInsetsPadding = true,
                        ) {
                            NavigationBarItem(
                                selected = state.page == 0,
                                onClick = { callbacks.onSelectTab(0) },
                                icon = AppIcons.ModuleBox,
                                label = AppTab.MODULE.label,
                            )
                            NavigationBarItem(
                                selected = state.page == 1,
                                onClick = { callbacks.onSelectTab(1) },
                                icon = AppIcons.RomLayers,
                                label = AppTab.ROM.label,
                            )
                            NavigationBarItem(
                                selected = state.page == 2,
                                onClick = { callbacks.onSelectTab(2) },
                                icon = AppIcons.Terminal,
                                label = AppTab.MAINTENANCE.label,
                            )
                        }
                    }
                }
            },
        ) { padding ->
            PatcherAppContent(
                state = state,
                glass = glass,
                savedPages = savedPages,
                backdrop = backdrop,
                padding = padding,
                backProgress = backProgress,
                previousDestination = previousDestination,
                callbacks = callbacks,
            )
        }

        ConfirmOperationWindowDialog(
            action = state.pendingConfirm,
            romPath = state.romPath,
            busy = state.busy,
            onConfirm = callbacks.onConfirmDialog,
            onDismiss = callbacks.onDismissConfirm,
        )

        BusyBackWindowDialog(
            show = state.showExitBusyDialog,
            onKeepWaiting = callbacks.onDismissBusyBack,
            onRequestCancel = {
                callbacks.onDismissBusyBack()
                callbacks.onCancelTask()
            },
        )
    }
}

@Composable
private fun PatcherAppContent(
    state: PatcherUiState,
    glass: Boolean,
    savedPages: SaveableStateHolder,
    backdrop: LayerBackdrop,
    padding: PaddingValues,
    backProgress: Float,
    previousDestination: String?,
    callbacks: PatcherCallbacks,
) {
    Box(Modifier.fillMaxSize()) {
        // Non-recursive backdrop recording plane: stays full-window even when IME opens,
        // and NEVER wraps any drawBackdrop surface so hwui RenderThread never recurses.
        Box(
            Modifier
                .matchParentSize()
                .then(if (glass) Modifier.layerBackdrop(backdrop) else Modifier)
                .background(MiuixTheme.colorScheme.surface)
        ) {
            state.wallpaper?.let { wp ->
                Image(
                    bitmap = wp,
                    contentDescription = null,
                    modifier = Modifier.fillMaxSize(),
                    contentScale = ContentScale.Crop,
                    alpha = state.wallpaperOpacity / 255f,
                )
            }
        }

        val bottomPadding = if (state.route.isEmpty()) {
            padding.calculateBottomPadding()
        } else {
            WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
        }

        // Foreground content avoids IME while background plane stays stationary.
        val gestureProgress = backProgress.coerceIn(-1f, 1f)
        val contentModifier = Modifier
            .align(Alignment.TopCenter)
            .widthIn(max = 720.dp)
            .fillMaxSize()
            .imePadding()
            .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Horizontal))

        Box(contentModifier) {
            val currentDestination = state.route.ifEmpty { "tab:${state.page}" }
            val showBackPreview = previousDestination != null &&
                previousDestination != currentDestination &&
                gestureProgress.absoluteValue > 0f

            if (showBackPreview) {
                Box(Modifier.matchParentSize()) {
                    DestinationContent(
                        destination = previousDestination,
                        state = state,
                        bottom = bottomPadding,
                        callbacks = callbacks,
                        savedPages = savedPages,
                        stateKey = "back:$previousDestination",
                    )
                }
            }

            val speed = state.predictiveBackSpeed.coerceIn(0.1f, 1f)
            val responseCurve = 2.35f - (speed - 0.1f) / 0.9f * 1.30f
            val completionDuration = (420f - (speed - 0.1f) / 0.9f * 200f).roundToInt().coerceIn(160, 420)
            val foregroundModifier = Modifier
                .matchParentSize()
                .graphicsLayer {
                    val curved = gestureProgress.absoluteValue.pow(responseCurve)
                    val visual = curved * gestureProgress.sign * 0.48f
                    val dist = visual.absoluteValue
                    translationX = size.width * visual * 0.78f
                    alpha = 1f - dist * 0.10f
                    scaleX = 1f - dist * 0.018f
                    scaleY = 1f - dist * 0.018f
                    transformOrigin = TransformOrigin(if (visual < 0f) 1f else 0f, 0.5f)
                }

            Box(foregroundModifier) {
                Crossfade(
                    targetState = currentDestination,
                    animationSpec = tween(completionDuration),
                    label = "patcher-route"
                ) { destination ->
                    DestinationContent(
                        destination = destination,
                        state = state,
                        bottom = bottomPadding,
                        callbacks = callbacks,
                        savedPages = savedPages,
                        stateKey = "current:$destination",
                    )
                }
            }
        }
    }
}

@Composable
private fun DestinationContent(
    destination: String,
    state: PatcherUiState,
    bottom: Dp,
    callbacks: PatcherCallbacks,
    savedPages: SaveableStateHolder,
    stateKey: String,
) {
    savedPages.SaveableStateProvider(stateKey) {
        when (destination) {
            "tab:0" -> ModuleScreen(
                state = state,
                bottom = bottom,
                onCheckEnv = callbacks.onCheckEnv,
                onSelectSourceMode = callbacks.onSelectModuleSource,
                onRomPathChange = callbacks.onRomPathChange,
                onRequestBuildModule = callbacks.onRequestBuildModule,
                onSaveZip = callbacks.onSaveZip,
                onOpenAppearance = { callbacks.onNavigate("appearance") },
                onOpenGuide = { callbacks.onNavigate("guide") },
                onOpenConsoleTab = { callbacks.onSelectTab(2) },
                onCancelTask = callbacks.onCancelTask,
            )
            "tab:1" -> RomPatchScreen(
                state = state,
                bottom = bottom,
                onRomPathChange = callbacks.onRomPathChange,
                onRequestPatchRom = callbacks.onRequestPatchRom,
                onQueryStatus = callbacks.onQueryStatus,
                onRequestRestoreRom = callbacks.onRequestRestoreRom,
                onOpenAppearance = { callbacks.onNavigate("appearance") },
                onOpenGuide = { callbacks.onNavigate("guide") },
                onOpenConsoleTab = { callbacks.onSelectTab(2) },
                onCancelTask = callbacks.onCancelTask,
            )
            "tab:2" -> ConsoleCleanupScreen(
                state = state,
                bottom = bottom,
                onCopyLogs = callbacks.onCopyLogs,
                onClearLogs = callbacks.onClearLogs,
                onCancelTask = callbacks.onCancelTask,
                onRequestCleanCache = callbacks.onRequestCleanCache,
                onRequestDeleteBackups = callbacks.onRequestDeleteBackups,
                onOpenAppearance = { callbacks.onNavigate("appearance") },
                onOpenGuide = { callbacks.onNavigate("guide") },
            )
            "appearance" -> AppearanceScreen(
                state = state,
                bottom = bottom,
                onBack = callbacks.onBack,
                callbacks = callbacks.appearance,
            )
            "guide" -> AboutScreen(
                bottom = bottom,
                onBack = callbacks.onBack,
            )
            else -> ModuleScreen(
                state = state,
                bottom = bottom,
                onCheckEnv = callbacks.onCheckEnv,
                onSelectSourceMode = callbacks.onSelectModuleSource,
                onRomPathChange = callbacks.onRomPathChange,
                onRequestBuildModule = callbacks.onRequestBuildModule,
                onSaveZip = callbacks.onSaveZip,
                onOpenAppearance = { callbacks.onNavigate("appearance") },
                onOpenGuide = { callbacks.onNavigate("guide") },
                onOpenConsoleTab = { callbacks.onSelectTab(2) },
                onCancelTask = callbacks.onCancelTask,
            )
        }
    }
}

/**
 * Shared Miuix page template with collapsing large-title [TopAppBar], translucent collapsed scrim,
 * and [overScrollVertical] bounce physics.
 */
@Composable
internal fun PatcherPage(
    title: String,
    bottom: Dp,
    back: (() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {},
    content: LazyListScope.() -> Unit,
) {
    val scroll = MiuixScrollBehavior()
    val list = rememberLazyListState()
    Scaffold(
        containerColor = Color.Transparent,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        topBar = {
            TopAppBar(
                title = title,
                color = if (LocalDarkTheme.current) {
                    Color(0xFF424246).copy(alpha = 0.20f + 0.36f * scroll.state.collapsedFraction.coerceIn(0f, 1f))
                } else if (LocalHasBackdropContent.current) {
                    MiuixTheme.colorScheme.surface.copy(alpha = scroll.state.collapsedFraction * 0.94f)
                } else {
                    MiuixTheme.colorScheme.surface
                },
                scrollBehavior = scroll,
                navigationIcon = {
                    if (back != null) {
                        ToolbarButton(
                            icon = AppIcons.ArrowBack,
                            description = "返回",
                            onClick = back,
                        )
                    }
                },
                actions = actions,
            )
        },
    ) { padding ->
        LazyColumn(
            state = list,
            modifier = Modifier
                .fillMaxSize()
                .overScrollVertical()
                .nestedScroll(scroll.nestedScrollConnection),
            contentPadding = PaddingValues(
                start = 12.dp,
                end = 12.dp,
                top = padding.calculateTopPadding() + 10.dp,
                bottom = bottom + 24.dp,
            ),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            overscrollEffect = null,
            content = content,
        )
    }
}
