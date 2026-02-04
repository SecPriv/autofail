adb push setup_files/script.sh /data/local/tmp

adb shell "su -c chmod +x /data/local/tmp/script.sh"
adb shell "su -c /data/local/tmp/script.sh"

adb shell "su -c rm -rf /data/local/tmp/etc-tmp"
adb shell "su -c mkdir /data/local/tmp/etc-tmp"
adb shell "su -c cp -r /system/etc/. /data/local/tmp/etc-tmp/"
adb shell "su -c 'printf \"127.0.0.1\ta.com\n127.0.0.1\tb.com\n\" >> /data/local/tmp/etc-tmp/hosts'"

adb shell "su -c mount -t tmpfs tmpfs /system/etc/"
adb shell "su -c cp -r /data/local/tmp/etc-tmp/. /system/etc/"
adb shell "su -c chown root:root /system/etc/*"
adb shell "su -c chmod 644 /system/etc/*"
adb shell "su -c chcon u:object_r:system_file:s0 /system/etc/*"

adb reverse tcp:8080 tcp:80 > /dev/null
adb reverse tcp:8443 tcp:443 > /dev/null
adb reverse tcp:8081 tcp:443 > /dev/null

adb shell "su -c iptables -t nat -A OUTPUT -p tcp --dport 80 -d 127.0.0.1 -j REDIRECT --to-port 8080"
adb shell "su -c iptables -t nat -A OUTPUT -p tcp --dport 443 -d 127.0.0.1 -j REDIRECT --to-port 8443"

echo "Network setup completed"


