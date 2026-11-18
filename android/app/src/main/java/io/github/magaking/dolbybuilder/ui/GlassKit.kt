package io.github.magaking.dolbybuilder.ui

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.CornerBasedShape
import androidx.compose.foundation.shape.CornerSize
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Outline
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import top.yukonga.miuix.kmp.basic.Card
import top.yukonga.miuix.kmp.basic.CardDefaults
import top.yukonga.miuix.kmp.basic.TabRow
import top.yukonga.miuix.kmp.basic.TabRowDefaults
import top.yukonga.miuix.kmp.basic.Text
import com.kyant.backdrop.effects.blur
import com.kyant.backdrop.drawBackdrop
import com.kyant.backdrop.effects.lens
import com.kyant.backdrop.highlight.Highlight
import top.yukonga.miuix.kmp.squircle.addSquircleRect
import top.yukonga.miuix.kmp.theme.MiuixTheme

internal object GlassRecipe {
    val CornerRadius = 14.dp
}

internal fun glassHighlight(params: GlassParams) = Highlight(
    width = params.edgeWidth.dp,
    blurRadius = (params.edgeWidth * params.edgeTaper).dp,
    alpha = params.edgeIntensity.coerceIn(0f, 1f),
)

/** Keep the glass mask on the same squircle path as a native Miuix card. */
private class GlassSquircle(
    topStart: CornerSize,
    topEnd: CornerSize = topStart,
    bottomEnd: CornerSize = topStart,
    bottomStart: CornerSize = topStart,
) : CornerBasedShape(topStart, topEnd, bottomEnd, bottomStart) {
    override fun createOutline(
        size: Size,
        topStart: Float,
        topEnd: Float,
        bottomEnd: Float,
        bottomStart: Float,
        layoutDirection: LayoutDirection,
    ): Outline = Outline.Generic(Path().apply {
        addSquircleRect(size.width, size.height, minOf(topStart, topEnd, bottomEnd, bottomStart))
    })

    override fun copy(topStart: CornerSize, topEnd: CornerSize, bottomEnd: CornerSize, bottomStart: CornerSize) =
        GlassSquircle(topStart, topEnd, bottomEnd, bottomStart)
}

/**
 * Liquid glass card following Nyako Manager's OriginOS recipe: subtle blur, AGSL edge refraction
 * with full-strength rim highlight, and a theme-tinted scrim that keeps text crisp over the
 * sampled backdrop. Falls back to Miuix [Card] when Liquid Glass is disabled or unsupported.
 */
@Composable
internal fun GlassCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    enabled: Boolean = true,
    cornerRadius: Dp = 16.dp,
    insideMargin: PaddingValues = CardDefaults.InsideMargin,
    tint: Color? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val colors = MiuixTheme.colorScheme
    val glass = LocalGlass.current
    val backdrop = LocalGlassBackdrop.current
    val surfaceColor = tint ?: colors.surfaceContainer
    if (glass && backdrop != null) {
        val interaction = remember { MutableInteractionSource() }
        val pressed by interaction.collectIsPressedAsState()
        val scale by animateFloatAsState(
            targetValue = if (pressed && enabled) 0.97f else 1f,
            animationSpec = spring(0.6f, 300f),
            label = "glass-card-scale"
        )
        val params = LocalGlassParams.current
        val scrimAlpha = if (tint != null) 0.66f else 0.55f
        Box(
            modifier = modifier
                .graphicsLayer {
                    scaleX = scale
                    scaleY = scale
                }
                .then(
                    if (onClick != null && enabled) {
                        Modifier.clickable(
                            interactionSource = interaction,
                            indication = null,
                            onClick = onClick,
                        )
                    } else {
                        Modifier
                    }
                )
                .drawBackdrop(
                    backdrop = backdrop,
                    shape = { GlassSquircle(CornerSize(cornerRadius)) },
                    effects = {
                        blur(params.blur.dp.toPx())
                        lens(params.range.dp.toPx(), params.intensity.dp.toPx())
                    },
                    highlight = { glassHighlight(params) },
                    shadow = null,
                    onDrawSurface = { drawRect(surfaceColor.copy(alpha = scrimAlpha)) },
                ),
            propagateMinConstraints = true,
        ) {
            Column(Modifier.padding(insideMargin).fillMaxWidth(), content = content)
        }
    } else {
        val fallbackAlpha = if (LocalHasBackdropContent.current) LocalCardOpacity.current else 1f
        val cardColors = CardDefaults.defaultColors(color = surfaceColor.copy(alpha = fallbackAlpha))
        if (onClick != null && enabled) {
            Card(
                onClick = onClick,
                modifier = modifier.fillMaxWidth(),
                cornerRadius = cornerRadius,
                insideMargin = insideMargin,
                colors = cardColors,
                content = content,
            )
        } else {
            Card(
                modifier = modifier.fillMaxWidth(),
                cornerRadius = cornerRadius,
                insideMargin = insideMargin,
                colors = cardColors,
                content = content,
            )
        }
    }
}

@Composable
internal fun PreferenceCard(
    modifier: Modifier = Modifier,
    tint: Color? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    GlassCard(modifier = modifier.fillMaxWidth(), tint = tint, content = content)
}

/**
 * Glass filter capsules with a spring-animated sliding selection pill; falls back to Miuix [TabRow].
 */
@Composable
internal fun GlassFilterTabs(
    titles: List<String>,
    selectedIndex: Int,
    enabled: Boolean = true,
    onTabSelected: (Int) -> Unit,
) {
    val colors = MiuixTheme.colorScheme
    val backdrop = LocalGlassBackdrop.current
    if (!LocalGlass.current || backdrop == null) {
        TabRow(
            tabs = titles,
            selectedTabIndex = selectedIndex,
            onTabSelected = { if (enabled) onTabSelected(it) },
            colors = TabRowDefaults.tabRowColors(
                backgroundColor = if (LocalHasBackdropContent.current) {
                    colors.surfaceContainer.copy(alpha = 0.45f)
                } else {
                    colors.surface
                },
                selectedBackgroundColor = colors.surfaceContainer.copy(alpha = LocalCardOpacity.current),
            ),
        )
        return
    }
    val corner = GlassRecipe.CornerRadius
    val params = LocalGlassParams.current
    val position = remember { Animatable(selectedIndex.toFloat()) }
    val selection by rememberUpdatedState(onTabSelected)
    LaunchedEffect(selectedIndex) {
        position.animateTo(selectedIndex.toFloat(), spring(1f, 800f, 0.001f))
    }
    Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
        BoxWithConstraints(Modifier.fillMaxWidth().height(54.dp)) {
            val slot = (maxWidth - 8.dp) / titles.size.coerceAtLeast(1)
            Box(
                Modifier.fillMaxSize().drawBackdrop(
                    backdrop = backdrop,
                    shape = { GlassSquircle(CornerSize(corner)) },
                    effects = {
                        blur(params.blur.dp.toPx())
                        lens(params.range.dp.toPx(), params.intensity.dp.toPx())
                    },
                    highlight = { glassHighlight(params) },
                    shadow = null,
                    onDrawSurface = { drawRect(colors.surfaceContainer.copy(alpha = 0.40f)) },
                )
            )
            Box(
                Modifier
                    .padding(4.dp)
                    .offset(x = slot * position.value.coerceIn(0f, (titles.size - 1).coerceAtLeast(0).toFloat()))
                    .width(slot)
                    .height(46.dp)
                    .background(
                        colors.surfaceContainer.copy(alpha = 0.88f),
                        GlassSquircle(CornerSize(corner - 2.dp)),
                    )
            )
            Row(Modifier.fillMaxSize().padding(4.dp), verticalAlignment = Alignment.CenterVertically) {
                titles.forEachIndexed { index, title ->
                    val tint by animateColorAsState(
                        targetValue = if (selectedIndex == index) colors.onSurface else colors.onSurfaceVariantSummary,
                        label = "glass-tab-$index"
                    )
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .height(46.dp)
                            .clickable(
                                enabled = enabled,
                                interactionSource = remember { MutableInteractionSource() },
                                indication = null,
                                onClick = { selection(index) },
                            ),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            text = title,
                            fontSize = 13.sp,
                            fontWeight = if (selectedIndex == index) FontWeight.SemiBold else FontWeight.Medium,
                            color = tint.copy(alpha = if (enabled) 1f else 0.5f),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            textAlign = TextAlign.Center,
                        )
                    }
                }
            }
        }
    }
}
