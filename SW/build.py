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
from modulefinder import ModuleFinder
from pathlib import Path
from types import ModuleType
from typing import List, Iterable, Tuple, Dict
from xml.etree import ElementTree

lib_dir = Path("lib")
src_dir = Path("src")
tools_dir = Path("tools")
compiled_dir = Path("compiled")

mpy_cross = tools_dir.joinpath(f"mpy-cross{Path(sys.executable).suffix}").resolve()


def check_dirs() -> None:
    os.makedirs(lib_dir, exist_ok=True)
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(tools_dir, exist_ok=True)
    os.makedirs(compiled_dir, exist_ok=True)


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
    dp = lib_dir.joinpath("adafruit-circuitpython-bundle-py").resolve()

    if not dp.is_dir():
        download_adafruit_bundle(dp)


def check_module_requirements(script_name: str = "code.py") -> List[ModuleType]:
    script = src_dir.joinpath(script_name).resolve()

    # The target script will be run on the target device using CircuitPython runtime,
    # not the runtime and environment that this current script is running in.
    # Therefore, do not use default sys.path for importing the modules!
    finder = ModuleFinder(path=[])
    # Run the script once to get the list of all modules that were imported or attempted to be imported
    finder.run_script(script.as_posix())
    # Successfully imported modules are built-in modules (empty path)
    modules = list(finder.modules.keys())
    print(f"{script} uses built-in modules: {', '.join(m for m in modules if m != '__main__')}")
    # Modules failed to import are most likely CircuitPython libraries

    # Rerun the script with CircuitPython library paths added
    finder = ModuleFinder(path=[script.parent.as_posix(), lib_dir.resolve().as_posix()] +
                               [dp.as_posix() for dp in lib_dir.resolve().glob("*/lib")])
    finder.run_script(script.as_posix())
    # All modules which failed to import initially, but are successfully imported now,
    # are CircuitPython libraries located in the provided library paths.
    required_modules = {name: module for name, module in finder.modules.items() if name not in modules}

    print(f"{script} uses CircuitPython libraries: {', '.join(required_modules)}")

    return list(required_modules.values())


def download_mpy_cross() -> None:
    bucket_url = "https://adafruit-circuit-python.s3.amazonaws.com/"
    base_prefix = "bin/mpy-cross/"
    web_url = f"{bucket_url}index.html?prefix={base_prefix}"

    if os.access(mpy_cross, os.X_OK):
        print(f"Using existing mpy-cross binary {mpy_cross} (skipping download from {web_url})")
        return

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


def compile_modules(modules: Iterable[ModuleType], debug: bool = False) -> List[Path]:
    # mpy-cross is used for compiling Python modules to bytecode
    download_mpy_cross()

    workers: Dict[Tuple[Path, Path], subprocess.Popen] = {}
    for module in modules:
        fp_in = Path(module.__file__)
        fp_out = compiled_dir.joinpath(f"{module.__name__}.mpy").resolve()

        # If the file exists and was not changed since last compilation, skip it
        if fp_out.exists():
            if fp_out.stat().st_mtime == fp_in.stat().st_mtime:
                print(f"Skipping {fp_in} (unchanged)")
                continue
            else:
                print(f"Recompiling {fp_in} to {fp_out} (changed)")
        else:
            print(f"Compiling {fp_in} to {fp_out} (new)")

        workers[fp_in, fp_out] = subprocess.Popen([
            mpy_cross.as_posix(),
            # https://docs.micropython.org/en/latest/library/micropython.html#micropython.opt_level
            "-O0" if debug else "-O3",
            "-o", fp_out.as_posix(),
            fp_in.as_posix()
        ], text=True)

    for (fp_in, fp_out), proc in workers.items():
        proc.wait(5)
        if proc.returncode:
            exit(f"Failed to execute `{' '.join(proc.args)}`: {proc.returncode} ({proc.stderr})")
        # Compilation can take undetermined amount of time, so adjust modification time of the output file
        # to be the same as the input file, to enable skipping unchanged files on subsequent runs.
        os.utime(fp_out, (fp_out.stat().st_atime, fp_in.stat().st_mtime))

        print(f"Compiled {fp_in} to {fp_out} ({fp_out.stat().st_size} bytes)")

    return [fp_out for fp_in, fp_out in workers.keys()]


def main() -> None:
    check_dirs()
    check_adafruit_libraries()
    modules = check_module_requirements()
    mpy_files = compile_modules(modules)


main()
