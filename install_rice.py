#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install_rice.py — Installer for the "most-racist-rice-V2" dotfiles on CachyOS / Arch Linux.

Repository : https://github.com/Zeibytes/most-racist-rice-V2.git

What it does
  1. Clones the rice repo (or uses a local copy via --local-repo).
  2. Installs every package the configs actually need (pacman, optionally AUR).
  3. Backs up each ~/.config folder (and font files) that is about to change,
     into ~/rice-backups/backup-<timestamp>/ mirroring your home layout.
  4. Copies the rice into ~/.config and rewrites hardcoded /home/zei paths
     to your real home directory.
  5. Installs the custom waybar fonts (Waycat, Skulltype) into ~/.local/share/fonts.
  6. Optionally syncs LazyVim plugins headlessly.

Run this as your NORMAL user (not root, no sudo wrapper). sudo is used
internally only for pacman.

Usage
  python install_rice.py                     # interactive install
  python install_rice.py --dry-run           # only show what would happen
  python install_rice.py --yes               # non-interactive (core packages only)
  python install_rice.py --with-optional     # also install librewolf/flameshot
  python install_rice.py --with-aur          # also install spotify from AUR
  python install_rice.py --skip-packages     # only backup + copy dotfiles
  python install_rice.py --restore           # list available backups
  python install_rice.py --restore latest    # roll back to the newest backup
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

REPO_URL = "https://github.com/Zeibytes/most-racist-rice-V2.git"

# The rice author's home dir is hardcoded in several configs; we rewrite it.
UPSTREAM_HOME = "/home/zei"

HOME = Path.home()
CONFIG_DIR = HOME / ".config"
FONT_DIR = HOME / ".local" / "share" / "fonts"
BACKUP_ROOT = HOME / "rice-backups"

# Files with these suffixes are leftovers in the repo and should not be copied.
COPY_IGNORE_SUFFIXES = ("*.bak", "*.save")

# Packages required by the rice, grouped only for nicer display.
CORE_PACKAGE_GROUPS: dict[str, list[str]] = {
    "Compositor / session (hyprland.lua, hyprlock.conf, mango/config.conf)": [
        "hyprland",                    # includes hyprlauncher / hyprland-run / hyprshutdown
        "hyprlock",                    # hypr/hyprlock.conf
        "mangowm",                     # mango/config.conf (alternative compositor)
        "xdg-desktop-portal-hyprland", # screen sharing / screenshots portal
        "qt6-wayland",                 # dolphin renders correctly under wayland
    ],
    "Terminal / shell (kitty.conf -> shell fish)": [
        "kitty",
        "fish",
    ],
    "Launchers (fuzzel.ini, rofi/config.rasi)": [
        "fuzzel",
        "rofi-wayland",
    ],
    "Bar (waybar/config.jsonc + scripts)": [
        "waybar",
        "bc",           # catloop.sh / skull.sh math
        "wireplumber",  # waybar "wireplumber" module
        "pavucontrol",  # waybar volume on-click
    ],
    "Wallpaper / screenshots (swaybg, grim+slurp+satty binds)": [
        "swaybg",
        "grim",
        "slurp",
        "satty",
    ],
    "Media keys (pamixer / playerctl binds)": [
        "pamixer",
        "playerctl",
    ],
    "Neovim — LazyVim (nvim/) and its requirements": [
        "neovim",
        "git",
        "base-devel",   # make/gcc/etc. for mason + native builds
        "curl",
        "wget",
        "unzip",
        "gzip",
        "ripgrep",
        "fd",
        "lazygit",
        "nodejs",
        "npm",
        "python-pip",
    ],
    "System info (fastfetch/config.jsonc)": [
        "fastfetch",
    ],
    "File manager (SUPER+E)": [
        "dolphin",
    ],
    "RGB (autostart openrgb)": [
        "openrgb",
    ],
    "GTK theme / icons / fonts (gtk-3.0, gtk-4.0, configs)": [
        "breeze-gtk",               # Breeze-Dark GTK theme
        "adwaita-icon-theme",       # Adwaita icons
        "adwaita-fonts",            # "Adwaita Sans" font
        "ttf-jetbrains-mono-nerd",  # Jetbrains Mono Nerd Font (kitty/fuzzel/hyprlock/waybar)
    ],
}

# Referenced by mango binds but not essential for the rice itself.
OPTIONAL_PACKAGES = ["librewolf", "flameshot"]
# AUR-only packages referenced by the configs.
AUR_PACKAGES = ["spotify"]

# "base-devel" is a group; probe a few members to decide if it is installed.
BASE_DEVEL_PROBE = ["make", "gcc", "fakeroot"]


# --------------------------------------------------------------------------- #
# Small helpers / pretty output
# --------------------------------------------------------------------------- #

def _use_color() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


_COLOR = _use_color()


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def info(msg: str) -> None:
    print(msg)


def ok(msg: str) -> None:
    print(f"{_c('  [OK]', '1;32')} {msg}")


def warn(msg: str) -> None:
    print(f"{_c('  [!!]', '1;33')} {msg}")


def err(msg: str) -> None:
    print(f"{_c('  [ER]', '1;31')} {msg}", file=sys.stderr)


def die(msg: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    err(msg)
    sys.exit(code)


def step(title: str) -> None:
    print()
    print(_c(f"==> {title}", "1;36"))


def run(
    cmd: list[str],
    *,
    check: bool = True,
    capture: bool = False,
    show: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    """Run a command, optionally capturing output. Raises on failure if check."""
    if show:
        info(_c(f"  $ {' '.join(cmd)}", "2"))
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        timeout=timeout,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def which(name: str) -> str | None:
    return shutil.which(name)


def confirm(prompt: str, *, assume_yes: bool, default: bool = True) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(_c(prompt + suffix, "1")).strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    return answer in ("y", "yes")


# --------------------------------------------------------------------------- #
# System checks
# --------------------------------------------------------------------------- #

def is_arch_based() -> bool:
    try:
        content = Path("/etc/os-release").read_text()
    except OSError:
        return False
    ids: list[str] = []
    for line in content.splitlines():
        if line.startswith(("ID=", "ID_LIKE=")):
            ids.extend(line.split("=", 1)[1].strip('"').split())
    return bool({"arch", "cachyos", "endeavouros", "arcolinux"} & set(ids))


def installed_packages() -> set[str]:
    try:
        proc = run(["pacman", "-Qq"], capture=True, show=False, check=False)
    except FileNotFoundError:
        return set()
    if proc.returncode != 0:
        return set()
    return set(proc.stdout.split())


def package_is_installed(pkg: str, installed: set[str]) -> bool:
    if pkg in installed:
        return True
    if pkg == "base-devel":
        return all(m in installed for m in BASE_DEVEL_PROBE)
    return False


# --------------------------------------------------------------------------- #
# Package installation
# --------------------------------------------------------------------------- #

def pacman_install(pkgs: list[str], *, dry_run: bool) -> bool:
    if not pkgs:
        return True
    if dry_run:
        warn(f"DRY-RUN: would run: sudo pacman -S --needed --noconfirm {' '.join(pkgs)}")
        return True
    if not which("sudo"):
        die("'sudo' is required to install packages but was not found.")
    # Cache sudo credentials once so pacman does not prompt mid-install.
    run(["sudo", "-v"])
    cmd = ["sudo", "pacman", "-S", "--needed", "--noconfirm", *pkgs]
    proc = run(cmd, check=False)
    if proc.returncode != 0:
        warn("pacman failed — refreshing package databases and retrying once ...")
        run(["sudo", "pacman", "-Sy"], check=False)
        proc = run(cmd, check=False)
    return proc.returncode == 0


def find_aur_helper() -> str | None:
    for helper in ("paru", "yay", "pacaur"):
        path = which(helper)
        if path:
            return helper
    return None


def aur_install(helper: str, pkgs: list[str], *, dry_run: bool) -> bool:
    if not pkgs:
        return True
    if dry_run:
        warn(f"DRY-RUN: would run: {helper} -S --needed --noconfirm {' '.join(pkgs)}")
        return True
    proc = run([helper, "-S", "--needed", "--noconfirm", *pkgs], check=False)
    return proc.returncode == 0


def install_packages(args: argparse.Namespace) -> None:
    step("Step 1/5 — Packages")

    if not which("pacman"):
        die("pacman not found — this installer targets Arch-based systems (CachyOS).")
    if not is_arch_based():
        warn("This does not look like an Arch-based system. Continuing anyway, "
             "but pacman installs may fail.")

    installed = installed_packages()

    flat_core: list[str] = []
    for group in CORE_PACKAGE_GROUPS.values():
        for pkg in group:
            if pkg not in flat_core:
                flat_core.append(pkg)

    missing_core = [p for p in flat_core if not package_is_installed(p, installed)]

    print()
    for title, group in CORE_PACKAGE_GROUPS.items():
        states = ", ".join(
            f"{p}{'' if package_is_installed(p, installed) else _c(' (missing)', '1;33')}"
            for p in group
        )
        info(f"  {_c(title, '1')}\n      {states}")

    print()
    if missing_core:
        info(f"  {_c(str(len(missing_core)) + ' core package(s) to install:', '1;33')} "
             + " ".join(missing_core))
    else:
        ok("All core packages are already installed.")

    # Optional (official repo) packages
    optional_choice = False
    if args.skip_optional:
        optional_choice = False
    elif args.with_optional:
        optional_choice = True
    elif not args.dry_run:
        optional_choice = confirm(
            f"  Also install optional apps referenced by the configs ({', '.join(OPTIONAL_PACKAGES)})?",
            assume_yes=args.yes, default=False,
        )

    # AUR packages
    helper = find_aur_helper()
    aur_choice = False
    if args.with_aur:
        aur_choice = True
    elif not args.dry_run and not args.skip_optional:
        aur_choice = confirm(
            f"  Also install AUR package(s) ({', '.join(AUR_PACKAGES)})? "
            f"(helper: {helper or 'none found'})",
            assume_yes=args.yes, default=False,
        )
    if aur_choice and not helper:
        warn("No AUR helper (paru/yay) found — skipping AUR packages. "
             "CachyOS usually ships 'paru'.")
        aur_choice = False

    if args.dry_run:
        if optional_choice or args.with_optional:
            warn(f"DRY-RUN: would also install optional: {' '.join(OPTIONAL_PACKAGES)}")
        if aur_choice or args.with_aur:
            warn(f"DRY-RUN: would also install AUR: {' '.join(AUR_PACKAGES)}")

    if not confirm("  Proceed with package installation?", assume_yes=args.yes):
        warn("Package installation skipped by user.")
        return

    to_install = list(missing_core)
    if optional_choice:
        to_install += [p for p in OPTIONAL_PACKAGES if p not in installed]

    if to_install and not pacman_install(to_install, dry_run=args.dry_run):
        warn("Some packages failed to install. Continuing — check the pacman output above.")

    if aur_choice and AUR_PACKAGES:
        if not aur_install(helper, AUR_PACKAGES, dry_run=args.dry_run):
            warn("AUR install failed (skipping). You can install manually later: "
                 f"{helper} -S {' '.join(AUR_PACKAGES)}")


# --------------------------------------------------------------------------- #
# Repository handling
# --------------------------------------------------------------------------- #

def obtain_repo(args: argparse.Namespace) -> tuple[Path, "callable"]:
    """Return (repo_path, cleanup_callable)."""
    if args.local_repo:
        repo = Path(args.local_repo).expanduser().resolve()
        if not repo.is_dir():
            die(f"--local-repo path does not exist: {repo}")
        if not any(repo.iterdir()):
            die(f"--local-repo path is empty: {repo}")
        ok(f"Using local repository: {repo}")
        return repo, (lambda: None)

    if not which("git"):
        if args.skip_packages or args.dry_run:
            die("'git' is required to clone the rice repo. Install it first: sudo pacman -S git")
        warn("'git' not found — installing it first ...")
        pacman_install(["git"], dry_run=False)
        if not which("git"):
            die("Failed to install git.")

    tmp = Path(tempfile.mkdtemp(prefix="rice-install-"))

    def cleanup() -> None:
        shutil.rmtree(tmp, ignore_errors=True)

    step("Step 0/5 — Fetch repository")
    try:
        run(["git", "clone", "--depth", "1", REPO_URL, str(tmp / "repo")])
    except subprocess.CalledProcessError:
        cleanup()
        die("git clone failed. Check your network connection.")
    repo = tmp / "repo"
    ok(f"Cloned to {repo}")
    return repo, cleanup


def repo_config_dirs(repo: Path) -> list[Path]:
    """Top-level, non-hidden directories of the repo = config folders."""
    return sorted(
        d for d in repo.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )


def repo_font_files(repo: Path) -> list[Path]:
    """All font files shipped in the repo (waybar Waycat/Skulltype etc.)."""
    fonts: list[Path] = []
    for pattern in ("*.ttf", "*.otf", "*.ttc"):
        fonts.extend(
            f for f in repo.rglob(pattern)
            if ".git" not in f.parts
        )
    return sorted(set(fonts))


# --------------------------------------------------------------------------- #
# Backup
# --------------------------------------------------------------------------- #

def create_backup_dir() -> Path:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = BACKUP_ROOT / f"backup-{stamp}"
    n = 1
    while candidate.exists():
        candidate = BACKUP_ROOT / f"backup-{stamp}-{n}"
        n += 1
    return candidate


def plan_backup(config_dirs: list[Path], fonts: list[Path]) -> tuple[list[tuple[Path, Path]], list[tuple[Path, Path]]]:
    """Return (existing_config_targets, existing_font_targets) as (src, dest_in_home) pairs."""
    config_targets = []
    for d in config_dirs:
        target = CONFIG_DIR / d.name
        if target.exists():
            config_targets.append((target, target))
    font_targets = []
    for f in fonts:
        target = FONT_DIR / f.name
        if target.exists():
            font_targets.append((target, target))
    return config_targets, font_targets


def do_backup(
    backup_dir: Path,
    config_targets: list[tuple[Path, Path]],
    font_targets: list[tuple[Path, Path]],
    *,
    dry_run: bool,
) -> Path | None:
    if not config_targets and not font_targets:
        ok("Nothing to back up (no existing configs will be overwritten).")
        return None

    if dry_run:
        for src, _ in config_targets + font_targets:
            warn(f"DRY-RUN: would back up {src}")
        return None

    backup_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"Backup created: {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]

    for src, _ in config_targets:
        rel = src.relative_to(HOME)
        dest = backup_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest, symlinks=True)
        ok(f"Backed up {src}  ->  {dest}")
        lines.append(str(src))

    if font_targets:
        fdest_dir = backup_dir / FONT_DIR.relative_to(HOME)
        fdest_dir.mkdir(parents=True, exist_ok=True)
        for src, _ in font_targets:
            dest = fdest_dir / src.name
            shutil.copy2(src, dest)
            ok(f"Backed up {src}  ->  {dest}")
            lines.append(str(src))

    (backup_dir / "BACKUP_INFO.txt").write_text("\n".join(lines) + "\n")
    return backup_dir


# --------------------------------------------------------------------------- #
# Copy + path fixing + fonts
# --------------------------------------------------------------------------- #

def copy_configs(config_dirs: list[Path], *, dry_run: bool) -> list[Path]:
    destinations: list[Path] = []
    ignore = shutil.ignore_patterns(".git", *COPY_IGNORE_SUFFIXES)
    for d in config_dirs:
        dest = CONFIG_DIR / d.name
        destinations.append(dest)
        if dry_run:
            warn(f"DRY-RUN: would copy {d}/  ->  {dest}/")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(d, dest, symlinks=True, dirs_exist_ok=True, ignore=ignore)
        ok(f"Copied {d.name}/  ->  {dest}/")
    return destinations


def fix_hardcoded_paths(destinations: list[Path], *, dry_run: bool) -> None:
    """Rewrite UPSTREAM_HOME (/home/zei) to the real $HOME in text configs."""
    if str(HOME) == UPSTREAM_HOME:
        return  # nothing to fix
    changed: list[Path] = []
    for dest in destinations:
        if not dest.exists():
            continue
        for path in dest.rglob("*"):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue  # binary file (images, fonts) — skip
            if UPSTREAM_HOME in text:
                if not dry_run:
                    path.write_text(text.replace(UPSTREAM_HOME, str(HOME)), encoding="utf-8")
                changed.append(path)
    if dry_run:
        for p in changed:
            warn(f"DRY-RUN: would rewrite '{UPSTREAM_HOME}' -> '{HOME}' in {p}")
    elif changed:
        ok(f"Rewrote hardcoded '{UPSTREAM_HOME}' paths in {len(changed)} file(s):")
        for p in changed:
            info(f"      {p}")


def make_scripts_executable(destinations: list[Path], *, dry_run: bool) -> None:
    for dest in destinations:
        if not dest.exists():
            continue
        for sh in dest.rglob("*.sh"):
            if dry_run:
                warn(f"DRY-RUN: would chmod +x {sh}")
                continue
            sh.chmod(sh.stat().st_mode | 0o111)
            ok(f"chmod +x {sh}")


def install_fonts(fonts: list[Path], *, dry_run: bool) -> None:
    if not fonts:
        return
    for f in fonts:
        dest = FONT_DIR / f.name
        if dry_run:
            warn(f"DRY-RUN: would install font {f}  ->  {dest}")
            continue
        FONT_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)
        ok(f"Installed font {f.name}  ->  {dest}")
    if dry_run:
        return
    if which("fc-cache"):
        run(["fc-cache", "-f"], show=False, check=False)
        ok("Font cache refreshed (fc-cache).")


def sync_nvim_plugins(args: argparse.Namespace) -> None:
    if args.no_nvim_plugins:
        return
    if not (CONFIG_DIR / "nvim").exists():
        return
    if not which("nvim"):
        warn("neovim not found in PATH — skipping plugin sync. "
             "Run 'nvim' once manually to bootstrap LazyVim.")
        return
    if args.dry_run:
        warn('DRY-RUN: would run: nvim --headless "+Lazy! sync" +qa')
        return
    info("  Syncing LazyVim plugins (this can take a few minutes) ...")
    try:
        run(["nvim", "--headless", "+Lazy! sync", "+qa"], check=False, timeout=1200)
        ok("LazyVim plugin sync finished.")
    except subprocess.TimeoutExpired:
        warn("Plugin sync timed out. Open nvim manually to finish it.")
    except Exception as exc:  # pragma: no cover
        warn(f"Plugin sync failed: {exc}. Open nvim manually to bootstrap plugins.")


# --------------------------------------------------------------------------- #
# Restore
# --------------------------------------------------------------------------- #

def list_backups() -> list[Path]:
    if not BACKUP_ROOT.exists():
        return []
    return sorted(
        (d for d in BACKUP_ROOT.iterdir() if d.is_dir() and d.name.startswith("backup-")),
        key=lambda p: p.name,
    )


def do_restore(selection: str) -> None:
    step("Restore from backup")
    backups = list_backups()
    if not backups:
        die(f"No backups found in {BACKUP_ROOT}")

    if selection == "latest":
        backup = backups[-1]
    else:
        candidate = Path(selection).expanduser()
        if not candidate.is_absolute():
            candidate = BACKUP_ROOT / selection
        if not candidate.is_dir():
            info("Available backups:")
            for b in backups:
                info(f"  - {b}")
            die(f"Backup not found: {selection}")
        backup = candidate

    info(f"Restoring from: {backup}")
    backed_cfg = backup / ".config"
    backed_fonts = backup / ".local" / "share" / "fonts"

    restored: list[str] = []
    if backed_cfg.is_dir():
        for child in backed_cfg.iterdir():
            target = CONFIG_DIR / child.name
            # Sanity guard: only ever touch directories directly inside ~/.config
            if target.resolve().parent != CONFIG_DIR.resolve():
                warn(f"Skipping suspicious path: {target}")
                continue
            if child.is_dir():
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(child, target, symlinks=True)
                restored.append(str(target))
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, target)
                restored.append(str(target))

    if backed_fonts.is_dir():
        FONT_DIR.mkdir(parents=True, exist_ok=True)
        for child in backed_fonts.iterdir():
            if child.is_file():
                dest = FONT_DIR / child.name
                shutil.copy2(child, dest)
                restored.append(str(dest))

    if not restored:
        warn("Backup contained nothing to restore.")
        return

    ok("Restored:")
    for r in restored:
        info(f"      {r}")
    warn("Note: files created by the rice that did not exist before are NOT removed "
         "by a restore; they are only overwritten where the backup had content.")
    if which("fc-cache"):
        run(["fc-cache", "-f"], show=False, check=False)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Install the most-racist-rice-V2 dotfiles on CachyOS / Arch.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--dry-run", action="store_true",
                   help="show what would happen without changing anything")
    p.add_argument("-y", "--yes", action="store_true",
                   help="non-interactive: install core packages only, no prompts")
    p.add_argument("--skip-packages", action="store_true",
                   help="skip the package phase entirely (backup + copy only)")
    p.add_argument("--with-optional", action="store_true",
                   help=f"also install optional official packages ({', '.join(OPTIONAL_PACKAGES)})")
    p.add_argument("--with-aur", action="store_true",
                   help=f"also install AUR packages ({', '.join(AUR_PACKAGES)}) if a helper exists")
    p.add_argument("--skip-optional", action="store_true",
                   help="never ask about optional/AUR packages")
    p.add_argument("--no-nvim-plugins", action="store_true",
                   help="do not run the headless LazyVim plugin sync")
    p.add_argument("--local-repo", type=Path, default=None, metavar="PATH",
                   help="use an already-cloned copy of the repo instead of cloning")
    p.add_argument("--restore", nargs="?", const="latest", default=None, metavar="BACKUP",
                   help="restore a backup ('latest' or a backup name/path); "
                        "without a value, lists available backups")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    print(_c("=" * 72, "1;35"))
    print(_c("  most-racist-rice-V2  —  CachyOS / Arch installer", "1;35"))
    print(_c(f"  repo   : {REPO_URL}", "1;35"))
    print(_c(f"  home   : {HOME}", "1;35"))
    print(_c("=" * 72, "1;35"))

    if os.geteuid() == 0 and not os.environ.get("RICE_INSTALLER_ALLOW_ROOT"):
        die("Do not run this installer as root/sudo — run it as your normal user. "
            "(It calls sudo itself for pacman.)")

    # ---------------- restore mode ---------------- #
    if args.restore is not None:
        if args.restore == "":
            backups = list_backups()
            if not backups:
                die(f"No backups found in {BACKUP_ROOT}")
            info("Available backups:")
            for b in backups:
                info(f"  - {b.name}")
            return 0
        do_restore(args.restore)
        return 0

    repo, cleanup = obtain_repo(args)
    try:
        config_dirs = repo_config_dirs(repo)
        if not config_dirs:
            die(f"No config folders found in repo: {repo}")
        fonts = repo_font_files(repo)

        # ---------------- packages ---------------- #
        if args.skip_packages:
            warn("--skip-packages: not touching packages.")
        else:
            install_packages(args)

        # ---------------- backup plan ---------------- #
        step("Step 2/5 — Backup of existing configs")
        config_targets, font_targets = plan_backup(config_dirs, fonts)
        if config_targets or font_targets:
            info("  These existing paths will be backed up before being changed:")
            for src, _ in config_targets + font_targets:
                info(f"      {src}")
        else:
            info("  No existing configs will be overwritten — nothing to back up.")

        # ---------------- copy plan ---------------- #
        step("Step 3/5 — Dotfiles to install")
        for d in config_dirs:
            info(f"      {d.name}/  ->  {CONFIG_DIR / d.name}/")
        for f in fonts:
            info(f"      font {f.name}  ->  {FONT_DIR / f.name}")
        if str(HOME) != UPSTREAM_HOME:
            info(f"      (hardcoded '{UPSTREAM_HOME}' paths will be rewritten to '{HOME}')")

        if not confirm("\n  Create backup and install the dotfiles now?",
                       assume_yes=args.yes):
            warn("Aborted by user before any changes were made.")
            return 0

        # ---------------- execute ---------------- #
        step("Step 4/5 — Backup + copy")
        backup_dir = create_backup_dir()
        done_backup = do_backup(backup_dir, config_targets, font_targets, dry_run=args.dry_run)
        destinations = copy_configs(config_dirs, dry_run=args.dry_run)
        fix_hardcoded_paths(destinations, dry_run=args.dry_run)
        make_scripts_executable(destinations, dry_run=args.dry_run)
        install_fonts(fonts, dry_run=args.dry_run)

        step("Step 5/5 — Neovim plugins")
        sync_nvim_plugins(args)

        # ---------------- summary ---------------- #
        print()
        print(_c("=" * 72, "1;32"))
        print(_c("  Installation finished!", "1;32"))
        print(_c("=" * 72, "1;32"))
        if done_backup:
            info(f"  Backup saved at : {done_backup}")
            info(f"  Roll back with  : python {Path(sys.argv[0]).name} --restore latest")
        info("  Installed into  : ~/.config/{fastfetch,fuzzel,gtk-3.0,gtk-4.0,hypr,kitty,")
        info("                     mango,nvim,rofi,wallpaper,waybar} + ~/.local/share/fonts")
        print()
        info(_c("  Next steps / things to check:", "1"))
        info("   1. Log out, then pick the 'Hyprland' (or 'mango') session in your")
        info("      display manager (SDDM) and log back in.")
        info("   2. ~/.config/hypr/hyprland.lua hardcodes monitor mode 1920x1080@144hz —")
        info("      adjust it to your display (hyprctl monitors shows your modes).")
        info("   3. ~/.config/mango/config.conf also has a monitor_rule for HDMI-A-1 —")
        info("      adjust it if you use mango.")
        info("   4. fastfetch config shows the author's name/device ('Zei', 'Zeibook Air')")
        info("      in ~/.config/fastfetch/config.jsonc — edit those strings if you like.")
        info("   5. Waybar's mpris module is set to player=spotify; if you don't use")
        info("      Spotify the widget just stays empty (or edit waybar/config.jsonc).")
        info("   6. Kitty is configured with 'shell fish' — fish is installed, but if")
        info("      you prefer bash/zsh edit ~/.config/kitty/kitty.conf.")
        return 0
    finally:
        cleanup()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        err("\nInterrupted by user.")
        sys.exit(130)
