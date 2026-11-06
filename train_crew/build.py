"""Build the small .NET bridge against the unmodified official TRAIN CREW SDK."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent


def main():
    sdk = ROOT / 'sdk/TrainCrewInput.dll'
    if hashlib.sha256(sdk.read_bytes()).hexdigest() != 'ab0c63b8ca309bdfb51c1a4046e33dcfca780841c5729fbdcc5917a73f261bea':
        raise RuntimeError('TRAIN CREW SDK does not match the official 2025-11-16 download')
    output = ROOT.parent / 'build/train_crew'
    output.mkdir(parents=True, exist_ok=True)
    compiler = Path(os.environ['WINDIR']) / 'Microsoft.NET/Framework/v4.0.30319/csc.exe'
    subprocess.run([str(compiler), '/nologo', '/optimize+', '/target:exe',
                    '/platform:anycpu', '/reference:System.Web.Extensions.dll',
                    '/reference:' + str(sdk), '/out:' + str(output / 'JRController.TrainCrew.exe'),
                    str(ROOT / 'Bridge.cs')], check=True)
    shutil.copy2(sdk, output / sdk.name)
    print('Official SDK SHA256:', hashlib.sha256(sdk.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
