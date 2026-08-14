# Master Implementation Plan — WiPhoto v5.0

## High-Level Objective
Deliver the complete set of professional features for WiPhoto (Tauri v2 + Rust + Vanilla JS) matching all requirements and acceptance criteria in ORIGINAL_REQUEST.md.

## Phase 0: Survey & Architecture Discovery
- Spawn 3 parallel Explorers to investigate:
  1. Rust backend (`src-tauri` structure, dependencies in `Cargo.toml`, current Tauri commands, test setup).
  2. Frontend architecture (`src/` JS structure, UI components, state management, test setup in `package.json`).
  3. Feature integration surface (Tauri IPC commands, event bus, format handling, workers/shaders integration points).

## Phase 1: PROJECT.md & Decomposition
- Synthesize survey findings into `PROJECT.md`.
- Enumerate Feature Inventory (R1.1 - R4.3).
- Define milestones and interface contracts:
  - Milestone 1: R1 (Local AI & Deduplication - tract-onnx integration, face indexing & duplicate detection Tauri commands, Rust tests)
  - Milestone 2: R2 (Pro Workflow UI - Split View / Compare Mode, Filmstrip view, RGB/Luminance histograms)
  - Milestone 3: R3 (WebGPU & Web Workers - WebGPU non-destructive adjustments, Web Worker offloading for Virtual Grid & sorting)
  - Milestone 4: R4 (Advanced Formats & Batch Export - AVIF/JXL backend decoding, Batch Export module)
  - Milestone 5: E2E Test Suite & Integration Hardening (`npm run test` & `cargo test`)

## Phase 2: Iterative Execution & Gating
- Dispatch sub-orchestrators / specialist workers for each milestone following standard iteration loop:
  - Explorer -> Worker -> Reviewer -> Challenger -> Forensic Auditor -> Gate Verdict (`GATE_STATUS.md`)
- Monitor progress, manage dead ends, and enforce integrity.

## Phase 3: Victory Audit & Handoff
- Verify all unit and integration tests pass with 0 errors (`npm run test` and `cargo test`).
- Write final summary in `progress.md` and report completion to parent Sentinel.
