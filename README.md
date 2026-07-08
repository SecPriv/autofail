This repository contains the artifacts for the paper **AutoFail: Breaking Web Boundaries using Android’s Autofill Framework**. 

### Adapt

The `ADAPT` directory contains the architecture to run the differential testing described in Sec. 4. `ADAPT/server/results.db` contains the results of our testing that we used to produce the analysis discussed in Sec 5.

### RealWorldAnalysis

The `RealWorldAnalysis` directory contains the artifacts to reproduce the real-world analysis discussed in Sec 8., alongside the data produced by such tools that we used in the paper. In particular, `RealWorldAnalysis/IframeConfigurationAnalysis` and `RealWorldAnalysis/HeaderConfigurationsAnalysis` contain the artifact for the analysis discussed in Sec 8.1  paragraph **Iframe Analysis.** and  paragraph **Embeddability Analysis** respectively.

### Spill

The `Spill` directory contains the source code of a PoC app that performs the **Cross-Context Account Oracle** discussed in Sec 6.

### XCLMitigation

The `XCLMitigation` directory contains the source code of a PoC app that performs the autofill using the secure interaction flow to mitigate the **Cross-Context Account Oracle** described in Sec 7.


## Artifact Evaluation

### Prerequisites

- macOS on Apple Silicon (required by the Android emulator), or a physical Android device (rooted, API 36 / Android 16)
- ~8 GB free disk space
- Internet connection

### One-time setup

Run `./setup.sh`. This installs (user-space, no root):
- `uv` + Python 3.12 virtualenv (flask, frida) for the ADAPT orchestrator
- Android `platform-tools` (adb) — required even for a physical device
- Node.js + npm for the real-world analysis crawler
- Java 17+ JDK (only if system Java is older than 17) — for building the Android PoC apps via Gradle

### Running the evaluation

1. **Start the emulator** (skip if using a physical device):
   ```
   ./emulator/launch_emulator.sh
   ```
   Installs Java 17, the Android SDK, and launches the `ae_android16` Google APIs emulator (rootable, no Play Store).

2. **Install Chrome + password managers**:
   ```
   ./emulator/install_apks.sh
   ```

3. **Start the ADAPT orchestrator** (frida + network setup + server):
   ```
   ./ADAPT/run_server.sh
   ```

4. **Sanity check** (device, frida, server reachability):
   ```
   ./basic_test.sh
   ```

5. **Cross-Context Account Oracle PoC** (Sec 6) — build the app first, then deploy:
   ```
   cd CrossContextAccountOracle/Spill && ./gradlew assembleDebug && cd ../..
   ./CrossContextAccountOracle/deploy-and-run.sh
   ```

6. **Mitigation PoC** (Sec 7) — build the XCLMitigation app first, then install and run:
   ```
   cd mitigation/XCLMitigation && ./gradlew assembleDebug && cd ../..
   ./mitigation/install-apps.sh
   ./mitigation/run-poc.sh
   ```

7. **Real-world analysis** (Sec 8):
   - Embeddability analysis: `cd RealWorldAnalysis/HeaderConfigurationsAnalysis && ./verify_analysis.sh`
   - Iframe analysis: `cd RealWorldAnalysis/IframeConfigurationAnalysis && ./verify_analysis.sh`
   - Iframe crawler sample: `cd RealWorldAnalysis/IframeConfigurationAnalysis && ./run_crawler_sample.sh`

