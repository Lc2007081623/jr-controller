"""Read-only game input selector inspection; no process memory writes."""
import ctypes as C
from ctypes import wintypes as W
import json,struct,hashlib
from pathlib import Path

EXPECTED_GAME_SHA256='7d04aca24bf4ce2c118afd7861be2f4e6308b0403138325e82b002ae37bb0706'

class ProcessEntry(C.Structure):
    _fields_=[('size',W.DWORD),('usage',W.DWORD),('pid',W.DWORD),('heap',C.c_size_t),
              ('module',W.DWORD),('threads',W.DWORD),('parent',W.DWORD),
              ('priority',W.LONG),('flags',W.DWORD),('name',W.WCHAR*260)]
class ModuleEntry(C.Structure):
    _fields_=[('size',W.DWORD),('module',W.DWORD),('pid',W.DWORD),('global_usage',W.DWORD),
              ('process_usage',W.DWORD),('base',C.c_void_p),('base_size',W.DWORD),
              ('handle',W.HMODULE),('name',W.WCHAR*256),('path',W.WCHAR*260)]

def inspect():
    k=C.WinDLL('kernel32',use_last_error=True)
    k.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD];k.CreateToolhelp32Snapshot.restype=W.HANDLE
    k.CloseHandle.argtypes=[W.HANDLE]
    k.Process32FirstW.argtypes=[W.HANDLE,C.POINTER(ProcessEntry)]
    k.Process32NextW.argtypes=[W.HANDLE,C.POINTER(ProcessEntry)]
    k.Module32FirstW.argtypes=[W.HANDLE,C.POINTER(ModuleEntry)]
    k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
    k.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]
    h=k.CreateToolhelp32Snapshot(2,0);p=ProcessEntry();p.size=C.sizeof(p);found=[]
    try:
        ok=k.Process32FirstW(h,C.byref(p))
        while ok:
            if 'train' in p.name.lower() or 'jreast' in p.name.lower():found.append((p.pid,p.name))
            ok=k.Process32NextW(h,C.byref(p))
    finally:k.CloseHandle(h)
    records=[]
    for pid,name in found:
        rec={'pid':pid,'name':name}
        if name.lower()!='jreast_trainsimulator.exe':records.append(rec);continue
        snapshot=k.CreateToolhelp32Snapshot(0x18,pid);m=ModuleEntry();m.size=C.sizeof(m)
        try:
            if not k.Module32FirstW(snapshot,C.byref(m)):
                rec['error']='module enumeration failed '+str(C.get_last_error());records.append(rec);continue
            base=m.base;rec.update(base=hex(base),path=m.path)
        finally:k.CloseHandle(snapshot)
        try:
            if hashlib.sha256(Path(m.path).read_bytes()).hexdigest()!=EXPECTED_GAME_SHA256:
                rec['error']='Game build differs from the analyzed binary; refusing to interpret offsets.'
                records.append(rec);continue
        except OSError as e:
            rec['error']='Cannot identify game build: '+str(e);records.append(rec);continue
        hp=k.OpenProcess(0x1010,False,pid)
        if not hp:rec['error']='read-only process open failed '+str(C.get_last_error());records.append(rec);continue
        try:
            for label,rva in [('layout_selector',0x16dd1ac),('input_type_selector',0x16dfca8),('vehicle_selector',0x16dca74)]:
                buf=C.create_string_buffer(4);read=C.c_size_t()
                if k.ReadProcessMemory(hp,C.c_void_p(base+rva),buf,4,C.byref(read)) and read.value==4:
                    rec[label]=struct.unpack('<i',buf.raw)[0]
                else:rec[label]='unreadable '+str(C.get_last_error())
        finally:k.CloseHandle(hp)
        records.append(rec)
    return {'processes':records,'note':'Selectors inferred from this specific game binary; read-only.'}

if __name__=='__main__':print(json.dumps(inspect(),ensure_ascii=False,indent=2))
