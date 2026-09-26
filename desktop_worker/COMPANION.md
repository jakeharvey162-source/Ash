# Ash Desktop Companion

The companion is an always-on-top mini Ash that lives above other windows, inspired by the desktop-pet interaction in the supplied reference video.

## Start

From `desktop_worker`:

```bash
python companion_overlay.py
```

The companion launches Ash's existing local voice runtime in the background and reacts to its events:

- idle / ready
- wake detected
- listening
- thinking
- narration / speaking
- completion
- runtime errors

Controls:

- drag anywhere to reposition
- double-click to open the main Ash web app
- right-click for restart, temporary hide, and quit

Set `ASH_COMPANION_VOICE=0` to use the visual companion without the voice runtime.

The companion does not bypass the existing permission gates. Computer-control jobs still require Ash's paired worker, explicit local opt-in with `ASH_COMPUTER_CONTROL=1`, and confirmation rules for protected actions.
