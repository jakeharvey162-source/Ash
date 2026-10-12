"""Import a public GitHub repository to an Ash-owned workspace for later review.

Cloning source is not permission to execute its code, install its packages, use
secrets, or push changes to a remote repository.
"""
from __future__ import annotations
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
from typing import Callable

URL = re.compile(r"^https://github\.com/([A-Za-z0-9][A-Za-z0-9-]{0,38})/([A-Za-z0-9._-]{1,100})(?:\.git)?/?$", re.I)


def parse_public_repo(url: str) -> tuple[str, str]:
    text = str(url or "").strip()
    if len(text) > 230 or "?" in text or "#" in text or "@" in text or "\\" in text:
        raise ValueError("Provide a public github.com owner/repository HTTPS URL.")
    match = URL.fullmatch(text)
    if not match:
        raise ValueError("Only public github.com HTTPS repository URLs are supported.")
    owner, name = match.groups()
    name = name.removesuffix(".git")
    if name in (".", "..") or ".." in name:
        raise ValueError("Invalid repository name.")
    return owner, name


def import_public_repo(url: str, workspace_root, *, runner: Callable | None = None) -> dict:
    owner, name = parse_public_repo(url)
    base = pathlib.Path(workspace_root).resolve()
    base.mkdir(parents=True, exist_ok=True)
    dest_folder = base / "repositories"
    if dest_folder.exists() and (dest_folder.is_symlink() or not dest_folder.is_dir()):
        raise ValueError("Repository destination is not a safe folder.")
    dest_folder.mkdir(exist_ok=True)
    if base not in dest_folder.resolve().parents:
        raise ValueError("Repository path must stay inside the Ash workspace.")
    dest = dest_folder / f"{owner}--{name}"
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("Repository is already present; review it before importing another copy.")
    run = runner or subprocess.run
    env = os.environ.copy()
    env.update({"GIT_TERMINAL_PROMPT":"0","GIT_CONFIG_NOSYSTEM":"1",
                "GIT_CONFIG_GLOBAL":os.devnull,"GIT_LFS_SKIP_SMUDGE":"1"})
    stage = pathlib.Path(tempfile.mkdtemp(prefix=".ash-import-",dir=dest_folder))
    try:
        def call(cmd):
            result = run(cmd, cwd=str(base), env=env, capture_output=True, text=True, timeout=75, check=False)
            if result.returncode:
                raise RuntimeError("Git import failed. Check the URL, connectivity, and repository access.")
        source = f"https://github.com/{owner}/{name}.git"
        call(["git","-c","core.hooksPath="+os.devnull,"-c","protocol.file.allow=never",
              "clone","--depth=1","--no-checkout","--no-recurse-submodules",source,str(stage)])
        call(["git","-C",str(stage),"-c","core.hooksPath="+os.devnull,"checkout","--force","HEAD"])
        count=0
        bytes_seen=0
        for current, dirs, files in os.walk(stage,followlinks=False):
            dirs[:]=[d for d in dirs if not (pathlib.Path(current)/d).is_symlink()]
            for file in files:
                p=pathlib.Path(current)/file
                if p.is_symlink():
                    raise ValueError("Repository contains a symlink; import refused.")
                count += 1
                bytes_seen += p.stat().st_size
                if count > 5000 or bytes_seen > 30_000_000:
                    raise ValueError("Repository exceeds safe import limits.")
        stage.rename(dest)
        return {"imported":True,"source":source,"local_folder":str(dest.relative_to(base)),
                "files":count,"bytes":bytes_seen,"executed_untrusted_code":False,
                "review_required":True,"pushed":False}
    finally:
        if stage.exists():
            shutil.rmtree(stage)
