package io.github.magaking.dolbybuilder.ui

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import io.github.magaking.dolbybuilder.ui.components.AppIcons
import kotlin.math.abs
import kotlin.math.roundToInt
import top.yukonga.miuix.kmp.basic.Icon
import top.yukonga.miuix.kmp.basic.Text
import com.kyant.backdrop.Backdrop
import com.kyant.backdrop.effects.blur
import com.kyant.backdrop.drawBackdrop
import com.kyant.backdrop.effects.lens
import top.yukonga.miuix.kmp.theme.MiuixTheme

/**
 * Liquid Glass bottom navigation capsule matching Nyako Manager (64/56 dp geometry,
 * spring-driven horizontal drag and press stretch).
 * Only the non-ancestor background backdrop is sampled, preventing RenderThread cycles.
 */
@Composable
internal fun GlassNavigationBar(
    selected: Int,
    backdrop: Backdrop,
    busy: Boolean,
    hasError: Boolean,
    hasExportableZip: Boolean,
    onSelected: (Int) -> Unit,
) {
    val colors = MiuixTheme.colorScheme
    val currentSelection by rememberUpdatedState(selected)
    val select by rememberUpdatedState(onSelected)
    val position = remember { Animatable(selected.toFloat()) }
    var dragging by remember { mutableStateOf(false) }
    var dragPosition by remember { mutableFloatStateOf(selected.toFloat()) }
    var releasePosition by remember { mutableStateOf<Float?>(null) }
    val interactions = remember { List(3) { MutableInteractionSource() } }
    val pressed = interactions.map { it.collectIsPressedAsState().value }.any { it }

    LaunchedEffect(selected, dragging) {
        if (dragging) {
            position.stop()
        } else {
            releasePosition?.let { position.snapTo(it) }
            releasePosition = null
            position.animateTo(selected.toFloat(), spring(1f, 1000f, 0.001f))
        }
    }

    val moving = position.isRunning
    val scaleX by animateFloatAsState(
        targetValue = if (pressed || dragging || moving) 1.10f else 1f,
        animationSpec = spring(0.6f, 250f),
        label = "glass-nav-width"
    )
    val scaleY by animateFloatAsState(
        targetValue = if (pressed || dragging || moving) 1.16f else 1f,
        animationSpec = spring(0.7f, 250f),
        label = "glass-nav-height"
    )
    val rtl = LocalLayoutDirection.current == LayoutDirection.Rtl
    val density = LocalDensity.current
    val labels = listOf(AppTab.MODULE.label, AppTab.ROM.label, AppTab.MAINTENANCE.label)
    val icons = listOf(AppIcons.ModuleBox, AppIcons.RomLayers, AppIcons.Terminal)
    val height = 64.dp + 16.dp * (density.fontScale - 1f).coerceAtLeast(0f)

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Horizontal))
            .navigationBarsPadding()
            .padding(horizontal = 24.dp, vertical = 10.dp),
        contentAlignment = Alignment.Center,
    ) {
        BoxWithConstraints(
            modifier = Modifier
                .widthIn(max = 440.dp)
                .fillMaxWidth()
                .height(height)
        ) {
            val slot = (maxWidth - 8.dp) / 3
            val slotPx = with(density) { slot.toPx() }
            val params = LocalGlassParams.current

            Box(
                Modifier
                    .fillMaxSize()
                    .drawBackdrop(
                        backdrop = backdrop,
                        shape = { CircleShape },
                        effects = {
                            blur(params.blur.dp.toPx())
                            lens(params.range.dp.toPx(), params.intensity.dp.toPx())
                        },
                        highlight = { glassHighlight(params) },
                        shadow = null,
                        onDrawSurface = { drawRect(colors.surfaceContainer.copy(alpha = 0.42f)) },
                    )
            )

            val fraction = if (dragging) dragPosition else position.value
            Box(
                Modifier
                    .padding(4.dp)
                    .offset(x = slot * fraction.coerceIn(0f, 2f))
                    .width(slot)
                    .height(height - 8.dp)
                    .graphicsLayer {
                        this.scaleX = scaleX + (abs(position.velocity) * 0.003f).coerceAtMost(0.06f)
                        this.scaleY = scaleY
                    }
                    .drawBackdrop(
                        backdrop = backdrop,
                        shape = { CircleShape },
                        effects = {
                            blur(params.blur.dp.toPx())
                            lens(params.range.dp.toPx(), params.intensity.dp.toPx())
                        },
                        highlight = { glassHighlight(params) },
                        shadow = null,
                        onDrawSurface = {
                            drawRect(colors.surfaceContainer.copy(alpha = 0.64f))
                            drawRect(colors.onSurface.copy(alpha = 0.08f))
                        },
                    )
            )

            Row(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(4.dp)
                    .selectableGroup()
                    .pointerInput(slotPx, rtl) {
                        detectHorizontalDragGestures(
                            onDragStart = {
                                dragPosition = position.value
                                dragging = true
                            },
                            onDragCancel = {
                                releasePosition = dragPosition
                                dragging = false
                            },
                            onDragEnd = {
                                val index = dragPosition.roundToInt().coerceIn(0, 2)
                                releasePosition = dragPosition
                                select(index)
                                dragging = false
                            },
                            onHorizontalDrag = { change, delta ->
                                change.consume()
                                val dir = if (rtl) -1f else 1f
                                dragPosition = (dragPosition + delta / slotPx * dir).coerceIn(0f, 2f)
                            },
                        )
                    },
                verticalAlignment = Alignment.CenterVertically,
            ) {
                labels.forEachIndexed { index, label ->
                    val tint by animateColorAsState(
                        targetValue = if (selected == index) colors.onSurface else colors.onSurfaceVariantSummary,
                        label = "glass-nav-tint-$index"
                    )
                    val dotColor = when {
                        index == 2 && hasError -> Color(0xFFF72727)
                        index == 2 && busy -> colors.primary
                        index == 0 && hasExportableZip && selected != 0 -> Color(0xFF36D167)
                        else -> null
                    }
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxHeight()
                            .selectable(
                                selected = selected == index,
                                interactionSource = interactions[index],
                                indication = null,
                                role = Role.Tab,
                                onClick = { if (currentSelection != index) select(index) },
                            ),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.Center,
                    ) {
                        Box {
                            Icon(icons[index], null, Modifier.size(24.dp), tint = tint)
                            if (dotColor != null) {
                                Box(
                                    Modifier
                                        .align(Alignment.TopEnd)
                                        .offset(x = 3.dp, y = (-2).dp)
                                        .size(6.dp)
                                        .background(dotColor, CircleShape)
                                )
                            }
                        }
                        Text(
                            text = label,
                            modifier = Modifier.padding(top = 2.dp),
                            fontSize = 11.sp,
                            fontWeight = if (selected == index) FontWeight.SemiBold else FontWeight.Medium,
                            color = tint,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
        }
    }
}
