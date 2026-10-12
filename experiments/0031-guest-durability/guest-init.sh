#!/bin/busybox sh
# This file belongs only in the disposable initramfs, never a host startup path.
BB=/bin/busybox
if [ "$$" -ne 1 ] || ! $BB grep -q 'imageinfo_disposable_guest=owned-marker-v1' /proc/cmdline 2>/dev/null; then
    # /proc is not mounted at initial PID 1 startup. Mount it only when PID 1 and
    # the independently supplied kernel command line can be checked afterward.
    if [ "$$" -ne 1 ]; then echo IMAGEINFO_REFUSE_HOST; exit 1; fi
    $BB mkdir -p /proc
    $BB mount -t proc proc /proc || exit 1
    if ! $BB grep -q 'imageinfo_disposable_guest=owned-marker-v1' /proc/cmdline; then echo IMAGEINFO_REFUSE_GUEST; exit 1; fi
fi
$BB mkdir -p /sys /dev /data /tmp
$BB mount -t sysfs sysfs /sys
$BB mount -t devtmpfs devtmpfs /dev
$BB modprobe virtio_pci
$BB modprobe virtio_blk
$BB modprobe ext4
if ! $BB mount -t ext4 -o data=ordered,errors=remount-ro /dev/vda /data; then echo IMAGEINFO_MOUNT_FAILED; $BB poweroff -f; exit 1; fi
$BB stty -echo -icanon < /dev/ttyS0
exec < /dev/ttyS0 > /dev/ttyS0 2>&1
echo IMAGEINFO_GUEST_READY
$BB uname -r
$BB cat /proc/mounts
# These controls affect this separate emulated kernel, never WSL/Windows.
echo 1 > /proc/sys/kernel/unknown_nmi_panic
echo 1 > /proc/sys/kernel/panic_on_unrecovered_nmi
mode=worker
for word in $($BB cat /proc/cmdline); do case "$word" in imageinfo_mode=*) mode=${word#imageinfo_mode=};; esac; done
case "$mode" in worker|worker-fail-*|full-disk)
    $BB mkdir /data/txn || exit 1
    $BB chmod 700 /data/txn
    if [ "$mode" = full-disk ]; then
        # Only this newly copied, 64 MiB emulated data disk is filled.
        $BB dd if=/dev/zero of=/data/fill.bin bs=65536 count=1024
        mode=worker
    fi
    $BB mkfifo /tmp/worker-input
    exec 3<>/tmp/worker-input
    /probe "$mode" /data/txn < /tmp/worker-input &
    child=$!
    while read -r command; do
        echo "IMAGEINFO_COMMAND:$command"
        case "$command" in
            continue|cancel|fail) echo "$command" >&3;;
            kill-worker) $BB kill -9 "$child"; echo IMAGEINFO_WORKER_KILLED;;
            shutdown) break;;
            '') continue;;
            *) echo "IMAGEINFO_CONTROL_REFUSED:$command";;
        esac
    done
    ;;
*)
    # Deliberate actors touch only fixed names in the owned marker transaction.
    case "$mode" in
        missing-intent) $BB rm /data/txn/intent.record;;
        missing-records) $BB rm /data/txn/intent.record /data/txn/prepared.record;;
        corrupt-intent) echo corrupt > /data/txn/intent.record;;
        oversized-intent) $BB dd if=/dev/zero of=/data/txn/intent.record bs=65536 count=2;;
        inaccessible-intent) $BB chmod 000 /data/txn/intent.record;;
        symlink-intent) $BB mv /data/txn/intent.record /data/txn/saved.record; $BB ln -s saved.record /data/txn/intent.record;;
        fifo-intent) $BB rm /data/txn/intent.record; $BB mkfifo /data/txn/intent.record;;
        corrupt-observation) echo corrupt > /data/txn/observation.record;;
        missing-recovery) $BB rm /data/txn/recovery.bin;;
        corrupt-recovery) echo foreign > /data/txn/recovery.bin;;
        inaccessible-root) $BB chmod 000 /data/txn;;
        missing-output) $BB rm /data/txn/output.bin;;
        foreign-output) $BB mv /data/txn/output.bin /data/txn/retained.bin; echo foreign > /data/txn/output.bin; $BB chmod 600 /data/txn/output.bin;;
        corrupt-output) echo changed > /data/txn/output.bin;;
        inaccessible-output) $BB chmod 000 /data/txn/output.bin;;
        symlink-output) $BB mv /data/txn/output.bin /data/txn/retained.bin; $BB ln -s retained.bin /data/txn/output.bin;;
        fifo-output) $BB rm /data/txn/output.bin; $BB mkfifo /data/txn/output.bin;;
        directory-output) $BB rm /data/txn/output.bin; $BB mkdir /data/txn/output.bin;;
        extra-alias) $BB ln /data/txn/recovery.bin /data/txn/foreign-alias.bin;;
        inspect|finalize|prune|admit) ;;
        *) echo IMAGEINFO_MODE_REFUSED; $BB poweroff -f; exit 1;;
    esac
    snapshot() {
        echo IMAGEINFO_SNAPSHOT_BEGIN
        $BB stat -c '%n:%i:%a:%u:%h:%s' /data/txn
        for name in recovery.bin prepared.record intent.record output.bin observation.record saved.record retained.bin foreign-alias.bin; do
            path=/data/txn/$name
            if [ -L "$path" ]; then $BB ls -ld "$path";
            elif [ -e "$path" ]; then
                $BB stat -c '%n:%i:%a:%u:%h:%s' "$path"
                if [ -f "$path" ]; then $BB sha256sum "$path"; fi
            else echo "absent:$name"; fi
        done
        echo IMAGEINFO_SNAPSHOT_END
    }
    snapshot
    /probe inspect /data/txn
    # Every state must refuse repair/prune without reopening/mutating artifacts.
    /probe finalize /data/txn
    /probe prune /data/txn
    /probe admit /data/txn
    snapshot
    echo IMAGEINFO_INSPECTION_DONE
    read -r command
    ;;
esac
echo IMAGEINFO_SHUTDOWN_BEGIN
$BB umount /data
echo IMAGEINFO_UNMOUNTED
$BB poweroff -f
