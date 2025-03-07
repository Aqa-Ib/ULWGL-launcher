import unittest
import ulwgl_run
import os
import argparse
import re
import ulwgl_plugins
import tarfile
import json
import ulwgl_util
from argparse import Namespace
from unittest.mock import patch
from pathlib import Path
from tomllib import TOMLDecodeError
from shutil import rmtree, copy, copytree


class TestGameLauncherPlugins(unittest.TestCase):
    """Test suite ulwgl_run.py plugins."""

    def setUp(self):
        """Create the test directory, exe and environment variables."""
        self.env = {
            "WINEPREFIX": "",
            "GAMEID": "",
            "PROTON_CRASH_REPORT_DIR": "/tmp/ULWGL_crashreports",
            "PROTONPATH": "",
            "STEAM_COMPAT_APP_ID": "",
            "STEAM_COMPAT_TOOL_PATHS": "",
            "STEAM_COMPAT_LIBRARY_PATHS": "",
            "STEAM_COMPAT_MOUNTS": "",
            "STEAM_COMPAT_INSTALL_PATH": "",
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": "",
            "STEAM_COMPAT_DATA_PATH": "",
            "STEAM_COMPAT_SHADER_PATH": "",
            "FONTCONFIG_PATH": "",
            "EXE": "",
            "SteamAppId": "",
            "SteamGameId": "",
            "STEAM_RUNTIME_LIBRARY_PATH": "",
            "ULWGL_ID": "",
            "STORE": "",
            "PROTON_VERB": "",
        }
        self.test_opts = "-foo -bar"
        # Proton verb
        # Used when testing build_command
        self.test_verb = "waitforexitandrun"
        # Test directory
        self.test_file = "./tmp.AKN6tnueyO"
        # Executable
        self.test_exe = self.test_file + "/" + "foo"
        # Cache
        self.test_cache = Path("./tmp.ND7tcK5m3K")
        # Steam compat dir
        self.test_compat = Path("./tmp.1A5cflhwQa")
        # ULWGL-Proton dir
        self.test_proton_dir = Path("ULWGL-Proton-jPTxUsKDdn")
        # ULWGL-Proton release
        self.test_archive = Path(self.test_cache).joinpath(
            f"{self.test_proton_dir}.tar.gz"
        )
        # /usr/share/ULWGL
        self.test_user_share = Path("./tmp.jl3W4MtO57")
        # ~/.local/share/Steam/compatibilitytools.d
        self.test_local_share = Path("./tmp.WUaQAk7hQJ")

        # Dictionary that represents the ULWGL_VERSIONS.json
        self.root_config = {
            "ulwgl": {
                "versions": {
                    "launcher": "0.1-RC3",
                    "runner": "0.1-RC3",
                    "runtime_platform": "sniper_platform_0.20240125.75305",
                    "reaper": "1.0",
                    "pressure_vessel": "v0.20240212.0",
                }
            }
        }
        # ULWGL_VERSION.json
        self.test_config = json.dumps(self.root_config, indent=4)

        self.test_user_share.mkdir(exist_ok=True)
        self.test_local_share.mkdir(exist_ok=True)
        self.test_cache.mkdir(exist_ok=True)
        self.test_compat.mkdir(exist_ok=True)
        self.test_proton_dir.mkdir(exist_ok=True)

        # Mock a valid configuration file at /usr/share/ULWGL:
        # tmp.BXk2NnvW2m/ULWGL_VERSION.json
        Path(self.test_user_share, "ULWGL_VERSION.json").touch()
        with Path(self.test_user_share, "ULWGL_VERSION.json").open(mode="w") as file:
            file.write(self.test_config)

        # Mock the launcher files
        Path(self.test_user_share, "ulwgl_consts.py").touch()
        Path(self.test_user_share, "ulwgl_dl_util.py").touch()
        Path(self.test_user_share, "ulwgl_log.py").touch()
        Path(self.test_user_share, "ulwgl_plugins.py").touch()
        Path(self.test_user_share, "ulwgl_run.py").touch()
        Path(self.test_user_share, "ulwgl_util.py").touch()
        Path(self.test_user_share, "ulwgl-run").symlink_to("ulwgl_run.py")

        # Mock the runtime files
        Path(self.test_user_share, "sniper_platform_0.20240125.75305").mkdir()
        Path(self.test_user_share, "sniper_platform_0.20240125.75305", "foo").touch()
        Path(self.test_user_share, "run").touch()
        Path(self.test_user_share, "run-in-sniper").touch()
        Path(self.test_user_share, "ULWGL").touch()

        # Mock pressure vessel
        Path(self.test_user_share, "pressure-vessel").mkdir()
        Path(self.test_user_share, "pressure-vessel", "foo").touch()

        # Mock ULWGL-Launcher
        Path(self.test_user_share, "ULWGL-Launcher").mkdir()
        Path(self.test_user_share, "ULWGL-Launcher", "compatibilitytool.vdf").touch()
        Path(self.test_user_share, "ULWGL-Launcher", "toolmanifest.vdf").touch()

        # Mock Reaper
        Path(self.test_user_share, "reaper").touch()

        # Mock the proton file in the dir
        self.test_proton_dir.joinpath("proton").touch(exist_ok=True)

        Path(self.test_file).mkdir(exist_ok=True)
        Path(self.test_exe).touch()

        self.test_cache.mkdir(exist_ok=True)
        self.test_compat.mkdir(exist_ok=True)
        self.test_proton_dir.mkdir(exist_ok=True)

        # Mock the proton file in the dir
        self.test_proton_dir.joinpath("proton").touch(exist_ok=True)

        # Mock the release downloaded in the cache:
        # tmp.5HYdpddgvs/ULWGL-Proton-jPTxUsKDdn.tar.gz
        # Expected directory structure within the archive:
        #
        # +-- ULWGL-Proton-5HYdpddgvs (root directory)
        # |   +-- proton              (normal file)
        with tarfile.open(self.test_archive.as_posix(), "w:gz") as tar:
            tar.add(
                self.test_proton_dir.as_posix(), arcname=self.test_proton_dir.as_posix()
            )

        Path(self.test_file).mkdir(exist_ok=True)
        Path(self.test_exe).touch()

    def tearDown(self):
        """Unset environment variables and delete test files after each test."""
        for key, val in self.env.items():
            if key in os.environ:
                os.environ.pop(key)

        if Path(self.test_file).exists():
            rmtree(self.test_file)

        if self.test_cache.exists():
            rmtree(self.test_cache.as_posix())

        if self.test_compat.exists():
            rmtree(self.test_compat.as_posix())

        if self.test_proton_dir.exists():
            rmtree(self.test_proton_dir.as_posix())

        if self.test_user_share.exists():
            rmtree(self.test_user_share.as_posix())

        if self.test_local_share.exists():
            rmtree(self.test_local_share.as_posix())

    def test_build_command_entry(self):
        """Test build_command.

        A FileNotFoundError should be raised if $PROTONPATH/ULWGL does not exist
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}"]
        exe = "{self.test_exe}"
        """
        toml_path = self.test_file + "/" + test_toml
        result = None
        test_command = []
        Path(toml_path).touch()

        # Mock the proton file
        Path(self.test_file, "proton").touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            # Config
            ulwgl_plugins.set_env_toml(self.env, result)
            # Prefix
            ulwgl_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            ulwgl_run.set_env(self.env, result)
            # Game drive
            ulwgl_plugins.enable_steam_game_drive(self.env)

        # Mock setting up the runtime
        # Don't copy _v2-entry-point
        with patch.object(
            ulwgl_util,
            "setup_runtime",
            return_value=None,
        ):
            ulwgl_util._install_ulwgl(
                self.test_user_share, self.test_local_share, self.test_compat, json
            )
            copytree(
                Path(self.test_user_share, "sniper_platform_0.20240125.75305"),
                Path(self.test_local_share, "sniper_platform_0.20240125.75305"),
                dirs_exist_ok=True,
                symlinks=True,
            )
            copy(Path(self.test_user_share, "run"), Path(self.test_local_share, "run"))
            copy(
                Path(self.test_user_share, "run-in-sniper"),
                Path(self.test_local_share, "run-in-sniper"),
            )

        for key, val in self.env.items():
            os.environ[key] = val

        # Build
        with self.assertRaisesRegex(FileNotFoundError, "_v2-entry-point"):
            ulwgl_run.build_command(self.env, self.test_local_share, test_command)

    def test_build_command_proton(self):
        """Test build_command.

        A FileNotFoundError should be raised if $PROTONPATH/proton does not exist

        Also, FileNotFoundError will be raised if the _v2-entry-point (ULWGL)
        is not in $HOME/.local/share/ULWGL
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}"]
        exe = "{self.test_exe}"
        """
        toml_path = self.test_file + "/" + test_toml
        result = None
        test_command = []
        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            # Config
            ulwgl_plugins.set_env_toml(self.env, result)
            # Prefix
            ulwgl_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            ulwgl_run.set_env(self.env, result)
            # Game drive
            ulwgl_plugins.enable_steam_game_drive(self.env)

        # Mock setting up the runtime
        with patch.object(
            ulwgl_util,
            "setup_runtime",
            return_value=None,
        ):
            ulwgl_util._install_ulwgl(
                self.test_user_share, self.test_local_share, self.test_compat, json
            )
            copytree(
                Path(self.test_user_share, "sniper_platform_0.20240125.75305"),
                Path(self.test_local_share, "sniper_platform_0.20240125.75305"),
                dirs_exist_ok=True,
                symlinks=True,
            )
            copy(Path(self.test_user_share, "run"), Path(self.test_local_share, "run"))
            copy(
                Path(self.test_user_share, "run-in-sniper"),
                Path(self.test_local_share, "run-in-sniper"),
            )
            copy(
                Path(self.test_user_share, "ULWGL"),
                Path(self.test_local_share, "ULWGL"),
            )

        for key, val in self.env.items():
            os.environ[key] = val

        # Build
        with self.assertRaisesRegex(FileNotFoundError, "proton"):
            ulwgl_run.build_command(self.env, self.test_local_share, test_command)

    def test_build_command_toml(self):
        """Test build_command.

        After parsing a valid TOML file, be sure we do not raise a FileNotFoundError
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}", "{self.test_file}"]
        exe = "{self.test_exe}"
        """
        toml_path = self.test_file + "/" + test_toml
        result = None
        test_command = []
        test_command_result = None

        Path(self.test_file + "/proton").touch()
        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            # Config
            ulwgl_plugins.set_env_toml(self.env, result)
            # Prefix
            ulwgl_run.setup_pfx(self.env["WINEPREFIX"])
            # Env
            ulwgl_run.set_env(self.env, result)
            # Game drive
            ulwgl_plugins.enable_steam_game_drive(self.env)

        # Mock setting up the runtime
        with patch.object(
            ulwgl_util,
            "setup_runtime",
            return_value=None,
        ):
            ulwgl_util._install_ulwgl(
                self.test_user_share, self.test_local_share, self.test_compat, json
            )
            copytree(
                Path(self.test_user_share, "sniper_platform_0.20240125.75305"),
                Path(self.test_local_share, "sniper_platform_0.20240125.75305"),
                dirs_exist_ok=True,
                symlinks=True,
            )
            copy(Path(self.test_user_share, "run"), Path(self.test_local_share, "run"))
            copy(
                Path(self.test_user_share, "run-in-sniper"),
                Path(self.test_local_share, "run-in-sniper"),
            )
            copy(
                Path(self.test_user_share, "ULWGL"),
                Path(self.test_local_share, "ULWGL"),
            )

        for key, val in self.env.items():
            os.environ[key] = val

        # Build
        test_command_result = ulwgl_run.build_command(
            self.env, self.test_local_share, test_command
        )
        self.assertTrue(
            test_command_result is test_command, "Expected the same reference"
        )

        # Verify contents of the command
        reaper, id, opt0, entry_point, opt1, verb, opt2, proton, verb2, exe = [
            *test_command
        ]
        # The entry point dest could change. Just check if there's a value
        self.assertTrue(reaper, "Expected reaper")
        self.assertTrue(id, "Expected a tag for reaper")
        self.assertTrue(opt0, "Expected --")
        self.assertTrue(entry_point, "Expected an entry point")
        self.assertEqual(opt1, "--verb", "Expected --verb")
        self.assertEqual(verb, self.test_verb, "Expected a verb")
        self.assertEqual(opt2, "--", "Expected --")
        self.assertEqual(
            proton,
            Path(self.env.get("PROTONPATH") + "/proton").as_posix(),
            "Expected the proton file",
        )
        self.assertEqual(verb2, self.test_verb, "Expected a verb")
        self.assertEqual(exe, self.env["EXE"], "Expected the EXE")

    def test_set_env_toml_nofile(self):
        """Test set_env_toml for values that are not a file.

        A FileNotFoundError should be raised if the 'exe' is not a file
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}", "{self.test_file}"]
        exe = "./bar"
        """
        toml_path = self.test_file + "/" + test_toml
        result = None

        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            # Env
            with self.assertRaisesRegex(FileNotFoundError, "exe"):
                ulwgl_plugins.set_env_toml(self.env, result)

    def test_set_env_toml_err(self):
        """Test set_env_toml for valid TOML.

        A TOMLDecodeError should be raised for invalid values
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = [[
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}", "{self.test_file}"]
        """
        toml_path = self.test_file + "/" + test_toml
        result = None

        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            # Env
            with self.assertRaisesRegex(TOMLDecodeError, "Invalid"):
                ulwgl_plugins.set_env_toml(self.env, result)

    def test_set_env_toml_nodir(self):
        """Test set_env_toml if certain key/value are not a dir.

        An IsDirectoryError should be raised if the following keys are not
        dir: proton, prefix
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "foo"
        proton = "foo"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}", "{self.test_file}"]
        """
        toml_path = self.test_file + "/" + test_toml
        result = None

        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            # Env
            with self.assertRaisesRegex(NotADirectoryError, "proton"):
                ulwgl_plugins.set_env_toml(self.env, result)

    def test_set_env_toml_tables(self):
        """Test set_env_toml for expected tables.

        A ValueError should be raised if the following tables are absent: ulwgl
        """
        test_toml = "foo.toml"
        toml_str = f"""
        [foo]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}", "{self.test_file}"]
        """
        toml_path = self.test_file + "/" + test_toml
        result = None

        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            # Env
            with self.assertRaisesRegex(ValueError, "ulwgl"):
                ulwgl_plugins.set_env_toml(self.env, result)

    def test_set_env_toml_paths(self):
        """Test set_env_toml when specifying unexpanded path values.

        Example: ~/Games/foo.exe

        An error should not be raised when passing unexpanded paths to the
        config file as well as the prefix, proton and exe keys
        """
        test_toml = "foo.toml"
        pattern = r"^/home/[\w\d]+"  # Expects only unicode decimals and alphanumerics

        # Replaces the expanded path to unexpanded
        # Example: ~/some/path/to/this/file -> /home/foo/path/to/this/file
        path_to_tmp = Path(
            Path(__file__).cwd().as_posix() + "/" + self.test_file
        ).as_posix()
        path_to_exe = Path(
            Path(__file__).cwd().as_posix() + "/" + self.test_exe
        ).as_posix()

        # Replace /home/[a-zA-Z]+ substring in path with tilda
        unexpanded_path = re.sub(
            pattern,
            "~",
            path_to_tmp,
        )
        unexpanded_exe = re.sub(
            pattern,
            "~",
            path_to_exe,
        )
        toml_str = f"""
        [ulwgl]
        prefix = "{unexpanded_path}"
        proton = "{unexpanded_path}"
        game_id = "{unexpanded_path}"
        exe = "{unexpanded_exe}"
        """
        # Path to TOML in unexpanded form
        toml_path = unexpanded_path + "/" + test_toml
        result = None
        result_set_env = None

        Path(toml_path).expanduser().touch()

        with Path(toml_path).expanduser().open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            # Env
            result_set_env = ulwgl_plugins.set_env_toml(self.env, result)
            self.assertTrue(isinstance(result_set_env, tuple), "Expected a tuple")

            # Check that the paths are still in the unexpanded form after
            # setting the env
            # In main, we only expand them after this function exits to
            # prepare for building the command
            self.assertEqual(
                self.env["EXE"], unexpanded_exe, "Expected path not to be expanded"
            )
            self.assertEqual(
                self.env["PROTONPATH"],
                unexpanded_path,
                "Expected path not to be expanded",
            )
            self.assertEqual(
                self.env["WINEPREFIX"],
                unexpanded_path,
                "Expected path not to be expanded",
            )
            self.assertEqual(
                self.env["GAMEID"], unexpanded_path, "Expectd path not to be expanded"
            )

    def test_set_env_toml_opts(self):
        """Test set_env_toml when passed a string as a launch argument."""
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = "{self.test_file} {self.test_file}"
        exe = "{self.test_exe}"
        """
        toml_path = self.test_file + "/" + test_toml
        result = None
        result_set_env = None

        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")

            # Env
            # The first argument is the env
            result_set_env = ulwgl_plugins.set_env_toml(self.env, result)
            self.assertTrue(isinstance(result_set_env, tuple), "Expected a tuple")
            self.assertTrue(
                result_set_env[0] is self.env, "Expected the same reference"
            )

            # Verify the launch arguments
            self.assertTrue(
                isinstance(result_set_env[1], list), "Expected a list for game options"
            )
            self.assertEqual(
                result_set_env[1][0],
                self.test_file,
                "Expected the test file as first arg",
            )
            self.assertEqual(
                result_set_env[1][1],
                self.test_file,
                "Expected the test file as second arg",
            )

            self.assertTrue(self.env["EXE"], "Expected EXE to be set")
            self.assertEqual(
                self.env["PROTONPATH"],
                self.test_file,
                "Expected PROTONPATH to be set",
            )
            self.assertEqual(
                self.env["WINEPREFIX"],
                self.test_file,
                "Expected WINEPREFIX to be set",
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )

    def test_set_env_toml(self):
        """Test set_env_toml."""
        test_toml = "foo.toml"
        toml_str = f"""
        [ulwgl]
        prefix = "{self.test_file}"
        proton = "{self.test_file}"
        game_id = "{self.test_file}"
        launch_args = ["{self.test_file}", "{self.test_file}"]
        exe = "{self.test_exe}"
        """
        toml_path = self.test_file + "/" + test_toml
        result = None
        result_set_env = None

        Path(toml_path).touch()

        with Path(toml_path).open(mode="w") as file:
            file.write(toml_str)

        with patch.object(
            ulwgl_run,
            "parse_args",
            return_value=argparse.Namespace(config=toml_path),
        ):
            # Args
            result = ulwgl_run.parse_args()
            self.assertIsInstance(
                result, Namespace, "Expected a Namespace from parse_arg"
            )
            self.assertTrue(vars(result).get("config"), "Expected a value for --config")
            # Env
            result_set_env = ulwgl_plugins.set_env_toml(self.env, result)
            self.assertTrue(isinstance(result_set_env, tuple), "Expected a tuple")
            self.assertTrue(self.env["EXE"], "Expected EXE to be set")
            self.assertEqual(
                self.env["PROTONPATH"],
                self.test_file,
                "Expected PROTONPATH to be set",
            )
            self.assertEqual(
                self.env["WINEPREFIX"],
                self.test_file,
                "Expected WINEPREFIX to be set",
            )
            self.assertEqual(
                self.env["GAMEID"], self.test_file, "Expected GAMEID to be set"
            )


if __name__ == "__main__":
    unittest.main()
