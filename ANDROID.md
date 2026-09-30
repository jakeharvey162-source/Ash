# Ash on Android

Ash now has a Capacitor-based Android shell.

## What the Android app can do immediately

- sign in to the same Ash account
- use the same Supabase memory/profile/automation backend
- send commands to Ash
- create and manage automations
- receive local notifications
- use Android's share sheet
- copy to clipboard
- open approved links in the system browser
- use voice input/output where supported
- queue jobs for a linked Ash desktop

## Build

```bash
npm install
npm run build
npm run android:add
npm run android:sync
npm run android:open
```

Android Studio can then build an APK/AAB.

## Connector model

Ash has a connector registry. Built-in device connectors run through Capacitor. Cloud connectors such as Gmail, Calendar, Drive and GitHub are represented as permissioned integrations and must use OAuth or another approved authorization flow. Provider/API credentials never belong in the APK.

## Important Android limitation

A normal Android app cannot silently control every other app. Deep cross-app UI automation requires Android AccessibilityService and explicit user enablement, and distribution through Google Play is subject to Play policy. Ash should therefore use official app intents/APIs first, and reserve accessibility automation for legitimate user-directed accessibility/automation workflows with clear disclosure and consent.


## Mobile-size and UX target

Ash Android is intentionally much smaller than the Windows desktop package. The CI pipeline now rejects debug or release APK/AAB artifacts above **25 MB**.

The mobile UI uses:
- display cutout / safe-area padding
- 44–48 px minimum touch targets
- a bottom navigation bar that clears gesture/navigation insets
- 16 px form controls on phones to avoid browser/WebView zoom behavior
- dynamic viewport height for keyboards and modern Android displays
- `adjustResize` so the on-screen keyboard does not cover the composer
- HTTPS-only WebView traffic
- native Android speech recognition and the existing foreground wake service instead of bundling Whisper/CT2 into the APK

The current Android CI artifact is already far below the Windows package size; the size gate prevents future dependencies from silently making the APK bloated.
