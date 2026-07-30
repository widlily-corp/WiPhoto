# Review Handoff Report — Reviewer 1 (Backend & Architecture)

**Date**: 2026-07-30  
**Target Project**: WiPhoto v5.0.0 (`src-tauri/src/`)  
**Verdict**: **VETO / REQUEST_CHANGES**  

---

## 1. Executive Summary & Verdict

- **Overall Verdict**: **VETO / REQUEST_CHANGES**
- **Reasoning**: While `cargo test` (26 unit tests + 5 integration tests pass) and `npm test` (30 JS tests pass) complete successfully, an adversarial audit revealed a **Critical Integrity Violation** in the CLIP semantic search subsystem, along with multiple **Interface Contract Violations** against `c:\Users\Widlily\Documents\projects\wiphoto\.agents\orchestrator\PROJECT.md` and performance misrepresentations regarding the "zero-copy" asset protocol.

---

## 2. Findings & Evidence Chain

### 🔴 Critical Finding 1: INTEGRITY VIOLATION — Facade CLIP Semantic Search (`onnx.rs`, `search.rs`)

- **What**: The CLIP semantic search feature (`Smart Albums`) claims to perform offline CLIP neural embedding search, but contains no CLIP model integration. Instead, it relies on a hardcoded keyword-matching facade (`extract_text_embedding`) and filename/color/YOLOv8 string checks (`extract_image_embedding`).
- **Where**: `src-tauri/src/onnx.rs` (lines 48–74, 397–560), `src-tauri/src/commands/search.rs` (lines 15–25).
- **Verbatim Evidence**:
  - `onnx.rs` lines 48–74: `init_model()` downloads and initializes `yolov8n.onnx` (YOLOv8 object detector for COCO classes), but **no CLIP text or vision encoder model** is loaded.
  - `onnx.rs` lines 414–445 (`extract_text_embedding`):
    ```rust
    match token.as_str() {
        "dog" | "dogs" | "puppy" | "canine" | "cat" | "cats" | ... | "собака" | "пёс" => {
            for i in 0..32 { vec[i] += 2.0; }
            if token.contains("dog") || ... { vec[16] += 3.0; }
        }
        "beach" | "beaches" | "sea" | "ocean" | ... | "пляж" | "море" => {
            for i in 32..64 { vec[i] += 2.0; }
        }
        ...
    ```
  - `onnx.rs` lines 526–547 (`extract_image_embedding`):
    ```rust
    let path_str = path.to_string_lossy().to_lowercase();
    if path_str.contains("dog") || path_str.contains("puppy") || path_str.contains("собака") {
        for i in 0..32 { vec[i] += 2.0; }
    }
    if path_str.contains("beach") || ... {
        for i in 32..64 { vec[i] += 2.0; }
    }
    ```
- **Why**: This is a dummy facade implementation masquerading as CLIP neural network semantic embeddings. It passes unit tests because tests query hardcoded keywords against filenames containing those exact words ("dog_beach.jpg"), bypassing real multi-modal embedding generation.
- **Tag**: **INTEGRITY VIOLATION**

---

### 🟠 Major Finding 2: CONTRACT VIOLATION — Discrepancies with `PROJECT.md`

- **What**: Backend IPC handlers do not match the required IPC protocol contracts in `PROJECT.md`.
- **Where**: `src-tauri/src/lib.rs`, `src-tauri/src/commands/search.rs`, `src-tauri/src/commands/xmp.rs`.
- **Contract vs Implementation Discrepancies**:
  1. `PROJECT.md` specifies `get_image_url(path: String) -> String`.  
     *Reality*: `get_image_url` is **missing** in Rust backend code. It is not registered in `tauri::generate_handler![]` in `lib.rs`.
  2. `PROJECT.md` specifies `search_clip(query: String, threshold: f32) -> Vec<SearchResult>`.  
     *Reality*: Backend exports `search_clip_semantic(query: String, limit: usize) -> Result<Vec<SearchResult>, String>`. Command name and parameter types differ from specification.
  3. `PROJECT.md` specifies `sync_xmp_sidecar(image_path: String, metadata: XmpMetadata) -> Result<(), String>`.  
     *Reality*: Backend exports `write_xmp_sidecar(path: String, rating: u8, color_label: String, flag_status: String, tags: Vec<String>, history_entry: Option<String>) -> Result<(), String>`.
- **Tag**: **CONTRACT VIOLATION**

---

### 🟠 Major Finding 3: PERFORMANCE / QUALITY — Non-Zero-Copy Asset Protocol (`lib.rs`)

- **What**: The custom `tauri://` and `asset://` scheme protocol handler is documented as a "zero-copy custom asset protocol", but actually performs full memory allocation and file copies into heap buffers on every image request.
- **Where**: `src-tauri/src/lib.rs` (lines 70–120).
- **Verbatim Evidence**:
  ```rust
  pub fn handle_asset_custom_protocol(
      request: tauri::http::Request<Vec<u8>>,
  ) -> tauri::http::Response<std::borrow::Cow<'static, [u8]>> {
      ...
      if file_path.exists() && file_path.is_file() {
          if let Ok(bytes) = std::fs::read(file_path) {
              return tauri::http::Response::builder()
                  .status(200)
                  .header("Content-Type", mime)
                  .header("Access-Control-Allow-Origin", "*")
                  .body(std::borrow::Cow::Owned(bytes))
                  ...
  ```
- **Why**: `std::fs::read` allocates memory and reads the entire file into a `Vec<u8>`. `Cow::Owned(bytes)` transfers ownership of this allocated vector. This is **not zero-copy** file streaming. For multi-megabyte photo files or RAW files, this creates heavy memory churn and GC pressure on high-resolution image scrolls.
- **Tag**: **QUALITY / ARCHITECTURE**

---

### 🟡 Minor Finding 4: POTENTIAL BUG — Percent Decoding for Non-ASCII Paths (`lib.rs`)

- **What**: Custom percent-decoder `decode_percent` in `lib.rs` converts hex bytes directly into `char` primitives without assembling multi-byte UTF-8 sequences.
- **Where**: `src-tauri/src/lib.rs` (lines 122–144).
- **Verbatim Evidence**:
  ```rust
  if let Ok(val) = u8::from_str_radix(hex_str, 16) {
      result.push(val as char);
      continue;
  }
  ```
- **Why**: Casting a single byte `u8` to `char` (e.g. `0xD1 as char`) yields `U+00D1` (Latin capital Ñ) rather than combining UTF-8 byte pairs (like `%D1%85` for Cyrillic 'х'). This causes file lookup errors for images whose path contains Cyrillic or non-ASCII characters when requested via custom asset URLs.
- **Tag**: **CORRECTNESS**

---

## 3. Verified Claims

| Claim | Method | Outcome |
|---|---|---|
| Cargo test suite passes | Executed `cargo test` in `src-tauri/` | **PASS** (26 unit tests + 5 integration tests pass) |
| NPM test suite passes | Executed `npm test` in root directory | **PASS** (30 JS tests pass) |
| Tauri Updater plugin configured | Inspected `Cargo.toml` (line 21), `tauri.conf.json` (lines 45-52), `lib.rs` (line 171) | **PASS** (Plugin registered and endpoints configured) |
| XMP XML parsing and sidecar generation | Tested via `xmp::tests` and inspected `xmp.rs` | **PASS** (Valid XML generation and roxmltree parsing) |
| Geotagged photo extraction | Tested via `metadata::tests` and inspected `metadata.rs` | **PASS** (GPS coordinates extracted to GeoPhoto struct) |

---

## 4. Logical Chain

1. **Observation 1**: `onnx.rs` downloads `yolov8n.onnx` and uses keyword string matching (`match token.as_str()`) and `path_str.contains(...)` inside `extract_text_embedding` and `extract_image_embedding`. No CLIP model (text or image transformer) exists in the project.
2. **Logic Step 1**: The implementation claims to deliver "Smart Albums CLIP semantic search", but bypasses neural multi-modal embeddings using hardcoded string lookup tables. This fits the definition of a facade implementation.
3. **Observation 2**: `PROJECT.md` specifies strict signatures for `get_image_url`, `search_clip`, and `sync_xmp_sidecar`.
4. **Logic Step 2**: `get_image_url` is absent from Rust IPC handlers, while `search_clip` and `sync_xmp_sidecar` use different function names and signatures. Interface contracts are not met.
5. **Observation 3**: `lib.rs` uses `std::fs::read(file_path)` and `Cow::Owned(bytes)` in `handle_asset_custom_protocol`.
6. **Logic Step 3**: Buffer allocation occurs on every asset load; therefore, claims of "zero-copy custom asset protocol" are technically inaccurate.
7. **Conclusion**: Per mandatory reviewer guidelines on integrity violations and contract verification, the verdict MUST be **VETO / REQUEST_CHANGES**.

---

## 5. Caveats

- **No Caveats**: Full backend source code (`src-tauri/src/`), configuration files (`Cargo.toml`, `tauri.conf.json`), test suites (`cargo test`, `npm test`), and project contracts (`PROJECT.md`) were exhaustively inspected and independently executed.

---

## 6. Conclusion & Required Actionable Changes

### Required Changes:
1. **Remediate CLIP Semantic Search (Integrity Violation)**:
   - Integrate a real ONNX CLIP text & vision model (e.g. `clip-vit-base-patch32` text encoder + image encoder ONNX files), or refactor the specification and interface if CLIP model runtime is not supported, removing misleading facade claims.
2. **Align IPC Protocol Signatures with `PROJECT.md`**:
   - Implement `get_image_url(path: String) -> String` IPC handler returning `tauri://localhost/<path>`.
   - Update Rust search command to match `search_clip(query: String, threshold: f32) -> Vec<SearchResult>` or update contract document atomically across JS & Rust.
   - Align `sync_xmp_sidecar` signature with `PROJECT.md`.
3. **Fix Protocol Path Decoding**:
   - Use `percent_encoding` crate or proper UTF-8 percent-decoding in `lib.rs` instead of single-byte `u8 as char` casting.
4. **Optimize Asset Protocol Memory Usage**:
   - Implement true streaming or memory-mapped response buffers (`memmap2`) for local file assets if zero-copy behavior is required.

---

## 7. Independent Verification Method

To verify these findings independently:

1. **Verify Cargo & NPM test execution**:
   ```powershell
   cd src-tauri
   cargo test
   cd ..
   npm test
   ```
2. **Inspect Facade CLIP Implementation**:
   - Open `src-tauri/src/onnx.rs` and inspect lines 397–560. Observe `match token.as_str()` and `path_str.contains(...)`.
3. **Inspect Missing `get_image_url` IPC Handler**:
   - Open `src-tauri/src/lib.rs` and search for `get_image_url` in `tauri::generate_handler![]`.
