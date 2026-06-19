adb shell "su -c killall simple_program" 2>/dev/null || true
adb push setup_files/simple_program /data/local/tmp
adb shell "su -c chmod 755 /data/local/tmp/simple_program"
adb shell "su -c 'nohup /data/local/tmp/simple_program > /dev/null 2>&1 &'"