# Restart adb as root
adb root

# Wait a second for the daemon to restart
sleep 2

adb push setup_files/script.sh /data/local/tmp

adb shell "chmod +x /data/local/tmp/script.sh"
adb shell "/data/local/tmp/script.sh"

adb shell "rm -rf /data/local/tmp/etc-tmp"
adb shell "mkdir /data/local/tmp/etc-tmp"
adb shell "cp -r /system/etc/. /data/local/tmp/etc-tmp/"
adb shell 'printf "127.0.0.1\ta.com\n127.0.0.1\tb.com\n" >> /data/local/tmp/etc-tmp/hosts'

adb shell "mount -t tmpfs tmpfs /system/etc/"
adb shell "cp -r /data/local/tmp/etc-tmp/. /system/etc/"
adb shell "chown root:root /system/etc/*"
adb shell "chmod 644 /system/etc/*"
adb shell "chcon u:object_r:system_file:s0 /system/etc/*"

adb reverse tcp:8080 tcp:8080 > /dev/null
adb reverse tcp:8443 tcp:8443 > /dev/null
adb reverse tcp:8081 tcp:8443 > /dev/null

adb shell "iptables -t nat -A OUTPUT -p tcp --dport 80 -d 127.0.0.1 -j REDIRECT --to-port 8080"
adb shell "iptables -t nat -A OUTPUT -p tcp --dport 443 -d 127.0.0.1 -j REDIRECT --to-port 8443"

echo "Network setup completed"
