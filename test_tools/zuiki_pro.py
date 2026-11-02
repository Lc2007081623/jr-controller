"""RUNNING TRAIN compatibility mapping verified with the physical C3 controller."""
from zuiki_virtual_test import ZuikiVirtual

VID,PID=0x33dd,0x0006
REVERSER_BYTES={'F':128,'N':0,'R':255}

class ZuikiProVirtual(ZuikiVirtual):
    def __init__(self):
        super().__init__(VID,PID)

    def set(self,notch,buttons=0,reverser='N'):
        if reverser not in REVERSER_BYTES:raise ValueError('Invalid reverser')
        # shortcut: ViGEm still exposes a DS4 descriptor; game compatibility is tested.
        self.report.bThumbRY=REVERSER_BYTES[reverser]
        super().set(notch,buttons,'N')
