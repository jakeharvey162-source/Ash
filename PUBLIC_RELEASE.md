# Ash public desktop release playbook

## Goal

Ship one obvious Windows download that a non-developer can install, link to an Ash account and keep updated without touching Python, Git or environment files.

## Release gate

Do not publish a tag until these workflows are green on the commit being released:

- Ash Quality
- Windows Desktop Release
- Ash Pro Acceptance
- Builder Acceptance
- OpenJarvis Integration when OpenJarvis code changed
- Ash Voice Live when voice code changed
- Ash Computer Control Live when computer-control code changed

A live-provider outage may block a provider-specific acceptance job. Treat that as a release blocker for the affected cloud feature unless the product has a verified fallback and the release notes disclose the limitation.

## Publish

1. Open GitHub -> Actions -> **Publish Desktop Release**.
2. Click **Run workflow**.
3. Enter a semantic version such as `0.3.0`.
4. The workflow creates tag `v0.3.0`.
5. The tag triggers **Windows Desktop Release**.
6. That workflow builds and smoke-tests:
   - `Ash.exe`
   - `AshWorker.exe`
   - `AshVoice.exe`
7. It creates the installer, portable ZIP and SHA-256 checksums.
8. If every packaging step passes, GitHub Release is published automatically.

Public users should normally download:

- `AshDesktopSetup.exe`

Advanced users can choose:

- `AshDesktop-portable.zip`

## Public download link

The Ash web landing page links to:

https://github.com/jakeharvey162-source/Ash/releases

After the first release exists, the stable installer asset can also be linked directly through GitHub's latest-release route:

https://github.com/jakeharvey162-source/Ash/releases/latest/download/AshDesktopSetup.exe

## Trust and security

Before a larger public launch:

- buy a Windows code-signing certificate and sign `Ash.exe`, `AshWorker.exe`, `AshVoice.exe` and the installer
- publish SHA-256 checksums
- keep provider secrets only in server-side secrets
- publish a privacy policy and terms
- document what screenshots/audio are processed and when
- keep local writes, CodeAct and protected computer-control actions confirmation-gated
- add crash reporting only as an explicit opt-in
- never silently enable startup, microphone, screen capture or computer control

## Rollout

Recommended rollout order:

1. 10 trusted alpha users
2. 50-user closed beta
3. public free tier
4. paid Pro tier
5. teams after billing, support and usage controls are stable

Track install success, first-run pairing success, wake-word success, task success, crash-free sessions, cloud cost per active user and paid conversion.
