"""Deterministic local companion gestures; never ask an LLM to hide the UI."""
import re
import platform
import subprocess
import webbrowser


def launch_command(text):
    match = re.fullmatch(r"(?:please )?(?:open|launch|start) (calculator|notepad|file explorer|browser)(?: please)?[.!?]?", str(text).strip(), re.I)
    if not match:
        return None
    app = match.group(1).lower()
    if app == "browser":
        if not webbrowser.open("about:blank"):
            raise RuntimeError("The default browser could not be opened")
    else:
        commands = {"Windows": {"calculator": ["calc.exe"], "notepad": ["notepad.exe"], "file explorer": ["explorer.exe"]},
                    "Darwin": {"calculator": ["open", "-a", "Calculator"], "notepad": ["open", "-a", "TextEdit"], "file explorer": ["open", "."]},
                    "Linux": {"calculator": ["gnome-calculator"], "notepad": ["gedit"], "file explorer": ["xdg-open", "."]}}
        command = commands.get(platform.system(), {}).get(app)
        if not command:
            raise RuntimeError("App launch is unavailable on this platform")
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"Launched {app}."


def presence_command(text):
    clean = re.sub(r"[^a-z ]", "", str(text).lower()).strip()
    clean = re.sub(r"^(hey )?(ash|arise)\s+", "", clean)
    if clean in {"get out", "go away", "disappear", "hide", "leave me alone", "take a break"}:
        return "dismiss", "Alright, portal time. Call my name when you need me."
    if clean in {"come back", "show yourself", "appear", "im back", "where are you"}:
        return "summon", "Now you need me? I'm here. Let's pick up where we left off."
    if clean in {"dance", "do a dance", "celebrate", "high five", "wave", "say hi"}:
        return "dance" if "dance" in clean or clean == "celebrate" else "wave", "You got it."
    return None
