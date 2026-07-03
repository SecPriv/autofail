# Android 16 AOSP Emulator Setup for macOS (Apple Silicon)

This script sets up a self-contained Android development environment (Java, Android SDK, Emulator) and launches an Android 16 (API 36) AOSP emulator on macOS with Apple Silicon.

## Prerequisites

- macOS running on Apple Silicon (M1/M2/M3/M4)
- Internet connection
- ~8 GB of free disk space
- Docker is **not** required (this is a native setup)

## Usage

1. Open a terminal in this directory.
2. Run the launcher:
   ```bash
   ./launch_emulator.sh
   ```

### First Run

On the first execution, the script will:
- Download and install OpenJDK 17 in `./jdk` (if not already installed system-wide)
- Download and install the Android SDK Command Line Tools in `./android-sdk`
- Download the Android 16 (API 36) AOSP ARM64 system image (~1.5 GB)
- Create an AVD named `ae_android16`
- Launch the emulator

This may take 10–20 minutes depending on your connection.

### Subsequent Runs

The script will skip all downloads and immediately launch the existing `ae_android16` AVD.

## Wiping / Recreating the AVD

To start fresh, delete the AVD directory and re-run the script:
```bash
rm -rf android-sdk/avd/ae_android16.avd
./launch_emulator.sh
```

To wipe the entire self-contained environment:
```bash
rm -rf jdk android-sdk
```

## Troubleshooting

- **"This script requires macOS running on Apple Silicon"**: The emulator requires hardware virtualization (HVF) only available on Apple Silicon. Running on Intel Macs or other OSes is not supported.
- **"The required AOSP system image is not available"**: Google may not have published the plain AOSP image for Android 16 yet. The script will strictly fail in this case. You would need to use the Google APIs image instead (requires modifying the script).
- **Emulator is slow**: Ensure macOS virtualization permissions are enabled. The emulator automatically uses `-gpu host` for native graphics acceleration.
