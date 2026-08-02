# Investigation Handoff Report: GitHub Actions CI/CD & Tauri OTA Update Mechanism

## 1. Observation

### A. CI/CD Workflow (`.github/workflows/ci.yml`)
- **Branch Triggers (Lines 5, 9)**:
  ```yaml
  branches: [ main, beta-rust+tuari ]
  ```
  The branch name contains a typo: `beta-rust+tuari` instead of `beta-rust+tauri`.
- **Platform Matrix (Lines 18, 67)**:
  - `test` job: `platform: [ubuntu-latest, windows-latest]`
  - `build` job: `platform: [ubuntu-22.04, windows-latest]`
  - `macos-latest` (or `macos-14`/`macos-13`) is completely omitted from both `test` and `build` matrices.
- **Job Dependency & Bottlenecks (Lines 60-63)**:
  - `build` job includes `needs: test`.
  - Sequential execution blocks build jobs from starting until test jobs finish across all platforms.
  - Setup steps (`actions/checkout@v4`, `actions/setup-node@v4`, `Swatinem/rust-cache@v2`, Linux system `apt-get` deps, `npm ci`) are executed 4 separate times.
- **Missing Node.js Cache in Build Job (Line 73-76)**:
  ```yaml
  - name: Setup Node.js
    uses: actions/setup-node@v4
    with:
      node-version: 22
  ```
  `cache: 'npm'` is missing in `build` job (present in `test` job line 27). `npm ci` downloads all NPM dependencies over the network from scratch.
- **Silent Lint Failures (Line 50)**:
  ```yaml
  npx eslint src/ || true
  ```
  ESLint failure exit code is suppressed via `|| true`.
- **Missing OTA Release Signing Environment Variables (Lines 95-103)**:
  ```yaml
  - name: Build Tauri App
    uses: tauri-apps/tauri-action@v0
    env:
      GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    with:
      tagName: v__VERSION__
      releaseName: 'WiPhoto v__VERSION__'
      releaseBody: 'WiPhoto v__VERSION__ release.'
      releaseDraft: true
      prerelease: false
  ```
  `TAURI_SIGNING_PRIVATE_KEY` and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` are absent from `env`. Without `TAURI_SIGNING_PRIVATE_KEY`, `tauri-action` cannot generate `.sig` signature files or `latest.json` updater metadata manifest.
- **Draft Releases (Line 102)**:
  `releaseDraft: true` creates draft releases on GitHub Releases, which do not expose public release download assets at `https://github.com/widlily/wiphoto/releases/latest/download/latest.json`.

### B. Tauri OTA Configuration (`src-tauri/tauri.conf.json`)
- **Plugin Configuration (Lines 48-53)**:
  ```json
  "plugins": {
    "updater": {
      "endpoints": [
        "https://github.com/widlily/wiphoto/releases/latest/download/latest.json"
      ],
      "pubkey": "dW50cnVzdGVkIGNvbW1lbnQ6IGF1dGhlbnRpY2F0aW9uIGtleQpSV1N5SnAxdWhEUmJidmlSdWdERFFxNWhzRzlDZmlydUc2OFEvaS80MmhrS04ydWRaUG5nOTU5aQo="
    }
  }
  ```
  - `endpoints`: Points to GitHub Releases `latest.json`.
  - `pubkey`: Contains a valid Minisign public key string (`untrusted comment: authentication key\nRWSyJp1uhDRbbviRugDDQq5hsG9CfiruG68Q/i/42hkKN2udZPng959i`).
- **Bundle Settings (Lines 33-46)**:
  ```json
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": [...]
  }
  ```
  `bundle.createUpdaterArtifacts` is omitted. In Tauri v2, explicitly configuring `"createUpdaterArtifacts": true` (or `"v1Compatible"`) ensures that `tauri build` generates update archives (`.nsis.zip` on Windows, `.app.tar.gz` on macOS, `.AppImage.tar.gz` on Linux) and signature files.

### C. Backend Dependencies & Registration (`src-tauri/Cargo.toml` & `src-tauri/src/lib.rs`)
- `src-tauri/Cargo.toml` (Line 21): `tauri-plugin-updater = "2"` is listed as a dependency.
- `src-tauri/src/lib.rs` (Line 176): `.plugin(tauri_plugin_updater::Builder::new().build())` is registered in `run()`.
- **Missing Process Plugin (`Cargo.toml:16-21` & `lib.rs:172-176`)**:
  `tauri-plugin-process` is missing from `Cargo.toml` and is not registered in `lib.rs`.

### D. Frontend OTA Implementation (`src/js/updater.js`)
- **IPC & Check Logic (Lines 123-142)**:
  `window.__TAURI__.updater.check()` and `plugin:updater|check` are queried properly.
- **Markdown Release Notes Parsing (Lines 30-99)**:
  Escapes HTML input (`&`, `<`, `>`), formats code blocks, headers (`#`, `##`, `###`), bold (`**`), italics (`*`), bullet lists (`-`, `*`), and paragraphs.
- **Relaunch Mechanism (Lines 245-250)**:
  ```javascript
  if (window.__TAURI__?.process?.relaunch) {
    window.__TAURI__.process.relaunch();
  } else {
    hideUpdateModal();
  }
  ```
  Because `tauri-plugin-process` is not included in `Cargo.toml` or registered in `lib.rs`, `window.__TAURI__?.process?.relaunch` evaluates to `undefined`, causing app restart to fall back silently to closing the update modal.

---

## 2. Logic Chain

1. **Multi-Platform CI Failure**:
   - *Observation*: `ci.yml` matrix includes only `ubuntu-22.04` and `windows-latest`.
   - *Deduction*: macOS artifacts (`.dmg`, `.app.tar.gz`) are never compiled or tested, leaving macOS users without builds or updates. Adding `macos-latest` to the runner matrix will build macOS targets.

2. **CI Pipeline Speed Bottlenecks**:
   - *Observation*: `build` job requires `test` job to complete (`needs: test`), duplicates setup actions, and lacks `cache: 'npm'` on line 76.
   - *Deduction*: Running test and build steps with duplicated setups doubles pipeline execution time. Removing unnecessary sequential dependencies or sharing caching strategies (`cache: 'npm'`, `Swatinem/rust-cache@v2`) speeds up multi-platform builds significantly.

3. **OTA Release Signing Breakdown**:
   - *Observation*: `tauri-action` in `ci.yml:95-103` lacks `TAURI_SIGNING_PRIVATE_KEY` in `env`, and `releaseDraft` is `true`.
   - *Deduction*: Tauri v2 updater requires valid Minisign signature files (`.sig`) matching `pubkey` in `tauri.conf.json` and a published `latest.json` manifest. Without `TAURI_SIGNING_PRIVATE_KEY`, `tauri-action` cannot produce signatures or publish `latest.json` to GitHub Releases, causing `window.__TAURI__.updater.check()` to fail with HTTP 404 or missing signatures.

4. **Missing Updater Artifact Generation**:
   - *Observation*: `tauri.conf.json` has `"targets": "all"` but omits `"createUpdaterArtifacts"`.
   - *Deduction*: Adding `"createUpdaterArtifacts": true` to `"bundle"` in `tauri.conf.json` ensures that `tauri build` produces compressed installer archives (`.nsis.zip`, `.app.tar.gz`, `.AppImage.tar.gz`) alongside installers.

5. **Post-Update Relaunch Failure**:
   - *Observation*: `updater.js:245-250` checks for `window.__TAURI__?.process?.relaunch()`, but `tauri-plugin-process` is missing from `Cargo.toml` and `lib.rs`.
   - *Deduction*: Without `tauri-plugin-process`, installed updates cannot automatically restart the application, forcing users to manually restart.

---

## 3. Caveats

- **No Source Code Changes**: This report is produced under a read-only investigation constraint. Source files were analyzed without modifications.
- **GitHub Secrets Environment**: Secret values (`TAURI_SIGNING_PRIVATE_KEY` and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`) must be added to repository settings in GitHub by the project maintainer.
- **macOS Build Hardware**: `macos-latest` on GitHub Actions runs on Apple Silicon (`aarch64`). If `x86_64` macOS targets are required, cross-compilation target toolchains or secondary matrix jobs may be needed.

---

## 4. Conclusion

The build pipeline and OTA update mechanism in WiPhoto have a solid foundation but require key fixes:
1. **CI/CD Optimization**:
   - Fix branch trigger typo `beta-rust+tuari` -> `beta-rust+tauri`.
   - Add `macos-latest` to workflow matrix (`test` and `build` jobs).
   - Add `cache: 'npm'` to Node.js setup in `build` job.
   - Remove `|| true` from `npx eslint src/` so linter errors fail the workflow properly.
   - Add `TAURI_SIGNING_PRIVATE_KEY` and `TAURI_SIGNING_PRIVATE_KEY_PASSWORD` to `tauri-action` env in `ci.yml`.
   - Set `releaseDraft: false` or implement automated publishing for release tags.
2. **Tauri OTA Configuration**:
   - Add `"createUpdaterArtifacts": true` in `src-tauri/tauri.conf.json` under `"bundle"`.
3. **Application Relaunch**:
   - Add `tauri-plugin-process = "2"` to `Cargo.toml` and register `.plugin(tauri_plugin_process::init())` in `src-tauri/src/lib.rs` to support automatic relaunch after update.

---

## 5. Verification Method

To verify these findings independently:

1. **Inspect Workflow Files**:
   - View `.github/workflows/ci.yml` lines 5, 18, 50, 67, 76, 96-102.
2. **Inspect Tauri Config & Cargo Dependencies**:
   - View `src-tauri/tauri.conf.json` lines 33-54 and `src-tauri/Cargo.toml` lines 15-22.
   - View `src-tauri/src/lib.rs` lines 170-177.
3. **Inspect Frontend Updater Implementation**:
   - View `src/js/updater.js` lines 118-178 and 223-272.
4. **Run Project Test Command**:
   - Execute `npm test` from project root to verify node test suite passing status:
     ```powershell
     npm test
     ```
   - Execute `cargo test --manifest-path src-tauri/Cargo.toml` to verify Rust tests.
