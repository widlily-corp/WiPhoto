## 2026-07-30T14:29:29Z
You are explorer_stability (teamwork_preview_explorer).
Your working directory is: c:\Users\Widlily\Documents\projects\wiphoto\.agents\explorer_stability
Project root: c:\Users\Widlily\Documents\projects\wiphoto
Project spec: c:\Users\Widlily\Documents\projects\wiphoto\.agents\orchestrator_v3\PROJECT.md

Task:
1. Create your working directory `.agents/explorer_stability` if needed, along with `BRIEFING.md` and `progress.md`.
2. Inspect both frontend JS and backend Rust for stability risks, race conditions, silent errors, unhandled promise rejections, panics, or memory issues.
3. Check app startup flow, folder scanning initialization, image loading flows, IPC message passing between JS and Tauri backend.
4. Identify any unhandled error paths (e.g., missing error handlers in Tauri commands, unhandled fetch/tauri invoke rejections, invalid file paths, missing image EXIF/XMP).
5. Deliver a handoff report `c:\Users\Widlily\Documents\projects\wiphoto\.agents\explorer_stability\handoff.md` detailing:
   - All identified bugs, silent errors, race conditions, or panic risks
   - Specific locations in frontend and backend
   - Recommended fixes for error handling and stability.
6. Send a message to parent with the summary and report location.
