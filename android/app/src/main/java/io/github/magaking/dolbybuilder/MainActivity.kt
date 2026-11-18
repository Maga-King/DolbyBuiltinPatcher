package io.github.magaking.dolbybuilder

import android.app.ActivityManager
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.WindowManager
import android.widget.Toast
import androidx.activity.BackEventCompat
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.PredictiveBackHandler
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat
import androidx.lifecycle.lifecycleScope
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import io.github.magaking.dolbybuilder.ui.AppTab
import io.github.magaking.dolbybuilder.ui.ConfirmAction
import io.github.magaking.dolbybuilder.ui.EnvStatus
import io.github.magaking.dolbybuilder.ui.ModuleSourceMode
import io.github.magaking.dolbybuilder.ui.PatcherApp
import io.github.magaking.dolbybuilder.ui.PatcherCallbacks
import io.github.magaking.dolbybuilder.ui.PatcherTheme
import io.github.magaking.dolbybuilder.ui.PatcherUiState
import io.github.magaking.dolbybuilder.ui.TaskStateKind
import io.github.magaking.dolbybuilder.ui.ZipArtifactInfo
import io.github.magaking.dolbybuilder.ui.components.copyTextToClipboard
import io.github.magaking.dolbybuilder.ui.screens.AppearanceCallbacks
import io.github.magaking.dolbybuilder.ui.theme.THEME_PREFS
import io.github.magaking.dolbybuilder.ui.theme.clearStoredWallpaper
import io.github.magaking.dolbybuilder.ui.theme.decodeAndStoreWallpaper
import io.github.magaking.dolbybuilder.ui.theme.extractWallpaperAccents
import io.github.magaking.dolbybuilder.ui.theme.loadStoredWallpaper
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

class MainActivity : ComponentActivity() {

    private val worker: ExecutorService = Executors.newSingleThreadExecutor()
    private val mainHandler = Handler(Looper.getMainLooper())

    @Volatile
    private var bridge: RootBridge? = null
    private var lastZipFile: File? = null

    private var uiState by mutableStateOf(PatcherUiState())
    private var routeStack by mutableStateOf(emptyList<String>())

    private val themePrefs by lazy { getSharedPreferences(THEME_PREFS, MODE_PRIVATE) }

    private val saveZipLauncher = registerForActivityResult(
        ActivityResultContracts.CreateDocument("application/zip")
    ) { uri: Uri? ->
        if (uri != null) {
            exportZipToUri(uri)
        }
    }

    private val pickWallpaperLauncher = registerForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        if (uri != null) {
            lifecycleScope.launch {
                val pair = withContext(Dispatchers.IO) {
                    val bmp = decodeAndStoreWallpaper(this@MainActivity, uri)
                    if (bmp != null) {
                        bmp.asImageBitmap() to extractWallpaperAccents(bmp)
                    } else {
                        null
                    }
                }
                if (pair != null) {
                    uiState = uiState.copy(
                        wallpaper = pair.first,
                        accents = pair.second,
                        accentIndex = 0,
                    )
                    toast("壁纸已应用")
                } else {
                    toast("无法读取所选图片，请更换图片重试")
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        WindowCompat.setDecorFitsSystemWindows(window, false)
        @Suppress("DEPRECATION")
        window.statusBarColor = android.graphics.Color.TRANSPARENT
        @Suppress("DEPRECATION")
        window.navigationBarColor = android.graphics.Color.TRANSPARENT

        val prefs = getPreferences(MODE_PRIVATE)
        val savedRomPath = prefs.getString("romPath", "") ?: ""
        val storedZip = prefs.getString("lastZip", null)?.let { File(it) }?.takeIf { it.isFile }
        lastZipFile = storedZip

        // Migrate legacy themeMode if present on first launch of Miuix UI
        val defaultColorMode = when (prefs.getString("themeMode", null)) {
            "light" -> 1
            "dark" -> 2
            "auto" -> 3
            else -> 0
        }

        uiState = uiState.copy(
            page = (savedInstanceState?.getInt("page") ?: 0).coerceIn(0, 2),
            route = savedInstanceState?.getString("route").orEmpty(),
            romPath = savedRomPath,
            lastZip = storedZip?.toArtifactInfo(),
            colorMode = themePrefs.getInt("color_mode", defaultColorMode).coerceIn(0, 5),
            keyColor = themePrefs.getInt("key_color", 0),
            accentIndex = themePrefs.getInt("accent_index", 0),
            wallpaperOpacity = themePrefs.getInt("wallpaper_opacity", 115).coerceIn(0, 255),
            cardOpacity = themePrefs.getInt("card_opacity", 224).coerceIn(100, 255),
            predictiveBack = themePrefs.getBoolean("predictive_back", true),
            predictiveBackSpeed = themePrefs.getFloat("predictive_back_speed", 0.35f).coerceIn(0.1f, 1f),
            glass = themePrefs.getBoolean("liquid_glass", true),
            glassBlur = themePrefs.getFloat("glass_blur", 2f).coerceIn(0f, 16f),
            glassRange = themePrefs.getFloat("glass_range", 20f).coerceIn(0f, 48f),
            glassIntensity = themePrefs.getFloat("glass_intensity", 60f).coerceIn(0f, 120f),
            glassEdgeWidth = themePrefs.getFloat("glass_edge_width", 1.5f).coerceIn(0f, 6f),
            glassEdgeTaper = themePrefs.getFloat("glass_edge_taper", 0.25f).coerceIn(0f, 1f),
            glassEdgeIntensity = themePrefs.getFloat("glass_edge_intensity", 1f).coerceIn(0f, 2f),
        )
        routeStack = savedInstanceState?.getStringArrayList("route_stack")?.toList().orEmpty()

        lifecycleScope.launch {
            val loaded = withContext(Dispatchers.IO) {
                loadStoredWallpaper(this@MainActivity)?.let { bmp ->
                    bmp.asImageBitmap() to extractWallpaperAccents(bmp)
                }
            }
            if (loaded != null) {
                uiState = uiState.copy(wallpaper = loaded.first, accents = loaded.second)
            }
        }

        setContent {
            val systemDark = isSystemInDarkTheme()
            val dark = uiState.colorMode % 3 == 2 || (uiState.colorMode % 3 == 0 && systemDark)
            val lowRam = remember {
                (getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager).isLowRamDevice
            }
            val glassAvailable = useLiquidGlass(
                enabled = true,
                apiLevel = Build.VERSION.SDK_INT,
                hardwareAccelerated = LocalView.current.isHardwareAccelerated,
                lowRam = lowRam,
            )
            val backProgress = remember { mutableFloatStateOf(0f) }

            SideEffect {
                WindowCompat.getInsetsController(window, window.decorView).apply {
                    isAppearanceLightStatusBars = !dark
                    isAppearanceLightNavigationBars = !dark
                }
            }

            LaunchedEffect(uiState.busy, uiState.activeOperationLabel) {
                if (uiState.busy) {
                    uiState = uiState.copy(elapsedSeconds = 0)
                    while (true) {
                        delay(1000L)
                        uiState = uiState.copy(elapsedSeconds = uiState.elapsedSeconds + 1)
                    }
                }
            }

            val previousDestination = routeStack.lastOrNull()
                ?: uiState.route.takeIf { it.isNotEmpty() }?.let { "tab:${uiState.page}" }
            val hasDialogOpen = uiState.pendingConfirm != null || uiState.showExitBusyDialog
            val canNavigateSubpageBack = previousDestination != null && !hasDialogOpen

            PredictiveBackHandler(enabled = canNavigateSubpageBack && uiState.predictiveBack) { progress ->
                try {
                    progress.collect { event ->
                        backProgress.floatValue = signedBackProgress(event)
                    }
                    backProgress.floatValue = 0f
                    navigateBack()
                } finally {
                    backProgress.floatValue = 0f
                }
            }
            BackHandler(enabled = canNavigateSubpageBack && !uiState.predictiveBack) {
                navigateBack()
            }
            BackHandler(enabled = uiState.busy && !canNavigateSubpageBack && !hasDialogOpen) {
                uiState = uiState.copy(showExitBusyDialog = true)
            }

            val visibleState = uiState.copy(glassAvailable = glassAvailable)
            val callbacks = remember {
                createCallbacks()
            }

            PatcherTheme(state = visibleState, dark = dark) {
                PatcherApp(
                    state = visibleState,
                    callbacks = callbacks,
                    backProgress = backProgress.floatValue,
                    previousDestination = previousDestination,
                )
            }
        }
    }

    private fun createCallbacks(): PatcherCallbacks = PatcherCallbacks(
        onSelectTab = { index ->
            routeStack = emptyList()
            uiState = uiState.copy(
                page = index.coerceIn(0, 2),
                route = "",
                romPathError = null,
            )
        },
        onNavigate = { targetRoute ->
            val current = uiState.route.ifEmpty { "tab:${uiState.page}" }
            if (targetRoute != current) {
                routeStack = routeStack + current
                uiState = uiState.copy(route = targetRoute)
            }
        },
        onBack = { navigateBack() },
        onSelectModuleSource = { mode ->
            uiState = uiState.copy(moduleSourceMode = mode, romPathError = null)
        },
        onRomPathChange = { value ->
            uiState = uiState.copy(romPath = value, romPathError = null)
            getPreferences(MODE_PRIVATE).edit().putString("romPath", value.trim()).apply()
        },
        onCheckEnv = { startTask("check") },
        onRequestBuildModule = {
            if (uiState.moduleSourceMode == ModuleSourceMode.LIVE_SYSTEM) {
                uiState = uiState.copy(pendingConfirm = ConfirmAction.GENERATE_LIVE_MODULE)
            } else if (validateRomPathOrFocus(AppTab.MODULE)) {
                uiState = uiState.copy(pendingConfirm = ConfirmAction.GENERATE_ROM_MODULE)
            }
        },
        onSaveZip = {
            val file = lastZipFile
            if (file != null && file.isFile && !uiState.busy) {
                saveZipLauncher.launch("杜比全景+解码器_KSU.zip")
            } else {
                toast("请先生成模块")
            }
        },
        onRequestPatchRom = {
            if (validateRomPathOrFocus(AppTab.ROM)) {
                uiState = uiState.copy(pendingConfirm = ConfirmAction.PATCH_ROM)
            }
        },
        onQueryStatus = {
            if (validateRomPathOrFocus(AppTab.ROM)) {
                startTask("status")
            }
        },
        onRequestRestoreRom = {
            if (validateRomPathOrFocus(AppTab.ROM)) {
                uiState = uiState.copy(pendingConfirm = ConfirmAction.RESTORE_ROM)
            }
        },
        onRequestCleanCache = {
            uiState = uiState.copy(pendingConfirm = ConfirmAction.CLEAN_CACHE)
        },
        onRequestDeleteBackups = {
            if (validateRomPathOrFocus(AppTab.ROM)) {
                uiState = uiState.copy(pendingConfirm = ConfirmAction.DELETE_BACKUPS)
            } else {
                toast("请先输入需要清理备份的目标 ROM 解包目录")
            }
        },
        onConfirmDialog = { action ->
            uiState = uiState.copy(pendingConfirm = null)
            when (action) {
                ConfirmAction.GENERATE_LIVE_MODULE -> startTask("generate")
                ConfirmAction.GENERATE_ROM_MODULE -> startTask("rom-module")
                ConfirmAction.PATCH_ROM -> startTask("patch")
                ConfirmAction.RESTORE_ROM -> startTask("restore")
                ConfirmAction.CLEAN_CACHE -> startTask("cache")
                ConfirmAction.DELETE_BACKUPS -> startTask("backups")
            }
        },
        onDismissConfirm = { uiState = uiState.copy(pendingConfirm = null) },
        onCancelTask = {
            bridge?.cancel()
            appendLog("已请求取消，将在安全边界结束当前任务。")
        },
        onCopyLogs = {
            copyTextToClipboard(this, "DolbyPatcherLogs", uiState.logs)
            toast("日志已复制到剪贴板")
        },
        onClearLogs = {
            if (!uiState.busy) {
                uiState = uiState.copy(
                    logs = "尚无构建记录",
                    lastLogLine = "",
                    taskStateKind = TaskStateKind.IDLE,
                    elapsedSeconds = 0,
                )
            }
        },
        onDismissBusyBack = { uiState = uiState.copy(showExitBusyDialog = false) },
        appearance = AppearanceCallbacks(
            onColorModeChange = { mode ->
                val clamped = mode.coerceIn(0, 5)
                themePrefs.edit().putInt("color_mode", clamped).apply()
                uiState = uiState.copy(colorMode = clamped)
            },
            onKeyColorChange = { color ->
                themePrefs.edit().putInt("key_color", color).apply()
                uiState = uiState.copy(keyColor = color)
            },
            onAccentIndexChange = { idx ->
                themePrefs.edit().putInt("accent_index", idx).apply()
                uiState = uiState.copy(accentIndex = idx)
            },
            onPickWallpaper = { pickWallpaperLauncher.launch("image/*") },
            onClearWallpaper = {
                clearStoredWallpaper(this)
                uiState = uiState.copy(wallpaper = null, accents = emptyList(), accentIndex = 0)
                toast("已移除自定义壁纸")
            },
            onWallpaperOpacityChange = { value ->
                val v = value.coerceIn(0, 255)
                themePrefs.edit().putInt("wallpaper_opacity", v).apply()
                uiState = uiState.copy(wallpaperOpacity = v)
            },
            onCardOpacityChange = { value ->
                val v = value.coerceIn(100, 255)
                themePrefs.edit().putInt("card_opacity", v).apply()
                uiState = uiState.copy(cardOpacity = v)
            },
            onPredictiveBackChange = { enabled ->
                themePrefs.edit().putBoolean("predictive_back", enabled).apply()
                uiState = uiState.copy(predictiveBack = enabled)
            },
            onPredictiveBackSpeedChange = { speed ->
                val v = speed.coerceIn(0.1f, 1f)
                themePrefs.edit().putFloat("predictive_back_speed", v).apply()
                uiState = uiState.copy(predictiveBackSpeed = v)
            },
            onGlassChange = { enabled ->
                themePrefs.edit().putBoolean("liquid_glass", enabled).apply()
                uiState = uiState.copy(glass = enabled)
            },
            onGlassBlurChange = { v ->
                val c = v.coerceIn(0f, 16f)
                themePrefs.edit().putFloat("glass_blur", c).apply()
                uiState = uiState.copy(glassBlur = c)
            },
            onGlassRangeChange = { v ->
                val c = v.coerceIn(0f, 48f)
                themePrefs.edit().putFloat("glass_range", c).apply()
                uiState = uiState.copy(glassRange = c)
            },
            onGlassIntensityChange = { v ->
                val c = v.coerceIn(0f, 120f)
                themePrefs.edit().putFloat("glass_intensity", c).apply()
                uiState = uiState.copy(glassIntensity = c)
            },
            onGlassEdgeWidthChange = { v ->
                val c = v.coerceIn(0f, 6f)
                themePrefs.edit().putFloat("glass_edge_width", c).apply()
                uiState = uiState.copy(glassEdgeWidth = c)
            },
            onGlassEdgeTaperChange = { v ->
                val c = v.coerceIn(0f, 1f)
                themePrefs.edit().putFloat("glass_edge_taper", c).apply()
                uiState = uiState.copy(glassEdgeTaper = c)
            },
            onGlassEdgeIntensityChange = { v ->
                val c = v.coerceIn(0f, 2f)
                themePrefs.edit().putFloat("glass_edge_intensity", c).apply()
                uiState = uiState.copy(glassEdgeIntensity = c)
            },
            onGlassReset = {
                themePrefs.edit()
                    .putFloat("glass_blur", 2f)
                    .putFloat("glass_range", 20f)
                    .putFloat("glass_intensity", 60f)
                    .putFloat("glass_edge_width", 1.5f)
                    .putFloat("glass_edge_taper", 0.25f)
                    .putFloat("glass_edge_intensity", 1f)
                    .apply()
                uiState = uiState.copy(
                    glassBlur = 2f,
                    glassRange = 20f,
                    glassIntensity = 60f,
                    glassEdgeWidth = 1.5f,
                    glassEdgeTaper = 0.25f,
                    glassEdgeIntensity = 1f,
                )
                toast("已恢复液态玻璃默认参数")
            },
        ),
    )

    private fun signedBackProgress(event: BackEventCompat): Float =
        event.progress * if (event.swipeEdge == BackEventCompat.EDGE_RIGHT) -1f else 1f

    private fun navigateBack() {
        val destination = routeStack.lastOrNull()
        if (destination != null) {
            routeStack = routeStack.dropLast(1)
            if (destination.startsWith("tab:")) {
                val tabIdx = destination.removePrefix("tab:").toIntOrNull()?.coerceIn(0, 2) ?: 0
                uiState = uiState.copy(page = tabIdx, route = "")
            } else {
                uiState = uiState.copy(route = destination)
            }
        } else {
            uiState = uiState.copy(route = "")
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        outState.putInt("page", uiState.page)
        outState.putString("route", uiState.route)
        outState.putStringArrayList("route_stack", ArrayList(routeStack))
        super.onSaveInstanceState(outState)
    }

    private fun toast(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }

    private fun validateRomPathOrFocus(preferredTab: AppTab): Boolean {
        val target = uiState.romPath.trim()
        if (target.isEmpty()) {
            routeStack = emptyList()
            uiState = uiState.copy(
                page = preferredTab.index,
                route = "",
                romPathError = "请输入手机内 ROM 解包目录（如 /data/DNA/DNA_01）",
            )
            return false
        }
        return true
    }

    private fun setBusyState(
        value: Boolean,
        operationLabel: String = uiState.activeOperationLabel,
    ) {
        uiState = uiState.copy(
            busy = value,
            activeOperationLabel = if (value) operationLabel else "",
            showExitBusyDialog = if (!value) false else uiState.showExitBusyDialog,
        )
        if (value) {
            window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        } else {
            window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    private fun appendLog(line: String) {
        val clean = line.trimEnd()
        if (clean.isEmpty()) return
        mainHandler.post {
            if (isDestroyed) return@post
            val base = if (uiState.logs == "尚无构建记录" || uiState.logs.isBlank()) {
                clean
            } else {
                uiState.logs + "\n" + clean
            }
            val capped = if (base.length > 45_000) {
                val cut = base.indexOf('\n', base.length - 45_000)
                if (cut in 0 until base.length) base.substring(cut + 1) else base.takeLast(45_000)
            } else {
                base
            }
            val latestSingle = clean.lineSequence().lastOrNull { it.isNotBlank() } ?: clean
            uiState = uiState.copy(
                logs = capped,
                lastLogLine = latestSingle,
            )
        }
    }

    private fun operationDisplayName(operation: String): String = when (operation) {
        "check" -> "正在检测环境与 ROOT 授权…"
        "generate" -> "正在读取当前系统并构建模块…"
        "rom-module" -> "正在生成模块…"
        "patch" -> "正在编译策略并原位修改 ROM…"
        "restore" -> "正在回退 ROM 上次修改…"
        "status" -> "正在查询 / 恢复上次事务状态…"
        "cache" -> "正在清理无用构建缓存…"
        "backups" -> "正在校验并删除已完成事务备份…"
        else -> "任务进行中 · 请保持前台…"
    }

    private fun startTask(operation: String) {
        if (uiState.busy) return
        val target = uiState.romPath.trim()
        val romOperation = operation == "patch" || operation == "restore" || operation == "status"
        val romInput = romOperation || operation == "rom-module" || operation == "backups"
        val moduleBuild = operation == "generate" || operation == "rom-module"

        if (romInput && target.isEmpty()) {
            uiState = uiState.copy(romPathError = "请输入 ROM 解包目录")
            return
        }
        if (romInput) {
            getPreferences(MODE_PRIVATE).edit().putString("romPath", target).apply()
        }

        val label = operationDisplayName(operation)
        setBusyState(true, label)
        uiState = uiState.copy(
            statusText = label,
            taskStateKind = TaskStateKind.RUNNING,
            logs = "",
            lastLogLine = "正在准备运行环境…",
        )

        val currentBridge = RootBridge(applicationContext) { msg -> appendLog(msg) }
        bridge = currentBridge

        worker.execute {
            try {
                val runtime = File(filesDir, "runtime")
                copyAssets("dolby_assets", File(runtime, "assets"))
                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(applicationContext))
                }

                val pyModule = Python.getInstance().getModule("mobile_bridge")
                val envText = pyModule.callAttr("check_environment", runtime.path).toString()
                appendLog(envText)

                if (currentBridge.exec("id -u\n", 45).trim() != "0") {
                    throw IOException("未获得 root 权限")
                }
                val model = currentBridge.model()
                appendLog("ROOT 授权通过；设备：$model")

                val detectedEnvStatus = if (envText.contains("缺少")) {
                    EnvStatus.NO_PAYLOAD
                } else {
                    EnvStatus.READY
                }
                mainHandler.post {
                    if (!isDestroyed) {
                        uiState = uiState.copy(
                            envStatus = detectedEnvStatus,
                            deviceModel = model,
                            envSummary = envText,
                        )
                    }
                }

                val historyPath = File(filesDir, "history").path
                if (moduleBuild) {
                    val result = pyModule.callAttr(
                        "generate",
                        runtime.path,
                        historyPath,
                        currentBridge,
                        if (operation == "rom-module") target else null,
                    ).toString()
                    val zipFile = File(JSONObject(result).getString("zip"))
                    lastZipFile = zipFile
                    getPreferences(MODE_PRIVATE).edit().putString("lastZip", zipFile.path).apply()
                    val artifact = zipFile.takeIf { it.isFile }?.toArtifactInfo()
                    mainHandler.post {
                        if (!isDestroyed) {
                            uiState = uiState.copy(lastZip = artifact)
                        }
                    }
                }

                if (romOperation) {
                    pyModule.callAttr(
                        "rom_operation",
                        runtime.path,
                        historyPath,
                        currentBridge,
                        target,
                        operation,
                    )
                }

                if (operation == "cache" || operation == "backups") {
                    pyModule.callAttr(
                        "cleanup",
                        runtime.path,
                        historyPath,
                        currentBridge,
                        target,
                        operation,
                    )
                }

                val doneText = when {
                    moduleBuild -> "模块已生成"
                    operation == "patch" -> "ROM 原位修改完成 · 未刷机"
                    operation == "restore" -> "ROM 回退完成"
                    operation == "status" -> "事务状态查询完成 · 请查看日志"
                    operation == "cache" || operation == "backups" -> "清理操作完成 · 请查看日志"
                    else -> "环境检测完成 · ROOT 可用"
                }

                mainHandler.post {
                    if (!isDestroyed) {
                        uiState = uiState.copy(
                            statusText = doneText,
                            taskStateKind = TaskStateKind.SUCCESS,
                        )
                    }
                }
            } catch (e: Exception) {
                val errMsg = e.message?.takeIf { it.isNotBlank() } ?: e.toString()
                appendLog(e.toString())
                mainHandler.post {
                    if (!isDestroyed) {
                        uiState = uiState.copy(
                            statusText = "任务未完成 · 请查看终端日志",
                            taskStateKind = TaskStateKind.ERROR,
                            envStatus = if (operation == "check" || uiState.envStatus == EnvStatus.UNCHECKED) {
                                EnvStatus.ERROR
                            } else {
                                uiState.envStatus
                            },
                            envSummary = if (operation == "check") errMsg else uiState.envSummary,
                        )
                    }
                }
            } finally {
                mainHandler.post {
                    if (!isDestroyed) {
                        setBusyState(false)
                    }
                }
            }
        }
    }

    private fun exportZipToUri(uri: Uri) {
        val zip = lastZipFile ?: return
        if (!zip.isFile || uiState.busy) return

        setBusyState(true, "正在导出保存模块 ZIP…")
        uiState = uiState.copy(
            statusText = "正在导出模块包…",
            taskStateKind = TaskStateKind.RUNNING,
        )

        worker.execute {
            try {
                FileInputStream(zip).use { input ->
                    val out = contentResolver.openOutputStream(uri, "wt")
                        ?: throw IOException("无法打开所选保存位置")
                    out.use { output ->
                        copyStream(input, output)
                    }
                }
                appendLog("模块已成功导出保存：${uri.lastPathSegment ?: "杜比全景+解码器_KSU.zip"}")
                mainHandler.post {
                    if (!isDestroyed) {
                        uiState = uiState.copy(
                            statusText = "ZIP 已保存 · 请前往 KSU 管理器刷入并重启",
                            taskStateKind = TaskStateKind.SUCCESS,
                        )
                        toast("模块 ZIP 已保存")
                    }
                }
            } catch (e: Exception) {
                appendLog("保存失败：$e")
                mainHandler.post {
                    if (!isDestroyed) {
                        uiState = uiState.copy(
                            statusText = "保存失败，请重新选择保存位置",
                            taskStateKind = TaskStateKind.ERROR,
                        )
                        toast("保存失败，请重新选择位置")
                    }
                }
            } finally {
                mainHandler.post {
                    if (!isDestroyed) {
                        setBusyState(false)
                    }
                }
            }
        }
    }

    @Throws(IOException::class)
    private fun copyAssets(source: String, target: File) {
        val children = assets.list(source)
        if (!children.isNullOrEmpty()) {
            if (!target.isDirectory && !target.mkdirs()) {
                throw IOException("无法创建资产目录")
            }
            for (child in children) {
                copyAssets("$source/$child", File(target, child))
            }
        } else {
            assets.open(source).use { input ->
                FileOutputStream(target).use { output ->
                    copyStream(input, output)
                }
            }
        }
    }

    override fun onDestroy() {
        bridge?.cancel()
        worker.shutdownNow()
        super.onDestroy()
    }

    companion object {
        @Throws(IOException::class)
        private fun copyStream(input: InputStream, output: OutputStream) {
            val buffer = ByteArray(65536)
            while (true) {
                val read = input.read(buffer)
                if (read == -1) break
                output.write(buffer, 0, read)
            }
        }

        private fun File.toArtifactInfo(): ZipArtifactInfo = ZipArtifactInfo(
            path = absolutePath,
            fileName = name,
            sizeBytes = length(),
            lastModifiedMillis = lastModified(),
        )
    }
}
