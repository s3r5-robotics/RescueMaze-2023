import json
import os
import re
import shutil
import tempfile
import urllib.request
import zipfile
from io import BytesIO
from modulefinder import ModuleFinder
from pathlib import Path
from types import ModuleType
from typing import List

lib_dir = Path("lib")
src_dir = Path("src")
tools_dir = Path("tools")
compiled_dir = Path("compiled")


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


check_dirs()
check_adafruit_libraries()
check_module_requirements()
