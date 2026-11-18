package io.github.magaking.dolbybuilder

/** Keep the fallback explicit: AGSL Liquid Glass optics require Android 13+ and hardware rendering. */
internal fun useLiquidGlass(
    enabled: Boolean,
    apiLevel: Int,
    hardwareAccelerated: Boolean,
    lowRam: Boolean,
): Boolean = enabled && apiLevel >= 33 && hardwareAccelerated && !lowRam
