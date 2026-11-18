package io.github.magaking.dolbybuilder.ui.theme

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ColorSpace
import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import androidx.compose.ui.graphics.Color
import java.io.File
import java.io.FileOutputStream

internal const val THEME_PREFS = "dolby_miuix_theme"
private const val WALLPAPER_FILE = "custom_wallpaper.jpg"

enum class ColorMode(val value: Int) {
    SYSTEM(0),
    LIGHT(1),
    DARK(2),
    MONET_SYSTEM(3),
    MONET_LIGHT(4),
    MONET_DARK(5),
}

val PresetAccentPalette = listOf(
    0,                      // Miuix Default
    0xFF1BB3C7.toInt(),     // Acoustic Cyan
    0xFF3482FF.toInt(),     // Cobalt Blue
    0xFF7454C9.toInt(),     // Studio Violet
    0xFF269174.toInt(),     // Emerald Green
    0xFFB47028.toInt(),     // Warm Gold
    0xFFBC4C66.toInt(),     // Rose Red
)

fun decodeAndStoreWallpaper(context: Context, uri: Uri): Bitmap? {
    val decoded = decodeBoundedUri(context, uri, maxDim = 1440) ?: return null
    val dest = File(context.filesDir, WALLPAPER_FILE)
    val tmp = File(context.filesDir, "$WALLPAPER_FILE.tmp")
    return try {
        FileOutputStream(tmp).use { out ->
            if (!decoded.compress(Bitmap.CompressFormat.JPEG, 88, out)) {
                tmp.delete()
                return null
            }
        }
        if (dest.exists()) dest.delete()
        if (!tmp.renameTo(dest)) {
            tmp.copyTo(dest, overwrite = true)
            tmp.delete()
        }
        decoded
    } catch (_: Exception) {
        tmp.delete()
        decoded.recycle()
        null
    }
}

fun loadStoredWallpaper(context: Context): Bitmap? {
    val file = File(context.filesDir, WALLPAPER_FILE)
    if (!file.isFile) return null
    return try {
        BitmapFactory.decodeFile(file.absolutePath)
    } catch (_: Exception) {
        null
    }
}

fun clearStoredWallpaper(context: Context) {
    val file = File(context.filesDir, WALLPAPER_FILE)
    if (file.exists()) file.delete()
}

private fun decodeBoundedUri(context: Context, uri: Uri, maxDim: Int): Bitmap? {
    return try {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            ImageDecoder.decodeBitmap(ImageDecoder.createSource(context.contentResolver, uri)) { decoder, info, _ ->
                val w = info.size.width.coerceAtLeast(1)
                val h = info.size.height.coerceAtLeast(1)
                val scale = minOf(maxDim.toFloat() / w, maxDim.toFloat() / h, 1f)
                decoder.setTargetSize((w * scale).toInt().coerceAtLeast(1), (h * scale).toInt().coerceAtLeast(1))
                decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
                decoder.setTargetColorSpace(ColorSpace.get(ColorSpace.Named.SRGB))
            }
        } else {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
            if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null
            var sample = 1
            while (bounds.outWidth / sample > maxDim * 2 || bounds.outHeight / sample > maxDim * 2) {
                sample *= 2
            }
            val opts = BitmapFactory.Options().apply {
                inSampleSize = sample
                inPreferredConfig = Bitmap.Config.ARGB_8888
            }
            val raw = context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, opts) }
                ?: return null
            val scale = minOf(maxDim.toFloat() / raw.width, maxDim.toFloat() / raw.height, 1f)
            if (scale < 1f) {
                val scaled = Bitmap.createScaledBitmap(
                    raw,
                    (raw.width * scale).toInt().coerceAtLeast(1),
                    (raw.height * scale).toInt().coerceAtLeast(1),
                    true
                )
                if (scaled !== raw) raw.recycle()
                scaled
            } else {
                raw
            }
        }
    } catch (_: Exception) {
        null
    }
}

fun extractWallpaperAccents(bmp: Bitmap): List<Color> {
    return try {
        val step = maxOf(1, minOf(bmp.width, bmp.height) / 24)
        val sw = maxOf(1, bmp.width / step)
        val sh = maxOf(1, bmp.height / step)
        val scaled = Bitmap.createScaledBitmap(bmp, sw, sh, true)
        val px = IntArray(sw * sh)
        scaled.getPixels(px, 0, sw, 0, 0, sw, sh)
        if (scaled !== bmp) scaled.recycle()
        val hist = mutableMapOf<Int, Int>()
        for (c in px) {
            val r = (c shr 16) and 0xFF
            val g = (c shr 8) and 0xFF
            val b = c and 0xFF
            val lum = (r * 299 + g * 587 + b * 114) / 1000
            if (lum < 28 || lum > 228) continue
            if (maxOf(r, g, b) - minOf(r, g, b) < 18) continue
            val q = ((r / 12) * 12 shl 16) or ((g / 12) * 12 shl 8) or ((b / 12) * 12)
            hist[q] = (hist[q] ?: 0) + 1
        }
        hist.entries
            .sortedByDescending { it.value }
            .take(4)
            .map { (key, _) ->
                Color(
                    ((key shr 16) and 0xFF).coerceAtMost(251) + 4,
                    ((key shr 8) and 0xFF).coerceAtMost(251) + 4,
                    (key and 0xFF).coerceAtMost(251) + 4
                )
            }
    } catch (_: Exception) {
        emptyList()
    }
}
