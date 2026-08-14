# Original User Request

## 2026-08-02T04:44:52Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview

Fix the thumbnail display issue and perform a deep audit of the WiPhoto (Tauri) frontend and Rust backend to resolve any other bugs. Optimize GitHub Actions for faster OTA updates across Windows, macOS, and Linux. Verify OTA functionality and prepare the codebase for the 5.0 release on GitHub.

Working directory: c:\Users\Widlily\Documents\projects\wiphoto
Integrity mode: development

## Requirements

### R1. Fix Thumbnail Display and Deep Audit
Identify and fix the issue preventing thumbnails (ARW/JPG) from displaying correctly in the UI. Conduct a deep audit of the frontend and Rust backend to fix any other existing bugs or UI errors.

### R2. Optimize GitHub Actions for OTA
Review and rewrite the existing GitHub Actions CI/CD pipeline to be optimized and fast. It must support OTA (Over-The-Air) updates for Windows, macOS, and Linux platforms.

### R3. Verify OTA Updates Implementation
Ensure that the OTA update mechanism is correctly implemented and functional in the Tauri application code, enabling automatic updates from GitHub Releases.

### R4. Release 5.0
After all fixes and OTA optimizations are applied and verified, commit the changes, push to GitHub, and trigger the 5.0 release process.

## Acceptance Criteria

### Thumbnail Fix and Audit
- [ ] Thumbnails for both raw (ARW) and JPG formats are correctly rendered in the gallery view.
- [ ] No console errors or backend panics occur during normal navigation and image loading.
- [ ] An independent agent acting as a judge confirms the UI renders thumbnails without broken image icons or black boxes, and that the audit resolved identified bugs.

### GitHub Actions and OTA Verification
- [ ] The GitHub Actions workflow file (`.github/workflows/ci.yml` or similar) builds for Windows, macOS, and Linux concurrently and is optimized for speed.
- [ ] The Tauri configuration is properly set up for OTA updates using GitHub Releases as the endpoints.
- [ ] An independent agent acting as a judge confirms the GitHub Actions pipeline is valid, fast, and that the OTA update logic in the application is correctly implemented.

## Follow-up — 2026-08-03T06:21:27Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview

Добавление комплексного пакета профессиональных функций в WiPhoto (Tauri v2 + Rust + Vanilla JS), включая локальный AI (распознавание лиц и дубликатов), режим сравнения (Split View), WebGPU-рендеринг, Web Workers и поддержку новых форматов (AVIF, JPEG XL).

Working directory: C:\Users\Widlily\Documents\projects\WiPhoto
Integrity mode: development

## Requirements

### R1. Local AI & Deduplication
Implement local face recognition and smart deduplication using `tract-onnx` in the Rust backend. Provide Tauri commands to index faces and find similar/duplicate images.

### R2. Pro Workflow UI
Implement a Split View / Compare Mode for side-by-side photo comparison, a Filmstrip view for the Loupe mode, and live RGB/Luminance histograms.

### R3. WebGPU & Web Workers
Implement a WebGPU-based renderer for non-destructive adjustments (exposure, contrast, HSL) and offload the Virtual Grid and array sorting logic to Web Workers to ensure the main thread remains unblocked.

### R4. Advanced Formats & Batch Export
Add support for decoding AVIF and JPEG XL formats in the Rust backend. Implement a Batch Export module with options for resizing, format conversion, and EXIF stripping.

## Acceptance Criteria

### Verification & Testing
- [ ] **R1 (AI)**: A Rust integration test must successfully load a dummy ONNX model (or mock) and generate an embedding/hash without panicking.
- [ ] **R2 & R3 (UI & Architecture)**: Node.js tests (`npm run test`) must verify the logic of the Web Worker message passing and the Split View state manager.
- [ ] **R4 (Formats)**: A Rust test (`cargo test`) must verify that an image can be processed through the batch export pipeline successfully.
- [ ] **Execution**: Both `npm run test` and `cargo test --manifest-path src-tauri/Cargo.toml` must pass cleanly with 0 errors.

