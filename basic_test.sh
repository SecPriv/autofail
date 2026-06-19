#!/bin/bash

# Check if adb is installed
if ! command -v adb &> /dev/null; then
    echo "Error: adb is not installed"
    exit 1
fi

# Get connected devices
devices=$(adb devices 2>&1)

# Check if any devices are listed
device_count=$(echo "$devices" | grep -v "List of devices" | grep "device$" | wc -l)

if [ "$device_count" -eq 0 ]; then
    echo "Error: No Android device connected"
    echo "$devices"
    exit 1
fi

# Check if device is authorized (not unauthorized)
unauthorized=$(echo "$devices" | grep "unauthorized$" | wc -l)

if [ "$unauthorized" -gt 0 ]; then
    echo "Error: Device is unauthorized. Please accept the USB debugging prompt on your device."
    exit 1
fi

echo "Success: Android device connected and USB debugging is enabled"
adb devices
exit 0
