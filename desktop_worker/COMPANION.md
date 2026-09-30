# Ash Hologram Desktop Companion

The desktop companion is Ash's persistent on-screen presence: a transparent, always-on-top humanoid hologram tied to the actual Ash runtime rather than a decorative animation.

## Windows install

Run:

```bat
desktop_worker\install_hologram_companion.bat
```

The installer creates an isolated environment, installs the Ash desktop core and the integrated OpenJarvis specialist, offers always-on voice and screen-control dependencies, creates a Desktop launcher, and adds Ash to Windows Startup.

After install, Ash can appear automatically when the user signs in to Windows.

## Hologram states

The avatar reacts to real runtime events:

- cyan: ready
- green: listening / wake word
- amber: thinking
- cyan pulse: speaking
- green: building
- purple: acting or local/offline intelligence
- red: runtime attention/error

The hologram has a projected base, floating particles, scanlines, blinking face, speaking mouth animation, chest core, state halo, compact mode and saved screen position.

## Controls

- **Ctrl + Alt + A** — summon the Ash hologram on Windows
- drag — move Ash
- double-click — open the full Ash command center
- middle-click or Esc — compact / expand
- right-click — restart voice/worker, hide temporarily, or quit

Set `ASH_COMPANION_VOICE=0` to run the visual companion without local voice.

## Intelligence behind the companion

The buddy starts both Ash's paired desktop worker and the local voice runtime. General desktop missions can use Ash's bounded tool runtime, private memory, live research, local schedules, adaptive model routing and the integrated OpenJarvis specialist when installed.

The companion does not bypass safety gates. Workspace writes, memory persistence and local schedule mutations are confirmation-gated. Computer-control actions remain isolated behind Ash's existing permissioned controller and protected-action rules.
