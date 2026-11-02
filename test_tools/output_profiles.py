"""Game output selection shared by the desktop app and its tests."""
import json
import os
from pathlib import Path

from xinput_notch_test import Backend
from zuiki_virtual_test import ZuikiVirtual

XBOX='JR EAST（Xbox）'
ZUIKI='RUNNING TRAIN（ZUIKI）'
MODES=(XBOX,ZUIKI)

def settings_path():
    return Path(os.environ.get('LOCALAPPDATA',Path.home()))/'JRController'/'settings.json'

def load_mode():
    try:
        mode=json.loads(settings_path().read_text(encoding='utf-8'))['game_mode']
        return mode if mode in MODES else XBOX
    except (OSError,ValueError,KeyError,TypeError):return XBOX

def save_mode(mode):
    if mode not in MODES:raise ValueError('Unknown game mode')
    path=settings_path();path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps({'game_mode':mode},ensure_ascii=False),encoding='utf-8')
    temp.replace(path)

class ZuikiBackend:
    """Use the tested handle/buttons; reverser remains unverified and is not sent."""
    def __init__(self):
        self.pad=None;self.notch='N';self.buttons=0;self.reverser='N'

    def connect(self):
        if self.pad is None:self.pad=ZuikiVirtual()

    def _report(self):
        if self.pad is None:raise RuntimeError('Virtual controller is not connected')
        # shortcut: neutral hat until RUNNING TRAIN reverser mapping is verified.
        self.pad.set(self.notch,self.buttons,'N')

    def set(self,name):
        self.notch=name;self._report()

    def set_buttons(self,mask):
        if mask!=self.buttons:
            self.buttons=mask;self._report()

    def set_reverser(self,name):
        self.reverser=name

    def close(self):
        pad,self.pad=self.pad,None
        if pad:
            try:pad.set('N',0,'N')
            finally:pad.close()

def create_backend(mode):
    if mode==ZUIKI:return ZuikiBackend()
    if mode==XBOX:return Backend()
    raise ValueError('Unknown game mode')
