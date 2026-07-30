# BRIEFING — 2026-07-30T15:07:24Z

## Mission
Fix race condition / silent failure when reading existing XMP sidecars in `src-tauri/src/commands/xmp.rs` and verify tests.

## 🔒 My Identity
- Archetype: XMP Race Fix Worker
- Roles: implementer, qa, specialist
- Working directory: c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_fix_xmp_race
- Original parent: 6febf72a-3d9d-468c-b35c-8f0858272366
- Milestone: Fix XMP Sidecar Read Race Condition

## 🔒 Key Constraints
- Retry up to 10 times with exponential backoff (starting at 2ms) if `fs::read_to_string(path)` returns transient errors or empty string when file size > 0.
- In `write_xmp_sidecar`, if `xmp_path.exists()`, error out with `Err(format!("Failed to read existing sidecar: {}", e))` instead of swallowing error.
- Verify `cargo test --manifest-path src-tauri/Cargo.toml --test xmp_roundtrip_stress`, `cargo check`, `cargo clippy`, and full `cargo test`.
- Document work in handoff.md.

## Current Parent
- Conversation ID: 6febf72a-3d9d-468c-b35c-8f0858272366
- Updated: 2026-07-30T15:07:24Z

## Task Summary
- **What to build**: Fix XMP read retry logic and handle read failures gracefully in `write_xmp_sidecar`.
- **Success criteria**: 100% pass on stress tests, cargo check clean, clippy clean, cargo test clean.

## Change Tracker
- **Files modified**: None yet
- **Build status**: Pending
- **Pending issues**: None

## Quality Status
- **Build/test result**: Pending
- **Lint status**: Pending
- **Tests added/modified**: Pending

## Loaded Skills
- None

## Key Decisions Made
- Initializing task files and investigating xmp.rs.

## Artifact Index
- `.agents/worker_fix_xmp_race/ORIGINAL_REQUEST.md` — Original prompt request
- `.agents/worker_fix_xmp_race/BRIEFING.md` — Agent briefing index
- `.agents/worker_fix_xmp_race/progress.md` — Execution progress log
