"""Build offline installer. Run from any directory with Python 3.12 x64."""
import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ICON=ROOT/'installer/hikari.ico'
DRIVER=ROOT/'.local-tools/installer/ViGEmBus_1.22.0_x64_x86_arm64.exe'
# Official v1.22.0 asset, Authenticode verified as Nefarius Software Solutions e.U.
DRIVER_SHA256='89220a7865076b342892f98865f3499fb7c4cfd673159e89d352c360fd014c6a'

def run(*args):
    subprocess.run([sys.executable,*args],cwd=ROOT,check=True)

def build_firmware_update():
    tool_dir = Path(os.environ.get('JR_ESPTOOL_DIR') or
                    Path(os.environ['LOCALAPPDATA']) / 'Arduino15/packages/esp32/tools/esptool_py/5.3.0')
    destination = ROOT / 'build/firmware_update'
    destination.mkdir(parents=True, exist_ok=True)
    config = configparser.ConfigParser(interpolation=None)
    config.read(ROOT / 'firmware/platformio.ini', encoding='utf-8')
    catalog = {}
    series_names = set()
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        staging = Path(temp)
        for section in config.sections():
            target = config[section]
            if not section.startswith('env:') or 'custom_firmware_series' not in target:
                continue
            environment = section.removeprefix('env:')
            series = target['custom_firmware_series']
            model = target['custom_firmware_model']
            version = target['custom_firmware_version']
            if (not re.fullmatch(r'hidari[1-9][0-9]*', series) or series in series_names or model in catalog
                    or not re.fullmatch(r'[A-Z0-9-]{1,32}', model)
                    or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version)):
                raise ValueError(f'Invalid firmware target {section}')
            subprocess.run(['pio', 'run', '-d', 'firmware', '-e', environment], cwd=ROOT, check=True)
            image = (ROOT / 'firmware/.pio/build' / environment / 'firmware.bin').read_bytes()
            if any(value.encode('ascii') + b'\0' not in image for value in (model, version)):
                raise RuntimeError(f'Firmware image metadata does not match {section}')
            (staging / f'{series}-v{version}-app.bin').write_bytes(image)
            catalog[model] = dict(series=series, version=version, sha256=hashlib.sha256(image).hexdigest())
            series_names.add(series)
        if not catalog:
            raise RuntimeError('No firmware update targets configured')
        for filename in ('esptool.exe', 'LICENSE'):
            shutil.copy2(tool_dir / filename, staging / filename)
        (staging / 'Source.txt').write_text(
            'Espressif esptool 5.3.0 source: https://github.com/espressif/esptool/tree/v5.3.0\n', encoding='utf-8')
        files = {file.name for file in staging.iterdir()}
        for name in files:
            (staging / name).replace(destination / name)
        (staging / 'manifest.json').write_text(json.dumps(catalog, indent=2) + '\n', encoding='utf-8')
        (staging / 'manifest.json').replace(destination / 'manifest.json')
        for stale in destination.glob('*-app.bin'):
            if stale.name not in files:
                stale.unlink()


def main():
    os.chdir(ROOT)
    if hashlib.sha256(DRIVER.read_bytes()).hexdigest()!=DRIVER_SHA256:
        raise RuntimeError('Driver installer does not match the verified official asset')
    run('bve_plugin/build.py','--test')
    run('train_crew/build.py')
    build_firmware_update()
    run('-m','unittest','discover','-s','test_tools','-p','test_*.py')
    run('-m','PyInstaller','--noconfirm','--onedir','--windowed','--name','JRController',
        '--icon',str(ICON),'--add-data',str(ICON)+';.',
        '--collect-all','vgamepad','--distpath','release/app','--workpath','build/pyinstaller',
        '--specpath','build','--add-data',str(ROOT/'installer/first_steps.html')+';.',
        '--add-data',str(ROOT/'installer/bve_guide.html')+';.',
        '--add-data',str(ROOT/'installer/train_crew_guide.html')+';.',
        '--add-data',str(ROOT/'build/train_crew')+';train_crew',
        '--add-data',str(ROOT/'build/firmware_update')+';firmware_update',
        'test_tools/controller_app.py')
    bundle=(ROOT/'release/app/JRController').resolve()
    for version in ('BVE5','BVE6'):
        destination=bundle/'BVE Plugins'/version
        destination.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/'build/bve'/version/'JRController.Bve.dll',destination/'JRController.Bve.dll')
    old=(bundle/'_internal/vgamepad/win/vigem/install').resolve()
    if old.exists():
        if not old.is_relative_to(bundle):raise RuntimeError('Unexpected build path')
        shutil.rmtree(old)
    run('installer/third_party_notices.py')
    run('-m','PyInstaller','--noconfirm','--onefile','--windowed','--uac-admin',
        '--icon',str(ICON),'--add-data',str(ICON)+';.',
        '--name','JRControllerSetup','--distpath','release','--workpath','build/setup',
        '--specpath','build','--add-data',str(bundle)+';app',
        '--add-data',str(DRIVER)+';.',
        '--add-data',str(ROOT/'build/ThirdPartyNotices.txt')+';.','installer/setup_app.py')
    result=ROOT/'release/JRControllerSetup.exe'
    digest=hashlib.sha256(result.read_bytes()).hexdigest()
    result.with_suffix('.exe.sha256').write_text(digest+'  '+result.name+'\n',encoding='ascii')
    print(result, result.stat().st_size, digest)

if __name__=='__main__':main()
