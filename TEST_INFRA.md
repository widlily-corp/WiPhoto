# Test Infrastructure Documentation (WiPhoto OTA Updates)

## 1. Overview
This document outlines the test architecture, environment setup, and execution methodology for the WiPhoto application, with specific focus on the OTA (Over-The-Air) Update subsystem (Requirements R1 and R2).

## 2. Test Framework & Environment
- **Test Runner**: Node.js built-in test runner (`node:test`)
- **Assertion Engine**: Node.js strict assertion library (`node:assert`)
- **Execution Sandbox**: Virtual Machine context (`node:vm`) for sandboxed execution of ES5/ES6 browser modules (`updater.js`, `utils.js`) without external heavy browser dependencies.
- **Mock DOM & Event Engine**: Custom lightweight HTML5 DOM & Tauri IPC mock environment built for high-performance end-to-end event loop testing.

## 3. Directory Layout & Test Conventions
Tests are co-located in `src/js/` following the `*.test.cjs` suffix convention:
- `src/js/updater_e2e.test.cjs`: Comprehensive 4-tier E2E & Integration test suite for OTA progress (R2) and graceful error handling (R1).
- `src/js/updater.test.cjs`: Component unit tests for version string parsing, markdown rendering, payload formatting, and state transitions.
- `src/js/tier1_tier2_features.test.cjs`: Core feature unit & boundary tests.
- `src/js/tier3_cross_features.test.cjs`: Integration tests across feature boundaries.
- `src/js/tier4_e2e_scenarios.test.cjs`: High-level scenario tests.
- `src/js/utils.test.cjs`: Utility helper unit tests.
- `src/js/spatial_stress.test.cjs`: Geo-spatial clustering performance benchmarks.
- `src/js/virtualgrid_stress.test.cjs`: DOM virtual grid stress and leak tests.

## 4. 4-Tier Testing Methodology
The suite implements strict 4-tier testing:
1. **Tier 1: Feature Coverage**: Verifies happy-path execution of visual progress indicators (R2) and graceful error handling (R1).
2. **Tier 2: Boundary & Edge Cases**: Tests zero content length, chunk overshoots, out-of-order progress events, rapid bursts, partial download drops, and retry loops.
3. **Tier 3: Cross-Feature Interactions**: Validates progress streaming uninterrupted by network drops, command palette error integration, and checksum verification failures.
4. **Tier 4: Real-World Scenarios**: Full end-to-end workflow simulations (OTA success, network drop + retry recovery, offline manual check fallback).

## 5. Running the Tests
To execute all tests across all modules:
```bash
npm test
```
To run a specific test file directly:
```bash
node --test src/js/updater_e2e.test.cjs
```
