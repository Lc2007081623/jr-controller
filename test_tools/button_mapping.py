"""Route the four calibrated controller buttons to Windows inputs."""
import ctypes as C
from ctypes import wintypes as W

from reverser_key import Input, KeyInput


BUTTONS = tuple('ABXY')
XBOX_BUTTONS = {
    'A': 0x1000, 'B': 0x2000, 'X': 0x4000, 'Y': 0x8000,
    'LB': 0x0100, 'RB': 0x0200, 'Back': 0x0020, 'Start': 0x0010,
    'LS': 0x0040, 'RS': 0x0080,
    '方向键 ↑': 0x0001, '方向键 ↓': 0x0002, '方向键 ←': 0x0004, '方向键 →': 0x0008,
}
KEY_CODES = {
    **{char: ord(char) for char in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'},
    **{f'F{i}': 0x6F + i for i in range(1, 25)},
    **{f'小键盘 {i}': 0x60 + i for i in range(10)},
    'Space': 0x20, 'Enter': 0x0D, 'Tab': 0x09, 'Esc': 0x1B, 'Backspace': 0x08,
    '↑': 0x26, '↓': 0x28, '←': 0x25, '→': 0x27,
    'Home': 0x24, 'End': 0x23, 'Page Up': 0x21, 'Page Down': 0x22,
    'Insert': 0x2D, 'Delete': 0x2E, 'Print Screen': 0x2C, 'Pause': 0x13,
    '左 Shift': 0xA0, '右 Shift': 0xA1, '左 Ctrl': 0xA2, '右 Ctrl': 0xA3,
    '左 Alt': 0xA4, '右 Alt': 0xA5, '左 Win': 0x5B, '右 Win': 0x5C,
    'Caps Lock': 0x14, 'Num Lock': 0x90, 'Scroll Lock': 0x91,
    '小键盘 *': 0x6A, '小键盘 +': 0x6B, '小键盘 -': 0x6D,
    '小键盘 .': 0x6E, '小键盘 /': 0x6F,
    ';': 0xBA, '=': 0xBB, ',': 0xBC, '-': 0xBD, '.': 0xBE, '/': 0xBF,
    '`': 0xC0, '[': 0xDB, '\\': 0xDC, ']': 0xDD, "'": 0xDE,
}
TARGET_LABELS = {
    'default': '游戏默认', 'off': '禁用',
    **{f'xbox:{name}': f'Xbox 360 · {name}' for name in (*XBOX_BUTTONS, 'LT', 'RT')},
    **{f'key:{name}': f'键盘 · {name}' for name in KEY_CODES},
}


def button_mapping(value):
    if not isinstance(value, dict):
        return {}
    return {button: target for button, target in value.items()
            if button in BUTTONS and isinstance(target, str) and target in TARGET_LABELS}


def mapped_outputs(pressed, mapping, xbox_mode):
    native = xbox = triggers = 0
    keys = set()
    for index, button in enumerate(BUTTONS):
        bit = 1 << index
        if not pressed & bit:
            continue
        kind, _, name = mapping.get(button, 'default').partition(':')
        if kind == 'key':
            keys.add(KEY_CODES[name])
        elif kind == 'default' or (kind == 'xbox' and not xbox_mode):
            native |= bit
        elif kind == 'xbox':
            if name == 'LT':
                triggers |= 1
            elif name == 'RT':
                triggers |= 2
            else:
                xbox |= XBOX_BUTTONS[name]
    return native, xbox | (native << 12), triggers, keys


class KeyboardOutput:
    def __init__(self):
        self.held = set()
        self.user = None

    def send(self, key, release):
        if self.user is None:
            self.user = C.WinDLL('user32', use_last_error=True)
            self.user.SendInput.argtypes = [W.UINT, C.POINTER(Input), C.c_int]
            self.user.SendInput.restype = W.UINT
            self.user.MapVirtualKeyW.argtypes = [W.UINT, W.UINT]
            self.user.MapVirtualKeyW.restype = W.UINT
        scan = self.user.MapVirtualKeyW(key, 4)
        flags = 2 if release else 0
        event = Input()
        event.type = 1
        if scan and scan >> 8 in (0, 0xE0):
            event.payload.key = KeyInput(0, scan & 0xFF, flags | 8 | (scan >> 8 == 0xE0), 0, 0)
        else:
            event.payload.key = KeyInput(key, 0, flags, 0, 0)
        if self.user.SendInput(1, C.byref(event), C.sizeof(event)) != 1:
            raise OSError(C.get_last_error(), 'SendInput failed')

    def update(self, keys):
        failure = None
        for key in sorted(self.held - keys):
            try:
                self.send(key, release=True)
                self.held.remove(key)
            except OSError as exc:
                failure = exc
        if failure is not None:
            raise failure
        for key in sorted(keys - self.held):
            self.send(key, release=False)
            self.held.add(key)
