"""Game output selection shared by the desktop app and its tests."""
import json
import os
from pathlib import Path

from xinput_notch_test import Backend
from zuiki_pro import ZuikiProVirtual
from bve_output import BveBackend
from train_crew_output import TrainCrewBackend

XBOX='JR EAST（Xbox）'
ZUIKI='RUNNING TRAIN（ZUIKI）'
BVE='BVE 5/6（专用插件）'
TRAIN_CREW='TRAIN CREW（官方接口）'
MODES=(XBOX,ZUIKI,BVE,TRAIN_CREW)

def settings_path():
    return Path(os.environ.get('LOCALAPPDATA',Path.home()))/'JRController'/'settings.json'

def load_settings():
    try:
        values = json.loads(settings_path().read_text(encoding='utf-8'))
        return values if isinstance(values, dict) else {}
    except (OSError, ValueError):
        return {}

def save_settings(**changes):
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(load_settings() | changes, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)

def load_mode():
    mode = load_settings().get('game_mode')
    return mode if mode in MODES else XBOX

def save_mode(mode):
    if mode not in MODES:
        raise ValueError('Unknown game mode')
    save_settings(game_mode=mode)

class ZuikiBackend:
    """Verified Pro handle, buttons and absolute reverser output."""
    def __init__(self):
        self.pad=None;self.notch='N';self.buttons=0;self.reverser='N'

    def connect(self):
        if self.pad is None:self.pad=ZuikiProVirtual()

    def _report(self):
        if self.pad is None:raise RuntimeError('Virtual controller is not connected')
        self.pad.set(self.notch,self.buttons,self.reverser)

    def set(self,name):
        self.notch=name;self._report()

    def set_buttons(self,mask):
        if mask!=self.buttons:
            self.buttons=mask;self._report()

    def set_reverser(self,name):
        if name not in ('F','N','R'):raise ValueError('Invalid reverser')
        self.reverser=name
        self._report()

    def close(self):
        pad,self.pad=self.pad,None
        if pad:
            try:pad.set('N',0,'N')
            finally:pad.close()

def create_backend(mode):
    if mode==TRAIN_CREW:return TrainCrewBackend()
    if mode==BVE:return BveBackend()
    if mode==ZUIKI:return ZuikiBackend()
    if mode==XBOX:return Backend()
    raise ValueError('Unknown game mode')
