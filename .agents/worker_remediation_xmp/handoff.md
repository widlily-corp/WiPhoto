# Handoff Report: XMP Sidecar History Truncation Defect Remediation

## 1. Observation

### Defect Analysis
In `src-tauri/src/commands/xmp.rs` (lines 129–142), `write_xmp_sidecar` originally called `fs::exists(&xmp_path)` and `read_to_string_with_retry(&xmp_path)` followed by `parse_xmp_content(&content)`.
During rapid sequential update stress testing (`test_xmp_1000_sequential_roundtrip_updates` in `tests/xmp_roundtrip_stress.rs`), the test failed with:
```text
assertion `left == right` failed: History length mismatch at iteration 54
  left: 1
 right: 54
```
Further testing also revealed microsecond file unlinking window during atomic rename (`fs::rename`) on Windows NTFS filesystem where `path.exists()` transiently returns `false` or file reads return partial/incomplete XML before file flush completes.

### Implemented Fix
1. Modified `src-tauri/src/commands/xmp.rs` to replace separate `read_to_string_with_retry` and un-retried `parse_xmp_content` with a robust unified `read_and_parse_xmp_with_retry(path: &Path) -> Result<Option<XmpData>, String>`.
2. `read_and_parse_xmp_with_retry` retries both file reading AND XMP parsing up to 25 times with exponential backoff (2ms initial delay up to 50ms cap).
3. Added `not_found_count` verification (requiring 3 consecutive `NotFound` / `!path.exists()` results) so transient NTFS file unlinking during atomic file renames does not return `Ok(None)` falsely or cause history reset.
4. Updated `write_xmp_sidecar` to use `read_and_parse_xmp_with_retry(&xmp_path)?`. If reading/parsing an existing sidecar returns an error, the operation propagates the error safely via `?` instead of initializing `history` to `Vec::new()` and destroying existing history.
5. Added unit test `test_write_xmp_sidecar_retries_and_preserves_history` in `src-tauri/src/commands/xmp.rs`.

---

## 2. Logic Chain

1. **Root Cause**: During rapid sequential XMP sidecar updates, `write_file_with_sync` writes a `.tmp_...` file and renames it over the target path (`fs::rename`). On Windows NTFS, during `fs::rename`, there is a transient window where `path.exists()` or `fs::read_to_string` returns `NotFound` or partial/un-flushed XML content.
2. **Failure Sequence in Original Code**:
   - `write_xmp_sidecar` checked `if xmp_path.exists()`. If `read_to_string_with_retry` returned partial XML, `parse_xmp_content` returned `None`.
   - `history` defaulted to `Vec::new()`.
   - `history.push(entry)` added only 1 entry.
   - The file was written, silently erasing all previous history entries.
3. **Remediation Strategy**:
   - Retrying `parse_xmp_content` alongside `fs::read_to_string` ensures that partial XML reads during concurrent writes are retried until the full XML payload is readable and parsed.
   - Retrying `!path.exists()` checks 3 times prevents transient `NotFound` during atomic rename from triggering false `Ok(None)` returns.
   - Propagating parse errors via `?` ensures that if an existing sidecar is corrupt or unreadable, `write_xmp_sidecar` aborts without overwriting disk state or truncating history.

---

## 3. Caveats
- Windows file locking: High-concurrency operations on Windows filesystems may experience brief lock delays; the retry loop's exponential backoff (2ms–50ms, max 25 retries) accommodates up to ~1.2s of total lock delay.
- No other caveats.

---

## 4. Conclusion
The XMP sidecar history truncation defect is fully remediated. History entries are strictly preserved across 1,000 sequential roundtrip updates without data loss, history length mismatch, or transient parse failure.

---

## 5. Verification Method

To independently verify the fix:

1. **Stress Test Verification**:
   ```bash
   cargo test --manifest-path src-tauri/Cargo.toml --test xmp_roundtrip_stress
   ```
   *Expected Result*: 3 tests passed (`test_xmp_special_characters_and_unicode_escaping`, `test_xmp_large_payload_and_malformed_xml_handling`, and `test_xmp_1000_sequential_roundtrip_updates`) with 0 failures.

2. **Full Test Suite Verification**:
   ```bash
   cargo test --manifest-path src-tauri/Cargo.toml
   ```
   *Expected Result*: All 33 unit tests, 4 backend stress tests, 5 e2e tests, and 3 stress tests pass 100%.

3. **Clippy Linter Verification**:
   ```bash
   cargo clippy --manifest-path src-tauri/Cargo.toml -- -D warnings
   ```
   *Expected Result*: Clean compilation with 0 warnings.
