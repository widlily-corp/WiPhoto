# Original User Request

## 2026-08-02T04:44:52Z

# Teamwork Project Prompt — Draft

> Status: Launched
> Goal: Craft prompt → get user approval → delegate to teamwork_preview

Fix the thumbnail display issue and perform a deep audit of the WiPhoto (Tauri) frontend and Rust backend to resolve any other bugs. Optimize GitHub Actions for faster OTA updates across Windows, macOS, and Linux. Verify OTA functionality and prepare the codebase for the 5.0 release on GitHub.

Working directory: c:\Users\Widlily\Documents\projects\wiphoto
Integrity mode: development

## Requirements

### R1. Fix Thumbnail Display and Deep Audit
Identify and fix the issue preventing thumbnails (ARW/JPG) from displaying correctly in the UI. Conduct a deep audit of the frontend and Rust backend to fix any other existing bugs or UI errors.

### R2. Optimize GitHub Actions for OTA
Review and rewrite the existing GitHub Actions CI/CD pipeline to be optimized and fast. It must support OTA (Over-The-Air) updates for Windows, macOS, and Linux platforms.

### R3. Verify OTA Updates Implementation
Ensure that the OTA update mechanism is correctly implemented and functional in the Tauri application code, enabling automatic updates from GitHub Releases.

### R4. Release 5.0
After all fixes and OTA optimizations are applied and verified, commit the changes, push to GitHub, and trigger the 5.0 release process.

## Acceptance Criteria

### Thumbnail Fix and Audit
- [ ] Thumbnails for both raw (ARW) and JPG formats are correctly rendered in the gallery view.
- [ ] No console errors or backend panics occur during normal navigation and image loading.
- [ ] An independent agent acting as a judge confirms the UI renders thumbnails without broken image icons or black boxes, and that the audit resolved identified bugs.

### GitHub Actions and OTA Verification
- [ ] The GitHub Actions workflow file (`.github/workflows/ci.yml` or similar) builds for Windows, macOS, and Linux concurrently and is optimized for speed.
- [ ] The Tauri configuration is properly set up for OTA updates using GitHub Releases as the endpoints.
- [ ] An independent agent acting as a judge confirms the GitHub Actions pipeline is valid, fast, and that the OTA update logic in the application is correctly implemented.
