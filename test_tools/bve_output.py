"""Local shared-memory output for the BVE 5/6 input device plugin."""
import ctypes
import mmap
import struct

from serial_protocol import NOTCH_ORDER

MAP_NAME = r'Local\JRController.BVE.v1'
MAGIC = 0x4A524256
PACKET = struct.Struct('<IIIiiiiI')


class BveBackend:
    def __init__(self):
        self.memory = None
        self.notch = 'N'
        self.reverser = 'N'
        self.buttons = 0
        self.sequence = 0

    def connect(self):
        if self.memory is None:
            self.memory = mmap.mmap(-1, PACKET.size, tagname=MAP_NAME)

    def set(self, name):
        if name not in NOTCH_ORDER:
            raise ValueError('Invalid BVE notch')
        self.notch = name

    def set_reverser(self, name):
        if name not in ('F', 'N', 'R'):
            raise ValueError('Invalid BVE reverser')
        self.reverser = name

    def set_buttons(self, mask):
        if type(mask) is not int or not 0 <= mask <= 15:
            raise ValueError('Invalid BVE buttons')
        self.buttons = mask

    def refresh(self, enabled):
        if self.memory is None:
            raise RuntimeError('BVE output is not connected')
        self.sequence = (self.sequence + 2) & 0xffffffff
        notch = NOTCH_ORDER.index(self.notch) - 9
        tick = ctypes.windll.kernel32.GetTickCount() & 0xffffffff
        # Publish odd first, then payload and matching even sequence last.
        self.memory[0:4] = struct.pack('<I', self.sequence | 1)
        packet = PACKET.pack(self.sequence, MAGIC, tick, notch,
                             {'F': 1, 'N': 0, 'R': -1}[self.reverser],
                             self.buttons, int(bool(enabled)), self.sequence)
        self.memory[4:] = packet[4:]
        self.memory[0:4] = packet[:4]

    def close(self):
        if self.memory is not None:
            try:
                self.refresh(False)
            finally:
                self.memory.close()
                self.memory = None
