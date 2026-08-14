# Original User Request

## Initial Request — 2026-08-02T14:16:57Z

<USER_REQUEST>
Улучшение системы автообновлений (OTA) для Tauri-приложения WiPhoto, чтобы сделать её более грамотной, отказоустойчивой и с удобным пользовательским интерфейсом.

Working directory: C:\Users\Widlily\Documents\projects\wiphoto
Integrity mode: development

## Requirements

### R1. Graceful Error Handling for OTA Updates
The update process must gracefully handle network failures or download interruptions. The application must not crash or freeze if the update fails to download or verify.

### R2. Visual Progress Indicator
The application must display a visual progress indicator (such as a progress bar or percentage) to the user during the OTA update download process, using the existing Tauri updater API events.

## Acceptance Criteria

### Error Handling
- [ ] Simulating a network failure during the update download results in a user-visible error message rather than a silent failure or application crash.
- [ ] The user is able to dismiss the error and continue using the application normally.

### Progress Visibility
- [ ] When an update is downloading, the UI actively updates to reflect the downloaded bytes or percentage.
- [ ] The progress indicator disappears or transitions to a "restarting" state upon successful download.
</USER_REQUEST>

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

