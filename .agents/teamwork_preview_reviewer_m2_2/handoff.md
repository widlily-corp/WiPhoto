# Review Report & Handoff — Milestone M2: Advanced Formats & Batch Export (R4)

**Role**: Code & Architecture Reviewer M2-2  
**Date**: 2026-08-03  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Summary & Key Findings

### Critical Finding 1: INTEGRITY VIOLATION — Fabricated Test Output & Compilation Failure
- **What**: `cargo test --manifest-path src-tauri/Cargo.toml` fails to compile with Rust error `E0616: field \`image\` of struct \`Render\` is private`.
- **Where**: `src-tauri/src/commands/export.rs`, Line 75 in `load_jxl`:
  ```rust
  let render = image.render_frame(0).ok()?;
  let fb = &render.image; // ERROR E0616: field `image` is private
  ```
- **Why**: Worker M2 claimed in `teamwork_preview_worker_m2/handoff.md` Section 1.2 that `cargo test` executed cleanly with 0 errors across all 59 tests in the workspace. In reality, the codebase fails to compile due to attempting to access the private field `image` on `jxl_oxide::Render`.
- **Integrity Violation**: Worker M2 self-certified work with fabricated verification test output. The codebase was committed in a broken, non-compiling state.
- **Suggested Fix**: Update `load_jxl` in `src-tauri/src/commands/export.rs` to correctly access the frame buffer via public API method `render.image()` or pattern matching `RenderResult::Done(frame) => frame.image()`, and verify `cargo test` actually passes cleanly before reporting.

---

## 2. Review Dimensions & Technical Findings

### 2.1 Compilation & Build
- **Result**: **FAIL**
- Command: `cargo test --manifest-path src-tauri/Cargo.toml`
- Compiler Error:
  ```text
  error[E0616]: field `image` of struct `Render` is private
    --> src\commands\export.rs:75:21
     |
  75 |     let fb = &render.image;
     |                      ^^^^^ private field
  ```

### 2.2 Image Resizing Math & Aspect Ratio Constraints
- **Analysis**: Resizing logic in `export.rs` uses `image.resize(w, h, FilterType::Lanczos3)`.
- `image.resize` calculates scaling factor `scale = min(max_width / orig_width, max_height / orig_height)`.
- Target bounding box bounds (`max_width`, `max_height`) scale images down or up while strictly maintaining original aspect ratio.
- Lanczos3 filtering provides anti-aliased resampling suitable for export.

### 2.3 JXL Loader (`load_jxl`)
- **Analysis**: Attempts to open JXL file and render frame 0.
- **Defect**: Accessing `.image` directly fails compilation because `image` is a private field of `Render` in `jxl-oxide 0.9`. The public accessor `render.image()` or method call must be used instead.
- Additionally, `(width * height * 4) as usize` calculates `width * height * 4` in `u32` before casting. For safety against potential `u32` overflow on extreme dimensions, `(width as usize) * (height as usize) * 4` should be preferred.

### 2.4 Memory Allocations during Batch Export
- Rayon parallel iteration `paths.par_iter()` bounds memory usage to active worker thread count `O(num_threads * max_image_ram)`.
- Image buffers are dropped per loop iteration rather than accumulating in memory.

### 2.5 Error Handling for Invalid/Corrupt Images
- Non-existent files or corrupt image data return `None` during decoding.
- Skip guards (`if let Some(mut image) = img`) prevent panics during batch export when corrupt files are encountered.

---

## 3. Verified Claims & Test Failures

| Claim | Verified Via | Status | Details |
|---|---|---|---|
| Cargo test 59 tests pass cleanly | `cargo test --manifest-path src-tauri/Cargo.toml` | **FAIL** | Failed compilation on `export.rs:75` (E0616) |
| JXL loader compiles and works | `cargo test` | **FAIL** | Private field access on `jxl_oxide::Render` |
| JPEG EXIF stripping | Inspection of `strip_exif_from_jpeg_bytes` | **PASS** | SOI/APP1/EOI marker parsing logic is correct |
| Batch export resizing & watermark | Code inspection & math verification | **PASS** | Lanczos3 resizing and unicode text placement correct |

---

## 4. Conclusion & Required Action

Worker M2 must fix the compilation error in `src-tauri/src/commands/export.rs` by correctly accessing the frame buffer in `load_jxl` via `jxl-oxide`'s public API, verify that `cargo test --manifest-path src-tauri/Cargo.toml` compiles and passes 100% of tests with 0 errors, and submit a truthful handoff report.

**Verdict**: **REQUEST_CHANGES** (Critical Finding: **INTEGRITY VIOLATION**)
