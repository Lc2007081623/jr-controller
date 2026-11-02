"""Neutral-only offline installation check; no physical serial port is opened."""
import json
from pathlib import Path
import time

from output_profiles import MODES,create_backend
from zuiki_virtual_test import raw_hid_paths
from output_profiles import ZUIKI

def check_installation():
    results=[]
    for mode in MODES:
        pad=create_backend(mode)
        try:
            pad.connect();pad.set('N');pad.set_reverser('N');pad.set_buttons(0)
            if mode==ZUIKI:
                time.sleep(.3)
                if not any('vid_33dd&pid_0006' in path.lower() for path in raw_hid_paths()):
                    raise RuntimeError('Windows 未识别到 Pro 虚拟手柄')
            results.append({'mode':mode,'ok':True})
        except Exception as exc:
            results.append({'mode':mode,'ok':False,'error':str(exc)})
        finally:
            try:pad.close()
            except Exception as exc:results.append({'mode':mode,'ok':False,'error':str(exc)})
        time.sleep(.1)
    return {'ok':all(row['ok'] for row in results),'checks':results}

def write_check(path):
    result=check_installation()
    Path(path).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    return 0 if result['ok'] else 1
