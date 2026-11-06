"""Absolute handle input through TRAIN CREW's official external-device SDK."""
from pathlib import Path
import queue
import subprocess
import sys
import threading

# TRAIN CREW has six service-brake notches. B7/B8 hold its service maximum.
NOTCHES = {'N': 0, 'EB': -8, **{f'P{i}': i for i in range(1, 6)},
           **{f'B{i}': -(min(i, 6) + 1) for i in range(1, 9)}}
REVERSER = {'F': 1, 'N': 0, 'R': -1}


class TrainCrewBackend:
    def __init__(self):
        self.process = None
        self.notch = 'N'
        self.reverser = 'N'
        self.buttons = 0

    def connect(self):
        if self.process is not None:
            return
        base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1] / 'build'))
        helper = base / 'train_crew/JRController.TrainCrew.exe'
        process = subprocess.Popen([str(helper)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        ready = queue.Queue()
        threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True).start()
        try:
            message = ready.get(timeout=5).strip()
            if message != 'READY':
                raise RuntimeError('TRAIN CREW 官方接口初始化失败：' + message)
        except Exception:
            process.kill(); process.wait()
            process.stdin.close(); process.stdout.close()
            raise
        self.process = process

    def set(self, name):
        if name not in NOTCHES:
            raise ValueError('Invalid notch')
        self.notch = name

    def set_reverser(self, name):
        if name not in REVERSER:
            raise ValueError('Invalid reverser')
        self.reverser = name

    def set_buttons(self, mask):
        if type(mask) is not int or not 0 <= mask <= 15:
            raise ValueError('Invalid button mask')
        self.buttons = mask

    def refresh(self, enabled):
        p = self.process
        if p is None or p.poll() is not None:
            raise RuntimeError('TRAIN CREW 接口进程已退出')
        n, r, b = (NOTCHES[self.notch], REVERSER[self.reverser], self.buttons) if enabled else (-8, 0, 0)
        p.stdin.write(f'{n} {r} {b}\n')
        p.stdin.flush()

    def close(self):
        p, self.process = self.process, None
        if p is None:
            return
        try:
            if p.poll() is None:
                p.stdin.write('-8 0 0\nQUIT\n'); p.stdin.flush()
                p.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            p.kill(); p.wait()
        finally:
            p.stdin.close(); p.stdout.close()
