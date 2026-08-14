# Handoff Report — Backend Architecture & Requirements Survey (R1 & R4)

## 1. Observation

### 1.1 Source Files & Paths Inspected
- `src-tauri/Cargo.toml` (lines 1-71): Currently includes `tract-onnx = "0.21.3"` (line 62) and `image = { version = "0.25", features = ["jpeg", "png", "gif", "bmp", "tiff", "webp", "ico"] }` (line 27). `avif` feature is missing from `image` features list, and `jxl-oxide` dependency is missing.
- `src-tauri/src/lib.rs` (lines 1-394): Custom protocol handler `handle_asset_custom_protocol` (lines 70-229) handles HTTP Range requests and ETag caching, but MIME mapping for `.jxl` is missing. Tauri command handler `invoke_handler!` (lines 289-340) registers scanner, thumbnails, metadata, file_ops, duplicates, editor, export, settings, xmp, and search commands.
- `src-tauri/src/onnx.rs` (lines 1-761): Uses `tract-onnx` for YOLOv8 model loading (`init_model()`, lines 31-75), image object detection (`analyze_image()`, lines 180-276), vector normalization, cosine similarity (`cosine_similarity()`, lines 365-382), text embedding (`extract_text_embedding()`, lines 398-525), and image embedding (`extract_image_embedding()`, lines 528-665). Model initialization attempts HTTP download from GitHub Releases (`download_model()`, lines 77-133), which fails offline.
- `src-tauri/src/commands/duplicates.rs` (lines 1-477): Implements perceptual hashes (`compute_hash()`, lines 109-180), BK-Tree spatial search (`bktree_query()`, lines 193-217), and commands `find_duplicates`, `get_duplicate_stats`, `compute_phash`. Face indexing and AI embedding search commands are not yet exposed.
- `src-tauri/src/commands/export.rs` (lines 1-229): Batch export command `export_files` (lines 73-177) supports `paths`, `dest_dir`, `format`, `quality`, `max_width`, `max_height`, `watermark_text`. EXIF metadata stripping option (`strip_exif: Option<bool>`) is missing.
- `src-tauri/src/models/image_info.rs` (lines 1-235): `IMAGE_EXTENSIONS` constant (lines 4-7) contains `"avif"`, but does not contain `"jxl"`.
- `src-tauri/tests/`: Integration tests present in `backend_stress_suite.rs`, `e2e_v500_tests.rs`, `xmp_roundtrip_stress.rs`.

---

## 2. Logic Chain

1. **R1 (Local AI & Deduplication)**:
   - *Observation*: `tract-onnx 0.21` is present in `Cargo.toml:62` and `src/onnx.rs` performs YOLOv8 inference and vector embedding extraction.
   - *Reasoning*: Requirement R1 demands face recognition indexing and duplicate finding via Tauri commands, plus a Rust integration test loading a dummy ONNX model/mock without panicking.
   - *Deduction*: `src/onnx.rs` must be enhanced to allow offline dummy model loading/mocking for tests, and `src/commands/duplicates.rs` / `src/lib.rs` must expose explicit Tauri commands (`index_faces`, `find_similar_images`).

2. **R4 (Advanced Formats & Batch Export)**:
   - *Observation*: `Cargo.toml:27` image crate features omit `avif`, `Cargo.toml` lacks `jxl-oxide`, `src/models/image_info.rs:4-7` lacks `"jxl"`, and `src/commands/export.rs:73` lacks EXIF stripping option.
   - *Reasoning*: Requirement R4 demands decoding support for AVIF and JPEG XL (`.jxl`), a Batch Export module with options for resizing, format conversion, and EXIF stripping, plus an integration test verifying batch export.
   - *Deduction*: Adding `avif-native`/`avif` feature and `jxl-oxide = "0.9"` dependency to `Cargo.toml`, updating MIME and extension tables, adding `strip_exif: Option<bool>` to `export_files`, and writing a batch export integration test will fulfill R4.

---

## 3. Caveats

- **Scope boundary**: This investigation was strictly read-only analysis as assigned to Backend Architecture Explorer. Code implementation changes were intentionally reserved for the Implementer agent.
- **Tract Model Execution**: `tract-onnx 0.21.3` is lightweight and pure-Rust, which guarantees cross-platform compatibility without C++ ONNX Runtime shared library dynamic linking issues on Windows/macOS/Linux.
- **JPEG XL crate selection**: `jxl-oxide` is a pure Rust JPEG XL decoder crate that integrates seamlessly with the `image` crate ecosystem without native C library build toolchain requirements.

---

## 4. Conclusion

The WiPhoto Rust backend architecture is robust, modular, and performance-optimized. Implementing requirements R1 and R4 requires specific, surgical additions:
1. Enable `avif` feature for `image` crate and add `jxl-oxide = "0.9"` in `Cargo.toml`.
2. Add `"jxl"` to `IMAGE_EXTENSIONS` in `image_info.rs` and MIME mapping in `lib.rs`.
3. Support `strip_exif` parameter and EXIF removal in `export_files` (`export.rs`).
4. Support dummy model loading in `onnx.rs` and expose `index_faces` / `find_similar_images` commands in `duplicates.rs` & `lib.rs`.
5. Add Rust integration tests in `tests/` to verify R1 (dummy ONNX model execution) and R4 (batch export pipeline).

---

## 5. Verification Method

### 5.1 Verification Commands
- Check cargo test suite execution:
  `cargo test --manifest-path src-tauri/Cargo.toml`
  (Must pass with 0 errors).

### 5.2 Files to Inspect
- `src-tauri/Cargo.toml` (verify dependencies and features).
- `src-tauri/src/lib.rs` (verify command handler registrations and MIME types).
- `src-tauri/src/onnx.rs` (verify ONNX model initialization and dummy model fallback).
- `src-tauri/src/commands/duplicates.rs` (verify face indexing and AI duplicate commands).
- `src-tauri/src/commands/export.rs` (verify `strip_exif` parameter and format options).
- `src-tauri/tests/` (verify R1 & R4 integration tests).

### 5.3 Invalidation Conditions
- Any test failure or panic during `cargo test --manifest-path src-tauri/Cargo.toml`.
- Network dependencies causing `cargo test` to fail when offline.
