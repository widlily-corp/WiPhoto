# Handoff Report — Milestone 2: XMP Sidecar Sync (R2)

## 1. Observation
- Existing XMP read/write functions were present in `src-tauri/src/commands/xmp.rs` (`read_xmp_sidecar`, `write_xmp_sidecar`, `parse_xmp_content`).
- `src-tauri/src/commands/metadata.rs` was missing a command to update photo metadata (ratings, labels, flag status, subject tags) and sync to adjacent `.xmp` sidecars.
- `src-tauri/src/commands/editor.rs` (`save_edited`, `save_cropped_edited_image`) saved edited images but did not generate or update adjacent `.xmp` sidecars with edit operations or history entries.
- `src-tauri/src/commands/scanner.rs` checked image file modification times but did not check adjacent `.xmp` sidecar modification times, causing updated sidecars for cached photos to be skipped during folder scans.
- Implemented changes:
  1. `src-tauri/src/commands/xmp.rs`:
     - Enhanced `parse_xmp_content` to support both attribute-style (`xmp:Rating="5"`) and element-style (`<xmp:Rating>5</xmp:Rating>`) XML.
     - Preserved history vector on XMP updates to append edit entries (`xmpMM:History`).
     - Added Rust unit tests `test_parse_xmp_content_element_style` and `test_write_and_read_xmp_sidecar_creation_and_update`.
  2. `src-tauri/src/commands/metadata.rs`:
     - Added `update_photo_metadata` command to update rating, color label, flag status, and tags, syncing changes directly to the adjacent `.xmp` sidecar via `xmp::write_xmp_sidecar`.
  3. `src-tauri/src/commands/editor.rs`:
     - Added sidecar update sync in `save_edited` and `save_cropped_edited_image` to generate/update adjacent `.xmp` sidecars (`filename.ext` -> `filename.xmp`) with history entries for saved exposure, color, and crop edits.
  4. `src-tauri/src/commands/scanner.rs`:
     - Updated `scan_folder` cache freshness check to calculate `mtime = img_mtime.max(xmp_mtime)`. When adjacent `.xmp` sidecars are created or modified, the scanner detects the update, re-indexes the photo, and loads rating, color label, flag status, and tags into `ImageInfo` and SQLite database.
  5. `src-tauri/src/db.rs` & `src-tauri/src/lib.rs`:
     - Updated `db.rs` schema initialization to ensure `modified_time` and `embedding` columns exist. Registered `update_photo_metadata` in Tauri `invoke_handler`.
  6. `src/js/api.js` & `src/js/tier1_tier2_features.test.cjs`:
     - Added `updatePhotoMetadata` API wrapper function.
     - Added JS unit & integration tests covering `.xmp` sidecar path resolution and metadata sidecar sync.
- Verification command outputs:
  - `cargo check`: Passed with 0 errors (`Finished dev profile in 3.40s`).
  - `cargo test`: 26 lib unit tests + 4 e2e tests passed (`test result: ok`).
  - `npm test`: 27 node unit & integration tests passed (`pass 27, fail 0, 100% success`).
  - Atomic commit created: `45dbc9a feat(xmp): implement real-time bidirectional xmp sidecar sync`.

## 2. Logic Chain
- **Step 1**: To achieve real-time bidirectional XMP sync (R2), metadata updates (rating, label, flag, tags) and image edit saves (exposure/color/crop) must automatically write or update an adjacent `.xmp` sidecar file (`filename.ext` -> `filename.xmp`).
- **Step 2**: Wiring `metadata.rs` (`update_photo_metadata`) and `editor.rs` (`save_edited`, `save_cropped_edited_image`) to `xmp::write_xmp_sidecar` ensures that all user actions that modify ratings, labels, tags, or edits persist an XMP sidecar adjacent to the image.
- **Step 3**: Incorporating `xmp_mtime` into `scanner.rs` (`img_mtime.max(xmp_mtime)`) ensures that whenever an `.xmp` sidecar is modified on disk (by WiPhoto or external tools like Lightroom), `scan_folder` invalidates cached records and loads the sidecar's ratings, labels, tags, and history into the database and UI.
- **Step 4**: Unit tests in `xmp.rs` and `tier1_tier2_features.test.cjs` verify that sidecar creation, XML parsing (attributes and elements), and update accumulation operate without data loss.

## 3. Caveats
- No caveats.

## 4. Conclusion
- Real-time bidirectional XMP sidecar synchronization (R2) is fully implemented, verified, and committed. All Rust and JS tests pass with 100% success rate.

## 5. Verification Method
- Execute the following commands in the workspace root:
  1. `cd src-tauri && cargo check`
  2. `cd src-tauri && cargo test`
  3. `npm test`
- Inspect `src-tauri/src/commands/xmp.rs`, `metadata.rs`, `editor.rs`, `scanner.rs`, and `src/js/tier1_tier2_features.test.cjs`.
