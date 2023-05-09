import filecmp
import json
import modulefinder
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from io import BytesIO
from modulefinder import ModuleFinder
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Collection
from xml.etree import ElementTree

# Note: all files from the main script's directory will be copied to the target CircuitPython drive!
MAIN_SCRIPT = Path("src", "code.py").resolve()
LIB_DIR = Path("lib").resolve()
COMPILED_DIR = Path("compiled", "lib").resolve()

DEPLOY_DIR_CFG_FILE = Path("circuitpy_drive.txt").resolve()
# Use the same extension as the current Python executable to ensure simple cross-platform executable name
MPY_CROSS_PATH = Path("tools", f"mpy-cross{Path(sys.executable).suffix}").resolve()


class Module(modulefinder.Module):

    @classmethod
    def from_module(cls, module: modulefinder.Module) -> "Module":
        return cls(module.__name__, module.__file__, module.__path__)

    def __str__(self) -> str:
        return self.__name__

    @property
    def is_built_in(self) -> bool:
        # All modules without a __file__ attribute are built-in modules
        return not self.__file__

    @property
    def module_path(self) -> Path:
        """Get absolute path to the module file (raise ValueError if this is a built-in module)"""
        if self.is_built_in:
            raise ValueError(f"Module {self.__name__} is built-in")
        return Path(self.__file__).resolve()

    @property
    def package_path(self) -> Optional[Path]:
        """Get relative package path of this module, or None if this is a single-file module"""
        # A package is a directory of Python modules containing an additional __init__.py file (to distinguish
        # a package from a directory that just happens to contain a bunch of Python scripts). Packages can be
        # nested to any depth, provided that the corresponding directories contain their own __init__.py file.
        # However, modules inside the package may not have the .__path__ attribute set, even if they are inside
        # the package - depends on how they are imported. Therefore, perform additional check with the module
        # name - modules cannot have dots in their name (but packages can) - dot in Python module name
        # represents the sub-package structure.
        mfp = self.module_path
        if self.__name__ == mfp.stem:
            # This is a single-file module
            return None
        # This is a module inside a package
        sub_dirs = self.__name__.split(".")
        # If the last part is the same as the file name (instead of __init__), then this is a directly
        # imported module inside a package - remove it, because it is not a (sub)directory.
        if sub_dirs[-1] == mfp.stem:
            sub_dirs.pop()
        return Path(*sub_dirs)

    @property
    def is_package(self) -> bool:
        return self.package_path and self.module_path.stem == "__init__"

    @property
    def package_relative(self) -> Path:
        """Get module path relative to the package, or just the file name if this module is not in a package"""
        return Path(self.package_path or "", self.module_path.name)


def ensure_adafruit_libraries() -> None:
    # Directory where the libraries shall be located
    target_dir = LIB_DIR.joinpath("adafruit-circuitpython-bundle-py")
    # GitHub repository from which to download the bundle from
    repo = "adafruit/Adafruit_CircuitPython_Bundle"

    print("### Checking Adafruit CircuitPython library bundle")

    if target_dir.is_dir():
        print(f"Library bundle already exists in {target_dir}")
        return

    # Get URL of the latest release archive
    with urllib.request.urlopen(f"https://api.github.com/repos/{repo}/releases/latest", timeout=5) as rsp:
        jsn = json.loads(rsp.read())
    asset = next(ast for ast in jsn["assets"] if re.match(r"adafruit-circuitpython-bundle-py-\d+\.zip", ast["name"]))

    print(f"Downloading {asset['name']} from {jsn['html_url']} to {target_dir}")

    with urllib.request.urlopen(asset["browser_download_url"]) as rsp:
        with zipfile.ZipFile(BytesIO(rsp.read())) as zf:
            with tempfile.TemporaryDirectory() as tmp_dir:
                zf.extractall(tmp_dir)
                # Move the extracted directory to the target directory
                extracted_dir = next(os.scandir(tmp_dir)).path
                shutil.move(extracted_dir, target_dir)


def check_module_requirements(script: Path) -> List[Module]:
    print(f"### Checking module requirements for {script}")

    # The target script will be run on the target device using CircuitPython runtime, not the runtime
    # and environment that this current script is running in. Therefore, do not use default sys.path
    # for importing the modules, but use the CircuitPython library paths.
    finder = ModuleFinder(path=[script.parent.as_posix(), LIB_DIR.as_posix()] +
                               [dp.as_posix() for dp in LIB_DIR.glob("*/lib")])
    finder.run_script(script.as_posix())
    # Enclose modules in helper class and exclude __main__, which is the target script itself.
    modules = [Module.from_module(m) for m in finder.modules.values() if m.__name__ != "__main__"]
    # List the built-in modules for information purposes, but then ignore them as they don't need to be compiled.
    print(f"{script} uses built-in modules: {', '.join(str(m) for m in modules if m.is_built_in)}")
    modules = [m for m in modules if not m.is_built_in]

    print(f"{script} uses CircuitPython modules:"
          f" {', '.join(str(m) for m in modules if not m.package_path)}")
    print(f"{script} uses CircuitPython packages:"
          f" {', '.join(str(m) for m in modules if m.is_package)}")
    print(f"{script} uses CircuitPython package modules:"
          f" {', '.join(str(m) for m in modules if m.package_path and not m.is_package)}")

    return modules


def download_mpy_cross() -> Path:
    bucket_url = "https://adafruit-circuit-python.s3.amazonaws.com/"
    base_prefix = "bin/mpy-cross/"
    web_url = f"{bucket_url}index.html?prefix={base_prefix}"

    mpy_cross = MPY_CROSS_PATH

    if os.access(mpy_cross, os.X_OK):
        print(f"Using existing mpy-cross binary {mpy_cross} (skipping download from {web_url})")
        return mpy_cross

    # Try to get just the file for the current platform. Example file names for version 8.0.5:
    #   mpy-cross-macos-11-8.0.5-arm64
    #   mpy-cross-macos-11-8.0.5-universal
    #   mpy-cross-macos-11-8.0.5-x64
    #   mpy-cross.static-aarch64-8.0.5
    #   mpy-cross.static-amd64-linux-8.0.5
    #   mpy-cross.static-raspbian-8.0.5
    #   mpy-cross.static-x64-windows-8.0.5.exe
    prefix = base_prefix + "mpy-cross" + {
        "Windows": ".static-x64-windows-",
        "Linux": ".static-" + {
            "x86_64": "amd64"
        }.get(platform.machine(), ""),
        "Darwin": f"-macos-{platform.mac_ver()[0].split('.')[0]}",
    }[platform.system()]

    with urllib.request.urlopen(f"{bucket_url}?delimiter=/&prefix={prefix}", timeout=10) as rsp:
        xml = ElementTree.fromstring(rsp.read())

    # Get all file names and parse the version numbers
    files = {}
    for e in xml.iterfind("{*}Contents"):
        m = re.match(r"mpy-cross.+-(\d+)\.(\d+)\.(\d+)", e.find("{*}Key").text.removeprefix(base_prefix))
        files[m.string] = int(int(m.group(1)) * 1e6 + int(m.group(2)) * 1e3 + int(m.group(3)))
    # Only keep the latest version
    latest_version = max(files.values())
    files = [fn for fn, ver in files.items() if ver == latest_version]

    if len(files) != 1:
        exit(f"Could not choose the correct mpy-cross binary for this platform"
             f" ({platform.system()}, {platform.machine()}), found: {files}."
             f" Please add selection logic above or download the binary"
             f" manually from {web_url} and save it as {mpy_cross}")

    url = f"{bucket_url}{base_prefix}{files[0]}"
    print(f"Downloading {url} to {mpy_cross}")

    mpy_cross.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as rsp:
        with open(mpy_cross, "wb") as fp:
            fp.write(rsp.read())
    # Make the file executable
    mpy_cross.chmod(mpy_cross.stat().st_mode | stat.S_IEXEC)

    return mpy_cross


def compile_modules(modules: Collection[Module], debug: bool = False):
    print(f"### Compiling {len(modules)} modules to {COMPILED_DIR}")

    # mpy-cross is used for compiling Python modules to bytecode
    mpy_cross = download_mpy_cross()

    # Mark all existing compiled files for deletion, for cleanup purposes
    files_to_remove = set(COMPILED_DIR.glob("**/*.mpy"))
    # Generate dict of files to compile (in path, out path), mapped to optional compilation process
    compiled_files: Dict[Tuple[Path, Path], subprocess.Popen] = {}

    for module in modules:
        fp_in = module.module_path
        fp_out = COMPILED_DIR.joinpath(module.package_relative).with_suffix(".mpy")
        # Each file present here is required, so it shall not be cleaned afterward
        files_to_remove.discard(fp_out)

        # If the file exists and was not changed since last compilation, skip it
        if fp_out.exists():
            if fp_out.stat().st_mtime == fp_in.stat().st_mtime:
                print(f"Skipping {fp_in} (unchanged)")
                continue
            else:
                print(f"Recompiling {fp_in} to {fp_out} (changed)")
        else:
            print(f"Compiling {fp_in} to {fp_out} (new)")
            # Make sure that the output directory exists
            fp_out.parent.mkdir(parents=True, exist_ok=True)

        compiled_files[fp_in, fp_out] = subprocess.Popen([
            mpy_cross.as_posix(),
            # https://docs.micropython.org/en/latest/library/micropython.html#micropython.opt_level
            "-O0" if debug else "-O3",
            "-o", fp_out.as_posix(),
            fp_in.as_posix()
        ], text=True)

    for (fp_in, fp_out), worker in compiled_files.items():
        worker.wait(5)
        if worker.returncode:
            exit(f"Failed to execute `{' '.join(worker.args)}`: {worker.returncode} ({worker.stderr})")
        # Compilation can take undetermined amount of time, so adjust modification time of the output file
        # to be the same as the input file, to enable skipping unchanged files on subsequent runs.
        os.utime(fp_out, (fp_out.stat().st_atime, fp_in.stat().st_mtime))

        print(f"Compiled {fp_in} to {fp_out} ({fp_out.stat().st_size} bytes)")

    # Cleanup all files that were compiled before but are not required anymore
    for file in files_to_remove:
        print(f"Removing {file} (not used anymore)")
        file.unlink()


def check_circuitpy_drive() -> Optional[Path]:
    if not DEPLOY_DIR_CFG_FILE.is_file():
        DEPLOY_DIR_CFG_FILE.write_text("Specify your CircuitPython drive path here (e.g. /media/CIRCUITPY or I:\\)\n")
        print(f"\nConfiguration file {DEPLOY_DIR_CFG_FILE} did not exist, auto-copy disabled")
        return None

    path = Path(DEPLOY_DIR_CFG_FILE.read_text().strip()).resolve()
    if not path.is_dir():
        print(f"\nConfiguration file {DEPLOY_DIR_CFG_FILE} contains invalid path ({path}), auto-copy disabled")
        return None

    return path


def sync_files(target_drive: Path) -> None:
    main_dir = MAIN_SCRIPT.parent
    files = {
        # All files from the directory containing the main script
        **{fp: target_drive.joinpath(fp.relative_to(main_dir))
           for fp in main_dir.glob("**/*") if fp.is_file()},
        # All compiled files
        **{fp: target_drive.joinpath("lib", fp.relative_to(COMPILED_DIR))
           for fp in COMPILED_DIR.glob("**/*") if fp.is_file()}
    }

    print(f"### Syncing {len(files)} files to {target_drive}")

    for src, dst in files.items():
        if dst.is_file():
            if filecmp.cmp(src, dst):
                print(f"Skipping {src} as it is already deployed")
                continue
            else:
                print(f"Updating {src} -> {dst}")
        else:
            print(f"Deploying {src} -> {dst}")

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main() -> None:
    # No need to follow
    # https://learn.adafruit.com/welcome-to-circuitpython/pycharm-and-circuitpython#creating-a-project-on-a-computers-file-system-3105042
    # as this script copies all required files to the device and keeps them in sync.
    ensure_adafruit_libraries()
    modules = check_module_requirements(MAIN_SCRIPT)
    compile_modules(modules)

    # Optionally copy all files to the device
    target_drive = check_circuitpy_drive()
    if target_drive:
        sync_files(target_drive)


main()
