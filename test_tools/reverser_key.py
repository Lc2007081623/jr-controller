"""A short Up-arrow pulse, restricted to the game foreground process."""
import ctypes as C
from ctypes import wintypes as W
from pathlib import PureWindowsPath

ULONG_PTR=C.c_size_t
class MouseInput(C.Structure):
    _fields_=[('dx',W.LONG),('dy',W.LONG),('mouseData',W.DWORD),('flags',W.DWORD),
              ('time',W.DWORD),('extra',ULONG_PTR)]
class KeyInput(C.Structure):
    _fields_=[('vk',W.WORD),('scan',W.WORD),('flags',W.DWORD),('time',W.DWORD),('extra',ULONG_PTR)]
class HardwareInput(C.Structure):
    _fields_=[('msg',W.DWORD),('low',W.WORD),('high',W.WORD)]
class Payload(C.Union):
    _fields_=[('mouse',MouseInput),('key',KeyInput),('hardware',HardwareInput)]
class Input(C.Structure):
    _fields_=[('type',W.DWORD),('payload',Payload)]

class ReverserKey:
    def __init__(self):
        self.user=C.WinDLL('user32',use_last_error=True)
        self.kernel=C.WinDLL('kernel32',use_last_error=True)
        self.user.GetForegroundWindow.restype=W.HWND
        self.user.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
        self.user.SendInput.argtypes=[W.UINT,C.POINTER(Input),C.c_int]
        self.user.SendInput.restype=W.UINT
        self.kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD]
        self.kernel.OpenProcess.restype=W.HANDLE
        self.kernel.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]
        self.kernel.CloseHandle.argtypes=[W.HANDLE]
        self.held=False;self.release_at=0

    def game_foreground(self):
        pid=W.DWORD()
        self.user.GetWindowThreadProcessId(self.user.GetForegroundWindow(),C.byref(pid))
        handle=self.kernel.OpenProcess(0x1000,False,pid.value)
        if not handle:return False
        try:
            size=W.DWORD(32768);buffer=C.create_unicode_buffer(size.value)
            if not self.kernel.QueryFullProcessImageNameW(handle,0,buffer,C.byref(size)):return False
            return PureWindowsPath(buffer.value).name.casefold()=='jreast_trainsimulator.exe'
        finally:self.kernel.CloseHandle(handle)

    def send(self,release):
        event=Input();event.type=1
        # Up arrow uses an extended scan code. Never hold it across disconnect.
        event.payload.key=KeyInput(0,0x48,0x0008|0x0001|(0x0002 if release else 0),0,0)
        if self.user.SendInput(1,C.byref(event),C.sizeof(event))!=1:
            raise OSError(C.get_last_error(),'SendInput failed')

    def request(self,now):
        if self.held:return 'ignored: previous pulse active'
        if not self.game_foreground():return 'ignored: game is not foreground'
        self.send(False);self.held=True;self.release_at=now+.12
        return 'sent: reverser forward / Up (confirm game HUD)'

    def release(self):
        if self.held:
            self.send(True);self.held=False

    def tick(self,now):
        if self.held and now>=self.release_at:self.release()
