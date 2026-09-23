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
