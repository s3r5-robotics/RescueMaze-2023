import json
import os
import re
import shutil
import tempfile
import urllib.request
import zipfile
from io import BytesIO
from pathlib import Path

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


check_dirs()
check_adafruit_libraries()
