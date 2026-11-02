"""Collect notices from the exact installed dependencies used in this build."""
from importlib.metadata import distribution
from pathlib import Path

parts=['JR Controller third-party notices\n\nViGEmBus 1.22.0: https://github.com/nefarius/ViGEmBus\n']
parts.append(Path('.local-tools/installer/ViGEmBus-LICENSE.txt').read_text(encoding='utf-8'))
for name in ('vgamepad','pyserial','pyinstaller'):
    package=distribution(name)
    parts.append('\n\n'+name+' '+package.version+'\n')
    for file in package.files or ():
        if any(word in file.name.lower() for word in ('license','copying','notice')):
            parts.append(package.locate_file(file).read_text(encoding='utf-8',errors='replace'))
import sys
parts.append('\n\nPython\n'+Path(sys.base_prefix,'LICENSE.txt').read_text(encoding='utf-8'))
Path('build/ThirdPartyNotices.txt').write_text('\n'.join(parts),encoding='utf-8')
