// Material Design icons, Copyright Google LLC. Licensed under Apache-2.0.
package io.github.magaking.dolbybuilder.ui.components

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathFillType
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.graphics.vector.path
import androidx.compose.ui.unit.dp

object AppIcons {
    private fun icon(name: String, block: ImageVector.Builder.() -> Unit): ImageVector =
        ImageVector.Builder(
            name = name,
            defaultWidth = 24.dp,
            defaultHeight = 24.dp,
            viewportWidth = 24f,
            viewportHeight = 24f
        ).apply(block).build()

    private fun svgIcon(name: String, pathData: String): ImageVector =
        ImageVector.Builder(name, 24.dp, 24.dp, 24f, 24f).apply {
            addPath(PathParser().parsePathString(pathData).toNodes(), fill = SolidColor(Color.Black))
        }.build()

    private fun ImageVector.Builder.filledPath(block: androidx.compose.ui.graphics.vector.PathBuilder.() -> Unit) {
        path(
            fill = SolidColor(Color.Black),
            pathFillType = PathFillType.NonZero,
            pathBuilder = block
        )
    }

    private fun ImageVector.Builder.strokedPath(
        strokeWidth: Float = 1.95f,
        block: androidx.compose.ui.graphics.vector.PathBuilder.() -> Unit
    ) {
        path(
            stroke = SolidColor(Color.Black),
            strokeLineWidth = strokeWidth,
            strokeLineCap = StrokeCap.Round,
            strokeLineJoin = StrokeJoin.Round,
            pathBuilder = block
        )
    }

    /** Rounded Material CheckCircle matching SukiSU/Nyako hero status emblem. */
    val CheckCircleRounded: ImageVector by lazy {
        svgIcon(
            "CheckCircleRounded",
            "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm3.88-11.71L10 14.17l-1.88-1.88c-.39-.39-1.02-.39-1.41 0-.39.39-.39 1.02 0 1.41l2.59 2.59c.39.39 1.02.39 1.41 0L17.3 9.7c.39-.39.39-1.02 0-1.41-.39-.39-1.03-.39-1.42 0z"
        )
    }

    val ArrowBack: ImageVector by lazy {
        icon("ArrowBack") {
            strokedPath(2.1f) {
                moveTo(19f, 12f)
                horizontalLineTo(5.5f)
                moveTo(11.5f, 6f)
                lineTo(5.5f, 12f)
                lineTo(11.5f, 18f)
            }
        }
    }

    val Check: ImageVector by lazy {
        icon("Check") {
            strokedPath(2.3f) {
                moveTo(5.5f, 12.5f)
                lineTo(10f, 17f)
                lineTo(18.8f, 7.5f)
            }
        }
    }

    val Refresh: ImageVector by lazy {
        icon("Refresh") {
            strokedPath(1.95f) {
                moveTo(19.5f, 5.5f)
                verticalLineTo(10f)
                horizontalLineTo(15f)
                moveTo(19f, 9.6f)
                curveTo(17.5f, 6.4f, 14.2f, 4.3f, 10.6f, 4.6f)
                curveTo(6.3f, 5f, 3.2f, 8.7f, 3.6f, 13f)
                curveTo(4f, 17.3f, 7.7f, 20.4f, 12f, 20f)
                curveTo(15.4f, 19.7f, 18.2f, 17.5f, 19.3f, 14.4f)
            }
        }
    }

    val Equalizer: ImageVector by lazy {
        icon("Equalizer") {
            strokedPath(2.2f) {
                moveTo(4f, 10f); lineTo(4f, 14f)
                moveTo(8f, 7f); lineTo(8f, 17f)
                moveTo(12f, 4f); lineTo(12f, 20f)
                moveTo(16f, 7f); lineTo(16f, 17f)
                moveTo(20f, 10f); lineTo(20f, 14f)
            }
        }
    }

    val ModuleBox: ImageVector by lazy {
        icon("ModuleBox") {
            strokedPath(1.9f) {
                moveTo(12f, 2.5f)
                lineTo(20.5f, 7f)
                lineTo(20.5f, 17f)
                lineTo(12f, 21.5f)
                lineTo(3.5f, 17f)
                lineTo(3.5f, 7f)
                close()
                moveTo(3.8f, 7.2f)
                lineTo(12f, 11.8f)
                lineTo(20.2f, 7.2f)
                moveTo(12f, 11.8f)
                lineTo(12f, 21.3f)
                moveTo(7.8f, 4.8f)
                lineTo(16.2f, 9.4f)
            }
        }
    }

    val RomLayers: ImageVector by lazy {
        icon("RomLayers") {
            strokedPath(1.9f) {
                moveTo(12f, 3f)
                lineTo(21f, 7.8f)
                lineTo(12f, 12.6f)
                lineTo(3f, 7.8f)
                close()
                moveTo(3f, 12.4f)
                lineTo(12f, 17.2f)
                lineTo(21f, 12.4f)
                moveTo(3f, 16.8f)
                lineTo(12f, 21.5f)
                lineTo(21f, 16.8f)
            }
        }
    }

    val Terminal: ImageVector by lazy {
        icon("Terminal") {
            strokedPath(1.9f) {
                moveTo(4f, 5f)
                horizontalLineTo(20f)
                arcTo(1.5f, 1.5f, 0f, false, true, 21.5f, 6.5f)
                verticalLineTo(17.5f)
                arcTo(1.5f, 1.5f, 0f, false, true, 20f, 19f)
                horizontalLineTo(4f)
                arcTo(1.5f, 1.5f, 0f, false, true, 2.5f, 17.5f)
                verticalLineTo(6.5f)
                arcTo(1.5f, 1.5f, 0f, false, true, 4f, 5f)
                close()
                moveTo(6.8f, 9.5f)
                lineTo(10f, 12.2f)
                lineTo(6.8f, 14.9f)
                moveTo(12f, 15f)
                horizontalLineTo(16.8f)
            }
        }
    }

    val ShieldCheck: ImageVector by lazy {
        icon("ShieldCheck") {
            strokedPath(1.9f) {
                moveTo(12f, 2.8f)
                lineTo(19.5f, 5.8f)
                verticalLineTo(11.5f)
                curveTo(19.5f, 16.3f, 16.3f, 19.8f, 12f, 21.4f)
                curveTo(7.7f, 19.8f, 4.5f, 16.3f, 4.5f, 11.5f)
                verticalLineTo(5.8f)
                close()
                moveTo(8.8f, 12.2f)
                lineTo(11.1f, 14.5f)
                lineTo(15.5f, 9.8f)
            }
        }
    }

    val ShieldAlert: ImageVector by lazy {
        icon("ShieldAlert") {
            strokedPath(1.9f) {
                moveTo(12f, 2.8f)
                lineTo(19.5f, 5.8f)
                verticalLineTo(11.5f)
                curveTo(19.5f, 16.3f, 16.3f, 19.8f, 12f, 21.4f)
                curveTo(7.7f, 19.8f, 4.5f, 16.3f, 4.5f, 11.5f)
                verticalLineTo(5.8f)
                close()
                moveTo(12f, 8.2f)
                verticalLineTo(12.8f)
            }
            filledPath {
                moveTo(12f, 16.2f)
                arcTo(1.1f, 1.1f, 0f, true, true, 12f, 16.21f)
                close()
            }
        }
    }

    val Folder: ImageVector by lazy {
        icon("Folder") {
            strokedPath(1.9f) {
                moveTo(3.5f, 6.5f)
                arcTo(1.5f, 1.5f, 0f, false, true, 5f, 5f)
                horizontalLineTo(9.4f)
                lineTo(11.4f, 7.2f)
                horizontalLineTo(19f)
                arcTo(1.5f, 1.5f, 0f, false, true, 20.5f, 8.7f)
                verticalLineTo(17.5f)
                arcTo(1.5f, 1.5f, 0f, false, true, 19f, 19f)
                horizontalLineTo(5f)
                arcTo(1.5f, 1.5f, 0f, false, true, 3.5f, 17.5f)
                close()
            }
        }
    }

    val DownloadSave: ImageVector by lazy {
        icon("DownloadSave") {
            strokedPath(2f) {
                moveTo(12f, 4f)
                verticalLineTo(14.5f)
                moveTo(8f, 10.8f)
                lineTo(12f, 14.8f)
                lineTo(16f, 10.8f)
                moveTo(4.5f, 17.2f)
                verticalLineTo(18.5f)
                arcTo(1.5f, 1.5f, 0f, false, false, 6f, 20f)
                horizontalLineTo(18f)
                arcTo(1.5f, 1.5f, 0f, false, false, 19.5f, 18.5f)
                verticalLineTo(17.2f)
            }
        }
    }

    val Restore: ImageVector by lazy {
        icon("Restore") {
            strokedPath(1.9f) {
                moveTo(4.5f, 8.5f)
                verticalLineTo(4.5f)
                horizontalLineTo(8.5f)
                moveTo(5f, 8.2f)
                curveTo(6.5f, 5.4f, 9.5f, 4f, 12.8f, 4.3f)
                curveTo(17.2f, 4.7f, 20.5f, 8.4f, 20.2f, 12.8f)
                curveTo(19.9f, 17.1f, 16.2f, 20.3f, 11.8f, 20f)
                curveTo(8.5f, 19.8f, 5.7f, 17.7f, 4.6f, 14.7f)
            }
        }
    }

    val HistoryStatus: ImageVector by lazy {
        icon("HistoryStatus") {
            strokedPath(1.9f) {
                moveTo(12f, 4f)
                curveTo(16.4f, 4f, 20f, 7.6f, 20f, 12f)
                curveTo(20f, 16.4f, 16.4f, 20f, 12f, 20f)
                curveTo(7.6f, 20f, 4f, 16.4f, 4f, 12f)
                curveTo(4f, 7.6f, 7.6f, 4f, 12f, 4f)
                close()
                moveTo(12f, 7.8f)
                verticalLineTo(12.2f)
                lineTo(15f, 14f)
            }
        }
    }

    val CleanSpark: ImageVector by lazy {
        icon("CleanSpark") {
            strokedPath(1.9f) {
                moveTo(12f, 3.5f)
                lineTo(13.8f, 8.2f)
                lineTo(18.5f, 10f)
                lineTo(13.8f, 11.8f)
                lineTo(12f, 16.5f)
                lineTo(10.2f, 11.8f)
                lineTo(5.5f, 10f)
                lineTo(10.2f, 8.2f)
                close()
                moveTo(18.2f, 15.5f)
                lineTo(18.9f, 17.6f)
                lineTo(21f, 18.3f)
                lineTo(18.9f, 19f)
                lineTo(18.2f, 21f)
                lineTo(17.5f, 19f)
                lineTo(15.5f, 18.3f)
                lineTo(17.5f, 17.6f)
                close()
            }
        }
    }

    val DeleteForever: ImageVector by lazy {
        icon("DeleteForever") {
            strokedPath(1.9f) {
                moveTo(4.5f, 6.5f)
                horizontalLineTo(19.5f)
                moveTo(9.5f, 6.5f)
                verticalLineTo(4.6f)
                arcTo(1f, 1f, 0f, false, true, 10.5f, 3.6f)
                horizontalLineTo(13.5f)
                arcTo(1f, 1f, 0f, false, true, 14.5f, 4.6f)
                verticalLineTo(6.5f)
                moveTo(6.5f, 6.5f)
                lineTo(7.3f, 19f)
                arcTo(1.5f, 1.5f, 0f, false, false, 8.8f, 20.4f)
                horizontalLineTo(15.2f)
                arcTo(1.5f, 1.5f, 0f, false, false, 16.7f, 19f)
                lineTo(17.5f, 6.5f)
                moveTo(10f, 11f)
                lineTo(14f, 15f)
                moveTo(14f, 11f)
                lineTo(10f, 15f)
            }
        }
    }

    val Copy: ImageVector by lazy {
        icon("Copy") {
            strokedPath(1.9f) {
                moveTo(9f, 8.5f)
                horizontalLineTo(18f)
                arcTo(1.5f, 1.5f, 0f, false, true, 19.5f, 10f)
                verticalLineTo(19f)
                arcTo(1.5f, 1.5f, 0f, false, true, 18f, 20.5f)
                horizontalLineTo(9f)
                arcTo(1.5f, 1.5f, 0f, false, true, 7.5f, 19f)
                verticalLineTo(10f)
                arcTo(1.5f, 1.5f, 0f, false, true, 9f, 8.5f)
                close()
                moveTo(16f, 8.5f)
                verticalLineTo(5.5f)
                arcTo(1.5f, 1.5f, 0f, false, false, 14.5f, 4f)
                horizontalLineTo(6f)
                arcTo(1.5f, 1.5f, 0f, false, false, 4.5f, 5.5f)
                verticalLineTo(14.5f)
                arcTo(1.5f, 1.5f, 0f, false, false, 6f, 16f)
                horizontalLineTo(7.5f)
            }
        }
    }

    val Paste: ImageVector by lazy {
        icon("Paste") {
            strokedPath(1.9f) {
                moveTo(9f, 4.5f)
                horizontalLineTo(15f)
                verticalLineTo(7f)
                horizontalLineTo(9f)
                close()
                moveTo(9f, 5.5f)
                horizontalLineTo(6.5f)
                arcTo(1.5f, 1.5f, 0f, false, false, 5f, 7f)
                verticalLineTo(19f)
                arcTo(1.5f, 1.5f, 0f, false, false, 6.5f, 20.5f)
                horizontalLineTo(17.5f)
                arcTo(1.5f, 1.5f, 0f, false, false, 19f, 19f)
                verticalLineTo(7f)
                arcTo(1.5f, 1.5f, 0f, false, false, 17.5f, 5.5f)
                horizontalLineTo(15f)
            }
        }
    }

    val Palette: ImageVector by lazy {
        icon("Palette") {
            strokedPath(1.9f) {
                moveTo(12f, 3.5f)
                curveTo(7.2f, 3.5f, 3.5f, 7.1f, 3.5f, 11.6f)
                curveTo(3.5f, 16.1f, 7.2f, 19.8f, 11.8f, 19.8f)
                horizontalLineTo(13.2f)
                arcTo(2.1f, 2.1f, 0f, false, false, 15.3f, 17.7f)
                curveTo(15.3f, 16.9f, 14.9f, 16.3f, 14.9f, 15.6f)
                curveTo(14.9f, 14.5f, 15.8f, 13.8f, 16.9f, 13.8f)
                horizontalLineTo(18f)
                curveTo(19.9f, 13.8f, 20.8f, 12.3f, 20.5f, 10.4f)
                curveTo(19.9f, 6.4f, 16.3f, 3.5f, 12f, 3.5f)
                close()
            }
            filledPath {
                moveTo(8f, 10.5f); arcTo(1.2f, 1.2f, 0f, true, true, 8f, 10.51f); close()
                moveTo(11f, 7.8f); arcTo(1.2f, 1.2f, 0f, true, true, 11f, 7.81f); close()
                moveTo(15f, 8.5f); arcTo(1.2f, 1.2f, 0f, true, true, 15f, 8.51f); close()
            }
        }
    }

    val Info: ImageVector by lazy {
        icon("Info") {
            strokedPath(1.9f) {
                moveTo(12f, 3.5f)
                curveTo(16.7f, 3.5f, 20.5f, 7.3f, 20.5f, 12f)
                curveTo(20.5f, 16.7f, 16.7f, 20.5f, 12f, 20.5f)
                curveTo(7.3f, 20.5f, 3.5f, 16.7f, 3.5f, 12f)
                curveTo(3.5f, 7.3f, 7.3f, 3.5f, 12f, 3.5f)
                close()
                moveTo(12f, 11.2f)
                verticalLineTo(16.2f)
            }
            filledPath {
                moveTo(12f, 8f)
                arcTo(1.1f, 1.1f, 0f, true, true, 12f, 8.01f)
                close()
            }
        }
    }

    val Bolt: ImageVector by lazy {
        icon("Bolt") {
            strokedPath(1.9f) {
                moveTo(13.2f, 3.2f)
                lineTo(5.5f, 13.2f)
                horizontalLineTo(11.6f)
                lineTo(10.8f, 20.8f)
                lineTo(18.5f, 10.8f)
                horizontalLineTo(12.4f)
                close()
            }
        }
    }

    val Close: ImageVector by lazy {
        icon("Close") {
            strokedPath(2f) {
                moveTo(6.5f, 6.5f)
                lineTo(17.5f, 17.5f)
                moveTo(17.5f, 6.5f)
                lineTo(6.5f, 17.5f)
            }
        }
    }
}
