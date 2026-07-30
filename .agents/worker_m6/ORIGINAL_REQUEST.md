## 2026-07-30T08:59:55Z
<USER_REQUEST>
You are the Implementation Worker for Milestone 6: OTA Updates (R6).
Working directory: `c:\Users\Widlily\Documents\projects\wiphoto`
Metadata directory: `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_m6`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Task:
1. Integrate built-in OTA update mechanism using `tauri-plugin-updater` (R6).
2. Add `tauri-plugin-updater` dependency to `src-tauri/Cargo.toml`.
3. Register updater plugin in `src-tauri/src/lib.rs` builder (`.plugin(tauri_plugin_updater::Builder::new().build())`).
4. Configure updater plugin in `src-tauri/tauri.conf.json` under `plugins.updater`.
5. Implement `src/js/updater.js` / API wrapper calling Tauri updater plugin to check for updates against GitHub Releases.
6. Create modal UI in `index.html` / `src/js/updater.js` that displays Release Notes rendered from Markdown with "Update Now" ("Обновить сейчас") and "Postpone" ("Отложить") buttons.
7. Add unit/integration tests in JS (`tier1_tier2_features.test.cjs`) and Rust (`e2e_v500_tests.rs`).
8. Verify `cargo check`, `cargo test`, and `npm test` pass.
9. Make atomic conventional commit: `feat(updater): integrate tauri-plugin-updater with markdown release notes modal`.
10. Write handoff report to `c:\Users\Widlily\Documents\projects\wiphoto\.agents\worker_m6\handoff.md` and notify parent.
</USER_REQUEST>
