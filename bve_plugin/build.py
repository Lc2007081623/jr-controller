"""Build both BVE architectures using the installed .NET Framework compilers."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bve5',default='D:/bve')
    parser.add_argument('--bve6',default='D:/BVE6')
    parser.add_argument('--test',action='store_true')
    args=parser.parse_args()
    source=Path(__file__).resolve().parent
    for version,game,framework,arch in (('BVE5',args.bve5,'v3.5','x86'),('BVE6',args.bve6,'v4.0.30319','x64')):
        output=source.parent/'build/bve'/version;output.mkdir(parents=True,exist_ok=True)
        api=Path(game)/'Mackoy.IInputDevice.dll'
        compiler=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework'/framework/'csc.exe'
        common=[str(compiler),'/nologo','/optimize+',f'/platform:{arch}',f'/reference:{api}','/reference:System.Windows.Forms.dll']
        subprocess.run([*common,'/target:library',f'/out:{output / "JRController.Bve.dll"}',str(source/'JRController.cs')],check=True)
        if args.test:
            shutil.copy2(api,output/api.name)
            executable=output/'PluginTests.exe'
            subprocess.run([*common,'/define:TEST','/target:exe',f'/out:{executable}',str(source/'JRController.cs'),str(source/'PluginTests.cs')],check=True)
            subprocess.run([str(executable)],check=True)


if __name__=='__main__':main()
