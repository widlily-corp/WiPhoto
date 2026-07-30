# WiPhoto v5.0.0 — Test Infrastructure & Strategy Specification

## Executive Summary

This document defines the comprehensive, requirement-driven test infrastructure and strategy for **WiPhoto v5.0.0**. The strategy provides full coverage across features **R1 to R7** structured through **Tiers 1 to 4** (Feature Coverage, Boundary/Corner Cases, Cross-Feature Combinations, and Real-World E2E Scenarios).

---

## 1. Requirement Scope (R1 – R7)

| Feature | Feature Name | Description | Key Modules |
|---|---|---|---|
| **R1** | **CLIP Semantic Search** | Local vector embeddings, cosine similarity ranking, natural language image query filtering. | `onnx.rs`, `search.js`, `commandpalette.js` |
| **R2** | **XMP Sidecar Sync** | Bidirectional synchronization of rating, color labels, flag status, subject tags, and edit history to adjacent `.xmp` files. | `xmp.rs`, `tags.js`, `editor.js` |
| **R3** | **Geo-Map View (Leaflet + Supercluster)** | EXIF GPS extraction, spatial bounding box filtering, Supercluster marker aggregation, offline map rendering. | `metadata.rs`, `map.js`, `leaflet.js`, `supercluster.js` |
| **R4** | **Zero-Copy Asset Protocol** | Streaming local image files using custom `tauri://localhost/` protocol, replacing Base64 encoding for optimal performance. | `lib.rs`, `thumbnails.rs`, `utils.js` |
| **R5** | **Refined Minimal UI & Command Palette** | Linear/Stripe design aesthetic (`#08090A` dark mode, 1px hairlines, tight typography), `Ctrl+K` command palette, focus traps. | `commandpalette.js`, `variables.css`, `main.css` |
| **R6** | **OTA Updates Integration** | Application version checks, `tauri-plugin-updater` manifest evaluation, release notes modal rendering, update flow. | `updater.js`, `settings.rs`, `lib.rs` |
| **R7** | **Release Build & Verification** | Version alignment (`5.0.0`), compilation integrity, test runner verification (`npm test`, `cargo test`). | `package.json`, `Cargo.toml`, `tauri.conf.json` |

---

## 2. Four-Tier Testing Hierarchy

```
+-----------------------------------------------------------------------+
|                       TIER 4: E2E Workflows                          |
|    Complete lifecycle flows (Import -> Tag -> Search -> Edit -> Update) |
+-----------------------------------------------------------------------+
|                    TIER 3: Cross-Feature Combinations                  |
|    Interactions (CLIP + Map Bounds, Palette + XMP Sync, Zero-Copy + Map) |
+-----------------------------------------------------------------------+
|                  TIER 2: Boundary & Corner Cases                      |
|    Malformed XML, invalid GPS, empty queries, path traversal, timeouts|
+-----------------------------------------------------------------------+
|                     TIER 1: Feature Unit Coverage                     |
|    Direct unit & integration tests for R1-R7 modules (JS & Rust)      |
+-----------------------------------------------------------------------+
```

### Tier 1: Feature Coverage (Unit & Component Level)
Focuses on individual functions and modules in JS and Rust operating in isolation.
- **R1 (CLIP/Vector)**: Vector cosine similarity score calculation, embedding normalization, similarity thresholding.
- **R2 (XMP Sync)**: Parsing valid XMP XML schemas (single & double quotes), rating/label extraction, sidecar formatting.
- **R3 (Geo-Map)**: EXIF GPS coordinate extraction, marker data mapping, Supercluster spatial tree construction.
- **R4 (Zero-Copy)**: Local file path to `tauri://localhost/` protocol URL transformation.
- **R5 (UI & Palette)**: Palette trigger registration, action filtering, hairlines CSS class bindings.
- **R6 (OTA Updater)**: Semantic version parsing (`semver` comparison), release notes Markdown transformation.
- **R7 (Build & Config)**: App version string getter, config struct defaults.

### Tier 2: Boundary & Corner Cases
Focuses on resilience against unexpected inputs, missing data, and invalid states.
- **R1**: Searching with empty string queries, queries with zero matching vectors, handling NaN/null embeddings.
- **R2**: Malformed/truncated XML content, rating values outside `0-5` (e.g. 99 or negative), special character XML escaping (`&`, `<`, `>`, `"`, `'`), non-existent sidecar paths.
- **R3**: Photos with missing EXIF GPS, invalid coordinates (`lat > 90`, `lon > 180`), empty photo arrays passed to Supercluster.
- **R4**: Paths containing spaces, non-ASCII characters, path traversal sequences (`../../`), invalid protocol scheme prefixes.
- **R5**: Pressing `Escape` when palette is closed, searching with unmatched terms, rapid palette toggling.
- **R6**: Malformed release JSON manifests, network failure during update checks, version downgrades.
- **R7**: Inconsistent version strings across configuration files.

### Tier 3: Cross-Feature Combinations
Focuses on multi-module integration and state propagation.
- **R1 + R3 (CLIP + Map Spatial Filter)**: Filtering CLIP search results by Geo-Map bounding box coordinates `(min_lat, max_lat, min_lon, max_lon)`.
- **R2 + R5 (Palette + XMP Sync)**: Triggering rating/tag updates via Command Palette actions and verifying XMP sidecar persistence.
- **R4 + R3 (Zero-Copy + Geo-Map)**: Rendering photo marker popup thumbnails in Geo-Map using Zero-Copy `tauri://` asset URLs.
- **R2 + R1 (XMP Sync + Semantic Search)**: Updating photo tags via XMP sidecar sync and verifying indexed search updates.
- **R5 + R6 (Palette + OTA Updates)**: Invoking "Check for Updates" action from Command Palette to initiate update modal workflow.

### Tier 4: Real-World Scenarios & E2E Workflows
Simulates full end-to-end user journeys through the application.
- **Workflow 1: Photo Cataloging & Spatial Analysis**: User scans photo directory -> EXIF GPS coordinates extracted -> Supercluster clusters generated -> photos indexed into SQLite DB.
- **Workflow 2: Photo Metadata Editing & Sidecar Persistence**: User opens photo -> modifies rating to 5 stars and adds tags -> system generates adjacent `.xmp` file -> sidecar re-read verifies identical metadata state.
- **Workflow 3: Smart Search & Zero-Copy View**: User opens Command Palette -> enters natural language query -> results filtered by map bounding box -> selected photo displayed via `tauri://localhost/` protocol.
- **Workflow 4: Application Maintenance & Release Verification**: User initiates version check -> release manifest parsed -> release notes displayed in modal -> version 5.0.0 validated.

---

## 3. Test Matrix & Mapping

| Test File | Language | Target Tiers | Features Covered |
|---|---|---|---|
| `src/js/utils.test.cjs` | JavaScript | Tier 1 | R5, R7 |
| `src/js/r1_r7_tier1_tier2.test.cjs` | JavaScript | Tier 1, Tier 2 | R1, R2, R3, R4, R5, R6, R7 |
| `src/js/tier3_cross_features.test.cjs` | JavaScript | Tier 3 | R1+R3, R2+R5, R4+R3, R2+R1, R5+R6 |
| `src/js/tier4_e2e_scenarios.test.cjs` | JavaScript | Tier 4 | Workflows 1, 2, 3, 4 |
| `src-tauri/src/commands/xmp.rs` (cfg test) | Rust | Tier 1, Tier 2 | R2 |
| `src-tauri/src/commands/scanner.rs` (cfg test) | Rust | Tier 1, Tier 2 | R3 |
| `src-tauri/src/db.rs` (cfg test) | Rust | Tier 1, Tier 2 | R1, R3, R7 |
| `src-tauri/src/onnx.rs` (cfg test) | Rust | Tier 1, Tier 2 | R1 |
| `src-tauri/tests/e2e_v500_tests.rs` | Rust Integration | Tier 1, Tier 2, Tier 3, Tier 4 | R1, R2, R3, R4, R5, R6, R7 |

---

## 4. Test Execution & Assertion Rules

1. **AAA Pattern**: Every test must explicitly follow **Arrange**, **Act**, **Assert** structure.
2. **Zero Cheating Mandate**: No hardcoded test outputs in production source code. Tests must execute real calculations and assertions.
3. **Execution Commands**:
   - JavaScript: `npm test`
   - Rust: `cargo test --manifest-path src-tauri/Cargo.toml`
4. **Pass Criteria**: 100% pass rate across all JS and Rust test suites with 0 failures and 0 ignored tests.
