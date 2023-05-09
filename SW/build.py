import filecmp
import json
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
from modulefinder import ModuleFinder, Module
from pathlib import Path
from typing import List, Iterable, Tuple, Dict, Optional, Collection
from xml.etree import ElementTree

LIB_DIR = Path("lib").resolve()
SRC_DIR = Path("src").resolve()
TOOLS_DIR = Path("tools").resolve()
COMPILED_DIR = Path("compiled", "lib").resolve()
DEPLOY_DIR_CFG_FILE = Path("circuitpy_drive.txt").resolve()


def check_dirs() -> None:
    os.makedirs(LIB_DIR, exist_ok=True)
    os.makedirs(SRC_DIR, exist_ok=True)
    os.makedirs(TOOLS_DIR, exist_ok=True)
    os.makedirs(COMPILED_DIR, exist_ok=True)


def download_adafruit_bundle(target_dir: Path, repo: str = "adafruit/Adafruit_CircuitPython_Bundle") -> None:
    # Get URL of the latest release archive
    with urllib.request.urlopen(f"https://api.github.com/repos/{repo}/releases/latest", timeout=5) as rsp:
        jsn = json.loads(rsp.read())
    asset = next(ast for ast in jsn["assets"] if re.match(r"adafruit-circuitpython-bundle-py-\d+\.zip", ast["name"]))

    print(f"Downloading {asset['name']} from {jsn['html_url']} to {target_dir}")

    with urllib.request.urlopen(asset["browser_download_url"]) as rsp:
        with zipfile.ZipFile(BytesIO(rsp.read())) as zf:
            with tempfile.TemporaryDirectory() as tmp_dir:
                zf.extractall(tmp_dir)
                shutil.move(next(os.scandir(tmp_dir)), target_dir)


def check_adafruit_libraries() -> None:
    dp = LIB_DIR.joinpath("adafruit-circuitpython-bundle-py")

    if not dp.is_dir():
        download_adafruit_bundle(dp)


def check_module_requirements(script: Path) -> List[Module]:
    print(f"### Checking module requirements for {script}")

    # The target script will be run on the target device using CircuitPython runtime, not the runtime
    # and environment that this current script is running in. Therefore, do not use default sys.path
    # for importing the modules, but use the CircuitPython library paths.
    finder = ModuleFinder(path=[script.parent.as_posix(), LIB_DIR.as_posix()] +
                               [dp.as_posix() for dp in LIB_DIR.glob("*/lib")])
    finder.run_script(script.as_posix())
    # All "non-file" modules are built-in modules
    print(f"{script} uses built-in modules: {', '.join(m.__name__ for m in finder.modules.values() if not m.__file__)}")
    # Others are CircuitPython libraries, which can either be single file or a directory
    modules = [m for m in finder.modules.values() if m.__file__ and m.__name__ != "__main__"]

    print(f"{script} uses CircuitPython libraries: {', '.join(m.__name__ for m in modules)}")

    return modules


def download_mpy_cross() -> Path:
    bucket_url = "https://adafruit-circuit-python.s3.amazonaws.com/"
    base_prefix = "bin/mpy-cross/"
    web_url = f"{bucket_url}index.html?prefix={base_prefix}"

    # Use the same extension as the current Python executable to ensure simple cross-platform usage
    mpy_cross = TOOLS_DIR.joinpath(f"mpy-cross{Path(sys.executable).suffix}")

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

    with urllib.request.urlopen(url) as rsp:
        with open(mpy_cross, "wb") as fp:
            fp.write(rsp.read())
    # Make the file executable
    mpy_cross.chmod(mpy_cross.stat().st_mode | stat.S_IEXEC)

    return mpy_cross


def get_module_paths(modules: Collection[Module]) -> Iterable[Tuple[Path, Path]]:
    for module in sorted(modules, key=lambda m: m.__file__):
        fp_in = Path(module.__file__).resolve()

        # Directory structure of the compiled modules must stay the same as the original modules!
        if module.__name__ != fp_in.stem:
            # This is a package, keep the directory structure
            sub_dirs = module.__name__.split(".")
            # If the last part is the same as the file name (instead of __init__),
            # then this is the module inside a package - remove it as subdir.
            if sub_dirs[-1] == fp_in.stem:
                sub_dirs.pop()
        else:
            # This is a single-file module
            sub_dirs = []

        fp_out = COMPILED_DIR.joinpath(*sub_dirs, fp_in.stem + ".mpy")

        yield fp_in, fp_out


def compile_modules(modules: Collection[Module], debug: bool = False) -> List[Path]:
    print(f"### Compiling {len(modules)} modules to {COMPILED_DIR}")

    # mpy-cross is used for compiling Python modules to bytecode
    mpy_cross = download_mpy_cross()

    existing_files = COMPILED_DIR.glob("**/*.mpy")

    workers: Dict[Tuple[Path, Path], Optional[subprocess.Popen]] = {}
    for fp_in, fp_out in get_module_paths(modules):
        # If the file exists and was not changed since last compilation, skip it
        if fp_out.exists():
            if fp_out.stat().st_mtime == fp_in.stat().st_mtime:
                print(f"Skipping {fp_in} (unchanged)")
                workers[fp_in, fp_out] = None
                continue
            else:
                print(f"Recompiling {fp_in} to {fp_out} (changed)")
        else:
            print(f"Compiling {fp_in} to {fp_out} (new)")

        # Make sure that the output directory exists
        fp_out.parent.mkdir(parents=True, exist_ok=True)

        workers[fp_in, fp_out] = subprocess.Popen([
            mpy_cross.as_posix(),
            # https://docs.micropython.org/en/latest/library/micropython.html#micropython.opt_level
            "-O0" if debug else "-O3",
            "-o", fp_out.as_posix(),
            fp_in.as_posix()
        ], text=True)

    for (fp_in, fp_out), proc in workers.items():
        if not proc:
            continue
        proc.wait(5)
        if proc.returncode:
            exit(f"Failed to execute `{' '.join(proc.args)}`: {proc.returncode} ({proc.stderr})")
        # Compilation can take undetermined amount of time, so adjust modification time of the output file
        # to be the same as the input file, to enable skipping unchanged files on subsequent runs.
        os.utime(fp_out, (fp_out.stat().st_atime, fp_in.stat().st_mtime))

        print(f"Compiled {fp_in} to {fp_out} ({fp_out.stat().st_size} bytes)")

    compiled_files = [fp_out for fp_in, fp_out in workers.keys()]

    for file in sorted(set(existing_files) - set(compiled_files)):
        print(f"Removing {file} (not used anymore)")
        file.unlink()

    return compiled_files


def check_circuitpy_drive() -> Optional[Path]:
    if not DEPLOY_DIR_CFG_FILE.is_file():
        DEPLOY_DIR_CFG_FILE.write_text("Specify your CircuitPython drive path here (e.g. /media/CIRCUITPY or I:\\)\n")
        print(f"Configuration file {DEPLOY_DIR_CFG_FILE} did not exist, auto-copy disabled")
        return None

    path = Path(DEPLOY_DIR_CFG_FILE.read_text().strip()).resolve()
    if not path.is_dir():
        print(f"Configuration file {DEPLOY_DIR_CFG_FILE} contains invalid path ({path}), auto-copy disabled")
        return None

    return path


def sync_files(sources: Iterable[Path], libs: Iterable[Path], target_drive: Path) -> None:
    files = {
        **{fp: target_drive.joinpath(fp.name) for fp in sources},
        **{fp: target_drive.joinpath("lib", fp.name) for fp in libs}
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

        shutil.copy2(src, dst)


def main() -> None:
    # No need to follow
    # https://learn.adafruit.com/welcome-to-circuitpython/pycharm-and-circuitpython#creating-a-project-on-a-computers-file-system-3105042
    # as this script copies all required files to the device and keeps them in sync.
    main_script = SRC_DIR.joinpath("code.py")
    boot_script = SRC_DIR.joinpath("boot.py")

    check_dirs()
    check_adafruit_libraries()
    modules = check_module_requirements(main_script)
    mpy_files = compile_modules(modules)

    # Optionally cpy all files to the device
    target_drive = check_circuitpy_drive()
    if target_drive:
        sync_files([main_script, boot_script], mpy_files, target_drive)


main()
