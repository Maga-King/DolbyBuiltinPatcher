package io.github.magaking.dolbybuilder.ui.components

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.magaking.dolbybuilder.ui.ConfirmAction
import io.github.magaking.dolbybuilder.ui.GlassCard
import io.github.magaking.dolbybuilder.ui.LocalDarkTheme
import io.github.magaking.dolbybuilder.ui.TaskStateKind
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import top.yukonga.miuix.kmp.basic.ButtonDefaults
import top.yukonga.miuix.kmp.basic.Icon
import top.yukonga.miuix.kmp.basic.IconButton
import top.yukonga.miuix.kmp.basic.LinearProgressIndicator
import top.yukonga.miuix.kmp.basic.Text
import top.yukonga.miuix.kmp.basic.TextButton
import top.yukonga.miuix.kmp.basic.TextField
import top.yukonga.miuix.kmp.theme.MiuixTheme
import top.yukonga.miuix.kmp.window.WindowDialog

@Composable
internal fun ToolbarButton(
    icon: ImageVector,
    description: String,
    onClick: () -> Unit,
    enabled: Boolean = true,
    tint: Color? = null,
) {
    val baseColor = tint ?: MiuixTheme.colorScheme.onSurface
    IconButton(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier.size(44.dp),
    ) {
        Icon(
            imageVector = icon,
            contentDescription = description,
            modifier = Modifier.size(22.dp),
            tint = baseColor.copy(alpha = if (enabled) 1f else 0.38f),
        )
    }
}

@Composable
internal fun StatusBadge(
    text: String,
    containerColor: Color,
    contentColor: Color,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier
            .background(containerColor, CircleShape)
            .padding(horizontal = 10.dp, vertical = 4.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = text,
            fontSize = 11.sp,
            fontWeight = FontWeight.SemiBold,
            color = contentColor,
            maxLines = 1,
        )
    }
}

@Composable
internal fun LiveTaskGlassCard(
    busy: Boolean,
    taskStateKind: TaskStateKind,
    operationLabel: String,
    statusText: String,
    lastLogLine: String,
    elapsedSeconds: Int,
    onOpenConsole: () -> Unit,
    onCancel: () -> Unit,
) {
    val colors = MiuixTheme.colorScheme
    val dark = LocalDarkTheme.current
    val tint = when {
        busy -> null
        taskStateKind == TaskStateKind.ERROR -> if (dark) Color(0xFF310808) else Color(0xFFF8E2E2)
        taskStateKind == TaskStateKind.SUCCESS -> if (dark) Color(0xFF1A3825) else Color(0xFFDFFAE4)
        else -> null
    }
    val accent = when {
        busy -> colors.primary
        taskStateKind == TaskStateKind.ERROR -> Color(0xFFF72727)
        else -> Color(0xFF28B857)
    }

    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        insideMargin = PaddingValues(14.dp),
        tint = tint,
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = when {
                    busy -> AppIcons.Bolt
                    taskStateKind == TaskStateKind.ERROR -> AppIcons.ShieldAlert
                    else -> AppIcons.CheckCircleRounded
                },
                contentDescription = null,
                tint = accent,
                modifier = Modifier.size(20.dp),
            )
            Spacer(Modifier.width(8.dp))
            Text(
                text = if (busy && operationLabel.isNotBlank()) operationLabel else statusText,
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
                color = colors.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier.weight(1f),
            )
            if (busy || elapsedSeconds > 0) {
                Spacer(Modifier.width(8.dp))
                Text(
                    text = formatElapsedSeconds(elapsedSeconds),
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                    color = colors.onSurfaceVariantSummary,
                )
            }
        }

        if (busy) {
            Spacer(Modifier.height(10.dp))
            LinearProgressIndicator(Modifier.fillMaxWidth())
        }

        if (lastLogLine.isNotBlank()) {
            Spacer(Modifier.height(8.dp))
            Text(
                text = lastLogLine,
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace,
                color = if (taskStateKind == TaskStateKind.ERROR) Color(0xFFF72727) else colors.onSurfaceVariantSummary,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }

        Spacer(Modifier.height(10.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            if (busy) {
                TextButton(
                    text = "请求安全取消",
                    onClick = onCancel,
                    minHeight = 32.dp,
                    cornerRadius = 10.dp,
                    insideMargin = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                )
            }
            TextButton(
                text = "查看完整终端",
                onClick = onOpenConsole,
                minHeight = 32.dp,
                cornerRadius = 10.dp,
                insideMargin = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                colors = ButtonDefaults.textButtonColorsPrimary(),
            )
        }
    }
}

@Composable
internal fun RomPathInputSection(
    romPath: String,
    romPathError: String?,
    enabled: Boolean,
    onRomPathChange: (String) -> Unit,
) {
    val context = LocalContext.current
    val colors = MiuixTheme.colorScheme
    val trimmed = romPath.trim()
    val looksLikeImage = trimmed.endsWith(".img", ignoreCase = true) ||
        trimmed.endsWith(".bin", ignoreCase = true) ||
        trimmed.endsWith(".zip", ignoreCase = true)

    Column(modifier = Modifier.fillMaxWidth()) {
        TextField(
            value = romPath,
            onValueChange = onRomPathChange,
            modifier = Modifier.fillMaxWidth(),
            label = "手机内 ROM 解包目录（如 /data/DNA/DNA_01）",
            useLabelAsPlaceholder = true,
            enabled = enabled,
            singleLine = true,
            textStyle = TextStyle(
                fontFamily = FontFamily.Monospace,
                fontSize = 14.sp,
                color = colors.onSurface,
            ),
            keyboardOptions = KeyboardOptions(
                capitalization = KeyboardCapitalization.None,
                autoCorrectEnabled = false,
                keyboardType = KeyboardType.Uri,
                imeAction = ImeAction.Done,
            ),
            leadingIcon = {
                Icon(
                    imageVector = AppIcons.Folder,
                    contentDescription = null,
                    modifier = Modifier.padding(start = 12.dp, end = 4.dp).size(20.dp),
                    tint = colors.primary,
                )
            },
            trailingIcon = if (romPath.isNotEmpty() && enabled) {
                {
                    ToolbarButton(
                        icon = AppIcons.Close,
                        description = "清空路径",
                        onClick = { onRomPathChange("") },
                    )
                }
            } else {
                null
            },
        )

        Spacer(Modifier.height(6.dp))
        val helperText = when {
            romPathError != null -> romPathError
            looksLikeImage -> "请输入已解包的五分区目录，不支持直接传入 .img / payload.bin / .zip 文件"
            else -> "需解包同一套 ROM 的五分区目录并保留 DNA config，不能填运行中系统目录"
        }
        val isWarn = romPathError != null || looksLikeImage
        Text(
            text = helperText,
            fontSize = 12.sp,
            lineHeight = 17.sp,
            color = if (isWarn) Color(0xFFF72727) else colors.onSurfaceVariantSummary,
            modifier = Modifier.padding(horizontal = 4.dp),
        )

        Spacer(Modifier.height(10.dp))
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(
                text = "粘贴路径",
                onClick = {
                    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager
                    val pasted = clipboard?.primaryClip?.getItemAt(0)?.coerceToText(context)?.toString()
                        ?.trim()?.trim('"', '\'')
                    if (!pasted.isNullOrEmpty()) onRomPathChange(pasted)
                },
                enabled = enabled,
                minHeight = 32.dp,
                cornerRadius = 10.dp,
                insideMargin = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
            )
            for (preset in listOf("/data/DNA/", "/data/local/tmp/")) {
                TextButton(
                    text = preset,
                    onClick = { onRomPathChange(preset) },
                    enabled = enabled,
                    minHeight = 32.dp,
                    cornerRadius = 10.dp,
                    insideMargin = PaddingValues(horizontal = 12.dp, vertical = 6.dp),
                    textStyle = TextStyle(
                        fontFamily = FontFamily.Monospace,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.Medium,
                    ),
                )
            }
        }
    }
}

@Composable
internal fun ConsoleTerminalBox(
    logs: String,
    busy: Boolean,
    minHeight: Dp = 210.dp,
    maxHeight: Dp = 350.dp,
    modifier: Modifier = Modifier,
) {
    val vScroll = rememberScrollState()
    LaunchedEffect(logs, busy) {
        if (busy || logs.length > 30) {
            vScroll.animateScrollTo(vScroll.maxValue)
        }
    }
    val styledLogs = remember(logs) { highlightLogs(logs) }

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(Color(0xFF0A1118))
            .border(1.dp, Color(0xFF1E3040), RoundedCornerShape(14.dp))
            .heightIn(min = minHeight, max = maxHeight)
            .verticalScroll(vScroll)
            .padding(14.dp),
    ) {
        SelectionContainer {
            Text(
                text = styledLogs,
                fontFamily = FontFamily.Monospace,
                fontSize = 12.sp,
                lineHeight = 18.sp,
            )
        }
    }
}

private fun highlightLogs(raw: String): AnnotatedString = buildAnnotatedString {
    val lines = raw.lines()
    lines.forEachIndexed { idx, line ->
        val color = when {
            line.contains("失败") || line.contains("错误") || line.contains("异常") ||
                line.contains("拒绝") || line.contains("Exception") || line.contains("Error") ->
                Color(0xFFFF9B91)
            line.contains("警告") || line.contains("注意") || line.contains("未解决") ||
                line.contains("超时") || line.contains("取消") ->
                Color(0xFFFFCF86)
            line.contains("完成") || line.contains("通过") || line.contains("齐全") ||
                line.contains("已生成") || line.contains("已保存") || line.contains("已清理") ->
                Color(0xFF6CE5CB)
            else -> Color(0xFFC9D8E3)
        }
        withStyle(SpanStyle(color = color)) {
            append(line)
        }
        if (idx < lines.lastIndex) append('\n')
    }
}

@Composable
internal fun ConfirmOperationWindowDialog(
    action: ConfirmAction?,
    romPath: String,
    busy: Boolean,
    onConfirm: (ConfirmAction) -> Unit,
    onDismiss: () -> Unit,
) {
    var closingAction by remember { mutableStateOf<ConfirmAction?>(null) }
    SideEffect {
        if (action != null) closingAction = action
    }
    val displayed = action ?: closingAction
    val target = romPath.trim()
    val isDanger = displayed == ConfirmAction.DELETE_BACKUPS

    val title = when (displayed) {
        ConfirmAction.GENERATE_LIVE_MODULE -> "生成模块"
        ConfirmAction.GENERATE_ROM_MODULE -> "生成模块"
        ConfirmAction.PATCH_ROM -> "确认备份并原位修改此 ROM"
        ConfirmAction.RESTORE_ROM -> "确认回退此 ROM 的上次修改"
        ConfirmAction.CLEAN_CACHE -> "清理无用构建缓存"
        ConfirmAction.DELETE_BACKUPS -> "永久删除备份（不可恢复）"
        null -> ""
    }

    val message = when (displayed) {
        ConfirmAction.GENERATE_LIVE_MODULE -> "来源 · 当前系统（需要 Root）"
        ConfirmAction.GENERATE_ROM_MODULE -> "来源 · $target"
        ConfirmAction.PATCH_ROM ->
            "目标解包目录：\n$target\n\n" +
                "将先只读快照、合并配置并调用 ARM64 secilc 编译目标 SELinux 策略，再通过一次性事务自动备份并写回此目录及 DNA config 标签。\n\n" +
                "• 不刷入运行分区、不自动重启，执行期间请保持前台\n" +
                "• 意外中断后请先「查询 / 恢复上次事务状态」，切勿重复修改\n" +
                "• 确认重新打包正常前请勿卸载本应用或删除同级 .dolby-patcher-backups"
        ConfirmAction.RESTORE_ROM ->
            "目标解包目录：\n$target\n\n" +
                "将按本应用最近一次修改记录与外部备份还原原厂文件及打包标签。\n\n" +
                "• 若目标文件已被其他工具再次修改，事务会自动中止保护，不强行覆盖\n" +
                "• 回退期间请保持应用在前台"
        ConfirmAction.CLEAN_CACHE ->
            "删除本工具产生的文件读取快照与已生成模块的中间临时目录。\n\n" +
                "• 保留已生成的模块 ZIP、ROM 原文件备份与事务回退记录\n" +
                "• 若存在未完成的写回事务将自动拒绝清理，确保数据安全"
        ConfirmAction.DELETE_BACKUPS ->
            "目标解包目录：\n$target\n\n" +
                "仅删除本应用对此目录创建的已结束事务备份（.dolby-patcher-backups 下对应任务）与构建记录，不会删除 ROM 本身或其他工具文件。\n\n" +
                "警告：删除后不可恢复，将永久失去这些记录的一键回退能力！请先确认 ROM 已完成打包且另有可靠备份。"
        null -> ""
    }

    val confirmLabel = when (displayed) {
        ConfirmAction.GENERATE_LIVE_MODULE -> "生成"
        ConfirmAction.GENERATE_ROM_MODULE -> "生成"
        ConfirmAction.PATCH_ROM -> "备份并开始内置"
        ConfirmAction.RESTORE_ROM -> "确认回退修改"
        ConfirmAction.CLEAN_CACHE -> "立即清理缓存"
        ConfirmAction.DELETE_BACKUPS -> "永久删除备份"
        null -> ""
    }

    WindowDialog(
        show = action != null,
        title = title,
        onDismissRequest = { if (!busy) onDismiss() },
        onDismissFinished = { closingAction = null },
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(max = 320.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            Text(
                text = message,
                fontSize = 14.sp,
                lineHeight = 20.sp,
                color = MiuixTheme.colorScheme.onSurfaceVariantSummary,
            )
        }
        Spacer(Modifier.height(18.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            TextButton(
                text = if (isDanger) "保留备份" else "取消",
                onClick = onDismiss,
                modifier = Modifier.weight(1f),
                enabled = !busy,
            )
            TextButton(
                text = confirmLabel,
                onClick = { action?.let(onConfirm) },
                modifier = Modifier.weight(1f),
                enabled = !busy,
                colors = if (isDanger) {
                    ButtonDefaults.textButtonColors(
                        color = Color(0xFFD93025),
                        textColor = Color.White,
                    )
                } else {
                    ButtonDefaults.textButtonColorsPrimary()
                },
            )
        }
    }
}

@Composable
internal fun BusyBackWindowDialog(
    show: Boolean,
    onKeepWaiting: () -> Unit,
    onRequestCancel: () -> Unit,
) {
    WindowDialog(
        show = show,
        title = "任务正在进行中",
        summary = "当前正在执行构建或一次性 ROM 事务。为防止写回中断，建议保持应用在前台等待完成；若尚处于快照或构建阶段，也可请求安全边界取消。",
        onDismissRequest = onKeepWaiting,
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            TextButton(
                text = "请求安全取消",
                onClick = onRequestCancel,
                modifier = Modifier.weight(1f),
            )
            TextButton(
                text = "继续等待",
                onClick = onKeepWaiting,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.textButtonColorsPrimary(),
            )
        }
    }
}

fun formatElapsedSeconds(seconds: Int): String {
    val safe = seconds.coerceAtLeast(0)
    val mins = safe / 60
    val secs = safe % 60
    return String.format(Locale.US, "%02d:%02d", mins, secs)
}

fun copyTextToClipboard(context: Context, label: String, text: String) {
    val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as? ClipboardManager ?: return
    clipboard.setPrimaryClip(ClipData.newPlainText(label, text))
}

fun formatFileSize(bytes: Long): String {
    if (bytes < 1024L) return "$bytes B"
    val kb = bytes / 1024.0
    if (kb < 1024.0) return String.format(Locale.US, "%.1f KB", kb)
    val mb = kb / 1024.0
    return String.format(Locale.US, "%.2f MB", mb)
}

fun formatTimestamp(millis: Long): String {
    if (millis <= 0L) return "未知时间"
    return SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()).format(Date(millis))
}
