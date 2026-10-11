# Ash Builder: quality evidence and feedback

This release adds an **automated source and build report** to new desktop-generated sites, visible in the Ash Builder job history. It is deliberately **not** an AI-generated five-star score or fabricated customer feedback.

How it works:

1. Ash builds the website as before using the user's chosen design direction.
2. The desktop worker reads only small frontend source files within the generated workspace. It ignores symlinks, dependency folders, compiled output, large files, and does not execute code.
3. It records six static signals: responsive-layout syntax, focus styling, reduced-motion support, semantic landmarks, interaction-handler presence, and absence of common placeholder copy.
4. It retains the true result of the actual npm build, whether the renderer degraded to a fallback, and what remains untested.
5. The Builder queue displays the verified build result, static check count, and up to three specific suggestions.

The report always marks **browser_tested=false**, **mobile_visual_tested=false**, **user_feedback_collected=false**, and **production_ready=false** until some independently verified acceptance process makes these statuses meaningful. A CSS class that looks responsive does not prove visual usability.

The latest feature is available in source control; previously queued jobs do not automatically receive new reports. The user's desktop worker must be updated to a version with this change and must be connected to their account.

## Recommended review loop

Build a fictional demo of each design preset. For each generated project, review the report, test at mobile/desktop widths, verify navigation/forms, capture screenshots, fix failing interactions, and collect feedback from an actual user. Record real issues rather than claiming broad end-user approval based solely on passing CI.

## Repos and plug-ins

Ash uses its existing OpenJarvis, GitHub metadata, USGS, Wazuh and imported security reports as separately bounded capabilities. A catalog entry, GitHub metadata lookup, or static source inspection is **not** proof that God's Eye View, ShadowBroker, Strix, Magic UI, or other standalone services are installed and operational.

This quality report adds no external data collection, credentials, model APIs, or browser execution.

## Browser accessibility regression (CI only)

Ash's real Builder acceptance workflow installs the maintained [Deque axe-core](https://github.com/dequelabs/axe-core) engine through [@axe-core/playwright](https://www.npmjs.com/package/@axe-core/playwright) **4.13.0**. The generated website is opened in Chromium at desktop and mobile sizes, and the automated WCAG A/AA checks are recorded in `builder-visual-acceptance.json`. Severe or critical rule violations fail this browser test; non-blocking rule observations remain in the report.

This is a genuine third-party automated accessibility integration in the CI test environment, **not an installed plugin in the Ash web app**. It tests only machine-detectable issues. Keyboard, screen-reader, content meaning, human visual quality and full functionality still require separate testing. The axe engine and integration are MPL-2.0; review the upstream project and bundled third-party license terms when redistributing binaries.

CI setup is isolated from customers' generated project dependencies:

```sh
npm install --no-save playwright @axe-core/playwright@4.13.0
node scripts/builder-visual-acceptance.mjs
```

The command expects the prebuilt sample website in `builder-acceptance-output/` and installed Chromium. The workflow creates those prerequisites automatically.
