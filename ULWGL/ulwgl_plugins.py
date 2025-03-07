from subprocess import PIPE, Popen, STDOUT
from os import environ
from pathlib import Path
from typing import Dict, Set, Any, List, Tuple
from argparse import Namespace
from shutil import which


def set_env_toml(
    env: Dict[str, str], args: Namespace
) -> Tuple[Dict[str, str], List[str]]:
    """Read a TOML file then sets the environment variables for the Steam RT.

    In the TOML file, certain keys map to Steam RT environment variables. For example:
          proton -> $PROTONPATH
          prefix -> $WINEPREFIX
          game_id -> $GAMEID
          exe -> $EXE
    At the moment we expect the tables: 'ulwgl'
    """
    try:
        import tomllib
    except ModuleNotFoundError:
        msg: str = "tomllib requires Python 3.11"
        raise ModuleNotFoundError(msg)

    toml: Dict[str, Any] = None
    path_config: str = Path(getattr(args, "config", None)).expanduser().as_posix()
    opts: List[str] = []

    if not Path(path_config).is_file():
        msg: str = "Path to configuration is not a file: " + getattr(
            args, "config", None
        )
        raise FileNotFoundError(msg)

    with Path(path_config).open(mode="rb") as file:
        toml = tomllib.load(file)

    _check_env_toml(env, toml)

    for key, val in toml["ulwgl"].items():
        if key == "prefix":
            env["WINEPREFIX"] = val
        elif key == "game_id":
            env["GAMEID"] = val
        elif key == "proton":
            env["PROTONPATH"] = val
        elif key == "store":
            env["STORE"] = val
        elif key == "exe":
            env["EXE"] = val
        elif key == "launch_args" and isinstance(val, list):
            opts = val
        elif key == "launch_args" and isinstance(val, str):
            opts = val.split(" ")

    return env, opts


def _check_env_toml(env: Dict[str, str], toml: Dict[str, Any]) -> Dict[str, Any]:
    """Check for required or empty key/value pairs when reading a TOML config.

    NOTE: Casing matters in the config and we do not check if the game id is set
    """
    table: str = "ulwgl"
    required_keys: List[str] = ["proton", "prefix", "exe"]

    if table not in toml:
        err: str = f"Table '{table}' in TOML is not defined."
        raise ValueError(err)

    for key in required_keys:
        if key not in toml[table]:
            err: str = f"The following key in table '{table}' is required: {key}"
            raise ValueError(err)

        # Raise an error for executables that do not exist
        # One case this can happen is when game options are appended at the
        # end of the exe
        # Users should use launch_args game options
        if key == "exe" and not Path(toml[table][key]).expanduser().is_file():
            val: str = toml[table][key]
            err: str = f"Value for key '{key}' in TOML is not a file: {val}"
            raise FileNotFoundError(err)

        # The proton and wine prefix need to be folders
        if (key == "proton" and not Path(toml[table][key]).expanduser().is_dir()) or (
            key == "prefix" and not Path(toml[table][key]).expanduser().is_dir()
        ):
            dir: str = Path(toml[table][key]).expanduser().as_posix()
            err: str = f"Value for key '{key}' in TOML is not a directory: {dir}"
            raise NotADirectoryError(err)

    # Check for empty keys
    for key, val in toml[table].items():
        if not val and isinstance(val, str):
            err: str = (
                f"Value is empty for '{key}' in TOML.\n"
                f"Please specify a value or remove the following entry:\n{key} = {val}"
            )
            raise ValueError(err)

    return toml


def enable_steam_game_drive(env: Dict[str, str]) -> Dict[str, str]:
    """Enable Steam Game Drive functionality.

    Expects STEAM_COMPAT_INSTALL_PATH to be set
    STEAM_RUNTIME_LIBRARY_PATH will not be set if the exe directory does not exist
    """
    paths: Set[str] = set()
    root: Path = Path("/")

    # Check for mount points going up toward the root
    # NOTE: Subvolumes can be mount points
    for path in Path(env["STEAM_COMPAT_INSTALL_PATH"]).parents:
        if path.is_mount() and path != root:
            if env["STEAM_COMPAT_LIBRARY_PATHS"]:
                env["STEAM_COMPAT_LIBRARY_PATHS"] = (
                    env["STEAM_COMPAT_LIBRARY_PATHS"] + ":" + path.as_posix()
                )
            else:
                env["STEAM_COMPAT_LIBRARY_PATHS"] = path.as_posix()
            break

    if "LD_LIBRARY_PATH" in environ:
        paths.add(Path(environ["LD_LIBRARY_PATH"]).as_posix())

    if env["STEAM_COMPAT_INSTALL_PATH"]:
        paths.add(env["STEAM_COMPAT_INSTALL_PATH"])

    # Hard code for now because these paths seem to be pretty standard
    # This way we avoid shelling to ldconfig
    paths.add("/usr/lib")
    paths.add("/usr/lib32")
    env["STEAM_RUNTIME_LIBRARY_PATH"] = ":".join(list(paths))

    return env


def enable_reaper(env: Dict[str, str], command: List[str], local: Path) -> List[str]:
    """Enable Reaper to monitor and keep track of descendent processes."""
    command.extend(
        [
            local.joinpath("reaper").as_posix(),
            "ULWGL_ID=" + env["ULWGL_ID"],
            "--",
        ]
    )

    return command


def enable_zenity(command: str, opts: List[str], msg: str) -> None:
    """Execute the command and pipe the output to Zenity.

    Intended to be used for long running operations (e.g. large file downloads)
    """
    bin: str = which("zenity")
    cmd: str = which(command)

    if not bin:
        err: str = "zenity was not found in system"
        raise FileNotFoundError(err)

    if not cmd:
        err: str = f"{command} was not found in system"
        raise FileNotFoundError(err)

    with Popen([cmd, *opts], stdout=PIPE, stderr=STDOUT) as proc:
        # Start Zenity with a pipe to its standard input
        zenity_proc: Popen = Popen(
            [
                f"{bin}",
                "--progress",
                "--auto-close",
                f"--text={msg}",
                "--percentage=0",
                "--pulsate",
            ],
            stdin=PIPE,
        )

        # Timeout all operations for 3 min.
        proc.wait(timeout=180)

        # Close the Zenity process's standard input
        zenity_proc.stdin.close()
        zenity_proc.wait()
