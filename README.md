This repository contains the artifacts for the paper **AutoFail: Breaking Web Boundaries using Android’s Autofill Framework**. 

### Adapt

The `ADAPT` directory contains the architecture to run the differential testing described in Sec. 4. `ADAPT/server/results.db` contains the results of our testing that we used to produce the analysis discussed in Sec 5.

### RealWorldAnalysis

The `RealWorldAnalysis` directory contains the artifacts to reproduce the real-world analysis discussed in Sec 8., alongside the data produced by such tools that we used in the paper. In particular, `RealWorldAnalysis/HeaderConfigurationsAnalysis ' and `RealWorldAnalysis/HeaderConfigurationsAnalysis`  contain the artifact for the analysis discussed in Sec 8.1 and Sec 8.2, respectively.

### Spill

The `Spill` directory contains the source code of a PoC app that performs the **Cross-Context Account Oracle** discussed in Sec 6.

### XCLMitigation

The `XCLMitigation` directory contains the source code of a PoC app that performs the autofill using the secure interaction flow to mitigate the **Cross-Context Account Oracle** described in Sec 7.


