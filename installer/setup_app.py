"""Offline Windows installer, built with the same PyInstaller tool as the app."""
import ctypes
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import ttk
import winreg

APP_NAME='JR Controller'
UNINSTALL_KEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\JRController'
RUN_KEY=r'Software\Microsoft\Windows\CurrentVersion\Run'

def install_directory():
    return Path(os.environ['ProgramW6432'])/APP_NAME

def driver_installed():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SYSTEM\CurrentControlSet\Services\ViGEmBus'):return True
    except FileNotFoundError:return False

def driver_result(code):
    if code not in (0,1641,3010):raise RuntimeError(f'驱动安装失败（{code}），请重新运行安装程序')
    return code in (1641,3010)

def shortcut_paths():
    return (Path(os.environ['PUBLIC'])/'Desktop'/'JR Controller.lnk',
            Path(os.environ['ProgramData'])/'Microsoft/Windows/Start Menu/Programs/JR Controller.lnk')

def shortcut(path,target):
    # Pass paths as arguments, never interpolate them into executable script text.
    script='Set s=CreateObject("WScript.Shell").CreateShortcut(WScript.Arguments(0))\n'
    script+='s.TargetPath=WScript.Arguments(1)\ns.WorkingDirectory=WScript.Arguments(2)\ns.Save\n'
    with tempfile.TemporaryDirectory(prefix='JRShortcut-') as temp:
        file=Path(temp)/'shortcut.vbs';file.write_text(script,encoding='ascii')
        subprocess.run([str(Path(os.environ['WINDIR'])/'System32/cscript.exe'),'//nologo',str(file),str(path),str(target),str(target.parent)],check=True,creationflags=subprocess.CREATE_NO_WINDOW)

def is_running():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenMutexW.argtypes=[ctypes.c_ulong,ctypes.c_bool,ctypes.c_wchar_p];kernel.OpenMutexW.restype=ctypes.c_void_p
    handle=kernel.OpenMutexW(0x100000,False,'Local\\JRController')
    if handle:
        kernel.CloseHandle.argtypes=[ctypes.c_void_p];kernel.CloseHandle(handle)
    return bool(handle)

def install(payload,startup,progress):
    if is_running():raise RuntimeError('请先退出正在运行的 JR 控制器，再点击安装')
    reboot=False
    if not driver_installed():
        progress('正在安装手柄驱动…')
        result=subprocess.run([str(payload/'ViGEmBus_1.22.0_x64_x86_arm64.exe'),'/quiet','/norestart'],creationflags=subprocess.CREATE_NO_WINDOW)
        reboot=driver_result(result.returncode)
    progress('正在安装控制器程序…')
    target=install_directory();target.mkdir(parents=True,exist_ok=True)
    shutil.copytree(payload/'app',target,dirs_exist_ok=True)
    shutil.copy2(payload/'ThirdPartyNotices.txt',target/'ThirdPartyNotices.txt')
    shutil.copy2(sys.executable,target/'Uninstall.exe')
    for path in shortcut_paths():shortcut(path,target/'JRController.exe')
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE,RUN_KEY,0,winreg.KEY_SET_VALUE|winreg.KEY_WOW64_64KEY) as key:
        if startup:winreg.SetValueEx(key,'JRController',0,winreg.REG_SZ,f'"{target / "JRController.exe"}" --background')
        else:
            try:winreg.DeleteValue(key,'JRController')
            except FileNotFoundError:pass
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE,UNINSTALL_KEY,0,winreg.KEY_SET_VALUE|winreg.KEY_WOW64_64KEY) as key:
        for name,value in {'DisplayName':APP_NAME,'DisplayVersion':'0.4.0','Publisher':'JR Controller Project',
                           'InstallLocation':str(target),'DisplayIcon':str(target/'JRController.exe'),
                           'UninstallString':f'"{target / "Uninstall.exe"}" --uninstall'}.items():
            winreg.SetValueEx(key,name,0,winreg.REG_SZ,value)
    return reboot

def uninstall():
    if is_running():raise RuntimeError('请先退出 JR 控制器，再卸载')
    target=install_directory().resolve()
    if Path(sys.executable).resolve()!=target/'Uninstall.exe':raise RuntimeError('卸载程序位置不正确')
    for path in shortcut_paths():path.unlink(missing_ok=True)
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,RUN_KEY,0,winreg.KEY_SET_VALUE|winreg.KEY_WOW64_64KEY) as key:
        try:winreg.DeleteValue(key,'JRController')
        except FileNotFoundError:pass
    try:winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE,UNINSTALL_KEY,winreg.KEY_WOW64_64KEY)
    except FileNotFoundError:pass
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.MoveFileExW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,ctypes.c_ulong]
    # Verify the sole removal root; locked executable files are removed on reboot.
    expected=(Path(os.environ['ProgramW6432'])/APP_NAME).resolve()
    if target!=expected:raise RuntimeError('Unexpected uninstall directory')
    deferred=False
    for path in sorted(target.rglob('*'),key=lambda p:len(p.parts),reverse=True)+[target]:
        try:
            if path.is_dir() and not path.is_symlink():path.rmdir()
            else:path.unlink()
        except OSError:
            if not kernel.MoveFileExW(str(path),None,4):raise ctypes.WinError(ctypes.get_last_error())
            deferred=True
    return deferred

def main():
    root=tk.Tk();root.title('JR 控制器安装');root.geometry('460x240');root.resizable(False,False)
    removing='--uninstall' in sys.argv
    status=tk.StringVar(value='将安装控制程序和所需手柄驱动' if not removing else '卸载控制程序，保留共用手柄驱动')
    startup=tk.BooleanVar(value=True);events=queue.Queue()
    ttk.Label(root,text='JR 控制器'+('卸载' if removing else '安装'),font=('Microsoft YaHei',18)).pack(pady=18)
    ttk.Label(root,textvariable=status,wraplength=420).pack(pady=10)
    if not removing:ttk.Checkbutton(root,text='登录后自动运行，插入即连接',variable=startup).pack(pady=5)
    def begin():
        button.config(state='disabled');choice=startup.get()
        root.protocol('WM_DELETE_WINDOW',lambda:status.set('正在处理，请稍候…'))
        def worker():
            try:
                restart=uninstall() if removing else install(Path(sys._MEIPASS),choice,lambda text:events.put(('status',text)))
                events.put(('done',restart))
            except Exception as exc:events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()
    button=ttk.Button(root,text='卸载' if removing else '安装',command=begin);button.pack(pady=14)
    def tick():
        while not events.empty():
            kind,value=events.get_nowait()
            if kind=='status':status.set(value)
            elif kind=='error':
                status.set(value);button.config(state='normal');root.protocol('WM_DELETE_WINDOW',root.destroy)
            elif kind=='done':
                status.set(('卸载完成' if removing else '安装完成，请从桌面打开 JR Controller')+('；请重启电脑' if value else ''))
                button.config(text='完成',state='normal',command=root.destroy)
                root.protocol('WM_DELETE_WINDOW',root.destroy)
        root.after(100,tick)
    tick();root.mainloop()

if __name__=='__main__':main()
