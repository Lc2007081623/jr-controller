"""Build offline installer. Run from any directory with Python 3.12 x64."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
DRIVER=ROOT/'.local-tools/installer/ViGEmBus_1.22.0_x64_x86_arm64.exe'
# Official v1.22.0 asset, Authenticode verified as Nefarius Software Solutions e.U.
DRIVER_SHA256='89220a7865076b342892f98865f3499fb7c4cfd673159e89d352c360fd014c6a'

def run(*args):
    subprocess.run([sys.executable,*args],cwd=ROOT,check=True)

def main():
    os.chdir(ROOT)
    if hashlib.sha256(DRIVER.read_bytes()).hexdigest()!=DRIVER_SHA256:
        raise RuntimeError('Driver installer does not match the verified official asset')
    run('-m','unittest','discover','-s','test_tools','-p','test_*.py')
    run('-m','PyInstaller','--noconfirm','--onedir','--windowed','--name','JRController',
        '--collect-all','vgamepad','--distpath','release/app','--workpath','build/pyinstaller',
        '--specpath','build','test_tools/controller_app.py')
    bundle=(ROOT/'release/app/JRController').resolve()
    old=(bundle/'_internal/vgamepad/win/vigem/install').resolve()
    if old.exists():
        if not old.is_relative_to(bundle):raise RuntimeError('Unexpected build path')
        shutil.rmtree(old)
    run('installer/third_party_notices.py')
    run('-m','PyInstaller','--noconfirm','--onefile','--windowed','--uac-admin',
        '--name','JRControllerSetup','--distpath','release','--workpath','build/setup',
        '--specpath','build','--add-data',str(bundle)+';app',
        '--add-data',str(DRIVER)+';.',
        '--add-data',str(ROOT/'build/ThirdPartyNotices.txt')+';.','installer/setup_app.py')
    result=ROOT/'release/JRControllerSetup.exe'
    digest=hashlib.sha256(result.read_bytes()).hexdigest()
    result.with_suffix('.exe.sha256').write_text(digest+'  '+result.name+'\n',encoding='ascii')
    print(result, result.stat().st_size, digest)

if __name__=='__main__':main()
