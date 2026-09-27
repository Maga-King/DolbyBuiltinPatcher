#!/system/bin/sh
MODDIR=${0%/*}
echo 'Dolby KSU: one-shot status, no changes'
echo 'Next-boot initrc cache (read-only):'
/system/bin/sh "$MODDIR/initrc-cache.sh" check || true
if cmp -s "$MODDIR/.runtime/boot" /proc/sys/kernel/random/boot_id; then
    cat "$MODDIR/.runtime/status" 2>/dev/null || true
    for name in gate codec commit recover; do
        echo "$name:"
        tail -20 "$MODDIR/.runtime/$name.log" 2>/dev/null
    done
else
    echo 'No gate record for CURRENT boot; old status is not proof of activation.'
fi
echo 'Current Dolby services (running is not proof of actual decoding):'
for name in mio-dolby-hidl mio-dolby-dms mio-dolby-codec; do
    echo "$name: $(getprop init.svc.$name)"
done
echo "Codec PID: $(pidof dolbycodecservice)"
echo 'Codec interface:'
timeout 3 service check android.hardware.media.c2.IComponentStore/default9 2>/dev/null || true
echo 'HWS:'
getprop init.svc.hwservicemanager
getprop hwservicemanager.ready
echo 'AIDL registrations:'
timeout 5 service list 2>/dev/null | grep -E 'vendor.dolby.dms|IComponentStore/default9|audio.effect.IFactory' || true
echo 'HIDL registration:'
timeout 5 lshal 2>/dev/null | grep 'vendor.dolby.hardware.dms@2.0::IDms/default' || true
