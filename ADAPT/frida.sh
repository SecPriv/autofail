adb push setup_files/simple_program /data/local/tmp
adb shell "su -c chmod 755 /data/local/tmp/simple_program"
adb shell "su -c /data/local/tmp/simple_program &"