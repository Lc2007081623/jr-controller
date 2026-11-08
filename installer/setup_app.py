"""Offline Windows installer, built with the same PyInstaller tool as the app."""
import ctypes
import json
import logging
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
from tkinter import ttk, filedialog
import winreg

APP_NAME='JR Controller'
VERSION='1.1.0'
UNINSTALL_KEY=r'Software\Microsoft\Windows\CurrentVersion\Uninstall\JRController'
RUN_KEY=r'Software\Microsoft\Windows\CurrentVersion\Run'

def install_directory():
    return Path(os.environ['ProgramW6432'])/APP_NAME

def check_system():
    arch=os.environ.get('PROCESSOR_ARCHITEW6432') or os.environ.get('PROCESSOR_ARCHITECTURE','')
    if sys.platform!='win32' or sys.getwindowsversion().major<10 or arch.upper()!='AMD64':
        raise RuntimeError('此安装包适用于 Windows 10/11 64 位（Intel/AMD）电脑。')

def verify_app(target):
    with tempfile.TemporaryDirectory(prefix='JRInstallCheck-') as temp:
        report=Path(temp)/'check.json'
        try:
            result=subprocess.run([str(target/'JRController.exe'),'--self-check',str(report)],
                                  timeout=35,creationflags=subprocess.CREATE_NO_WINDOW)
            data=json.loads(report.read_text(encoding='utf-8'))
        except (OSError,ValueError,subprocess.TimeoutExpired) as exc:
            logging.exception('Installation check failed')
            raise RuntimeError('程序自检未完成，请重启电脑后重新运行安装包；可查看安装日志。') from exc
        logging.info('Application check: %s',data)
        return result.returncode==0 and isinstance(data,dict) and data.get('ok') is True

def run_driver(payload,repair=False):
    args=[str(payload/'ViGEmBus_1.22.0_x64_x86_arm64.exe')]
    # The official 1.22.0 EXE is an Advanced Installer bootstrapper, not WiX Burn.
    args+=['/exenoui']
    if repair:args+=['/fomus','//']
    args+=['/qn','/norestart']
    result=subprocess.run(args,creationflags=subprocess.CREATE_NO_WINDOW,timeout=300)
    logging.info('Driver repair=%s exit=%s',repair,result.returncode)
    return driver_result(result.returncode)

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

def install_bve_plugins(target, paths):
    for version, directory in paths:
        if version not in ('BVE5','BVE6'):raise ValueError('无效的 BVE 版本')
        if not directory:continue
        game=Path(directory)
        if not (game/'BveTs.exe').is_file() or not (game/'Mackoy.IInputDevice.dll').is_file():
            raise RuntimeError(f'{version} 请选择包含 BveTs.exe 的游戏目录：{game}')
        destination=game/'Input Devices';destination.mkdir(exist_ok=True)
        try:shutil.copy2(target/'BVE Plugins'/version/'JRController.Bve.dll',destination/'JRController.Bve.dll')
        except OSError as exc:raise RuntimeError(f'无法更新 {version} 插件，请退出 BVE 并检查目录权限后重试：{game}') from exc
        logging.info('Installed %s input plugin: %s',version,destination)

def install(payload,startup,progress,bve_paths=()):
    check_system()
    if is_running():raise RuntimeError('请先退出正在运行的 JR 控制器，再点击安装')
    reboot=False;existing=driver_installed()
    progress(1,'检查手柄驱动')
    if not existing:reboot=run_driver(payload)
    progress(2,'安装控制器程序和离线使用说明')
    target=install_directory();target.mkdir(parents=True,exist_ok=True)
    shutil.copytree(payload/'app',target,dirs_exist_ok=True)
    shutil.copy2(payload/'ThirdPartyNotices.txt',target/'ThirdPartyNotices.txt')
    shutil.copy2(target/'_internal/first_steps.html',target/'first_steps.html')
    shutil.copy2(target/'_internal/bve_guide.html',target/'bve_guide.html')
    shutil.copy2(target/'_internal/train_crew_guide.html',target/'train_crew_guide.html')
    install_bve_plugins(target,bve_paths)
    shutil.copy2(sys.executable,target/'Uninstall.exe')
    for path in shortcut_paths():shortcut(path,target/'JRController.exe')
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE,RUN_KEY,0,winreg.KEY_SET_VALUE|winreg.KEY_WOW64_64KEY) as key:
        if startup:winreg.SetValueEx(key,'JRController',0,winreg.REG_SZ,f'"{target / "JRController.exe"}" --background')
        else:
            try:winreg.DeleteValue(key,'JRController')
            except FileNotFoundError:pass
    with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE,UNINSTALL_KEY,0,winreg.KEY_SET_VALUE|winreg.KEY_WOW64_64KEY) as key:
        for name,value in {'DisplayName':APP_NAME,'DisplayVersion':VERSION,'Publisher':'JR Controller Project',
                           'InstallLocation':str(target),'DisplayIcon':str(target/'JRController.exe'),
                           'UninstallString':f'"{target / "Uninstall.exe"}" --uninstall'}.items():
            winreg.SetValueEx(key,name,0,winreg.REG_SZ,value)
    progress(3,'检查 Xbox、RUNNING TRAIN、BVE 和 TRAIN CREW 输出')
    if not reboot and not verify_app(target):
        if existing:
            progress(3,'修复已有手柄驱动后重新检查')
            reboot=run_driver(payload,repair=True)
        if not reboot and (not existing or not verify_app(target)):
            raise RuntimeError('程序已复制，但手柄自检未通过。请重启电脑后重试安装；仍失败时提供安装日志。')
    progress(4,'需要重启后完成驱动检查' if reboot else '安装与虚拟手柄检查通过')
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
    log_directory=Path(os.environ['ProgramData'])/'JRController'
    try:
        log_directory.mkdir(parents=True,exist_ok=True)
        log_path=log_directory/'setup.log'
        with log_path.open('a',encoding='utf-8'):pass
    except OSError:log_path=Path(tempfile.gettempdir())/'JRController-setup.log'
    logging.basicConfig(filename=log_path,level=logging.INFO,encoding='utf-8',
                        format='%(asctime)s %(levelname)s %(message)s',force=True)
    logging.info('Setup %s started; uninstall=%s',VERSION,'--uninstall' in sys.argv)
    root=tk.Tk();root.title('JR 控制器安装');root.geometry('660x690');root.resizable(False,False)
    root.configure(bg='#F3F6FC')
    removing='--uninstall' in sys.argv
    status=tk.StringVar(value='无需 Python，无需联网。请先退出游戏和旧版 JR 控制器。' if not removing else '卸载控制程序，保留共用手柄驱动')
    startup=tk.BooleanVar(value=True);events=queue.Queue()
    body=ttk.Frame(root,padding=24);body.pack(fill='both',expand=True)
    ttk.Label(body,text='JR 控制器'+('卸载' if removing else '完整安装'),font=('Microsoft YaHei',21,'bold')).pack(anchor='w')
    ttk.Label(body,text='Windows 10 / 11 · 64 位 · '+VERSION).pack(anchor='w',pady=(3,16))
    steps=[tk.StringVar(value=text) for text in ('1  检查电脑与手柄驱动','2  安装程序、插件与离线说明','3  验证三个游戏模式','4  完成安装，连接硬件')]
    if not removing:
        for text in steps:ttk.Label(body,textvariable=text,font=('Microsoft YaHei',11)).pack(anchor='w',pady=5)
    bar=ttk.Progressbar(body,maximum=4);bar.pack(fill='x',pady=12)
    ttk.Label(body,textvariable=status,wraplength=565,justify='left').pack(anchor='w',pady=8)
    if not removing:ttk.Checkbutton(root,text='登录后自动运行，插入即连接',variable=startup).pack(pady=5)
    bve_vars=[]
    if not removing:
        box=ttk.LabelFrame(root,text='BVE 插件（可选；留空则仅随程序附带）',padding=10)
        box.pack(fill='x',padx=24,pady=5)
        for version,default in (('BVE5','D:/bve'),('BVE6','D:/BVE6')):
            value=tk.StringVar(value=default if (Path(default)/'BveTs.exe').is_file() else '')
            bve_vars.append((version,value))
            row_bve=ttk.Frame(box);row_bve.pack(fill='x',pady=3)
            ttk.Label(row_bve,text=version,width=6).pack(side='left')
            ttk.Entry(row_bve,textvariable=value).pack(side='left',fill='x',expand=True,padx=6)
            def browse(v=value):
                folder=filedialog.askdirectory(title='选择包含 BveTs.exe 的游戏目录')
                if folder:v.set(folder)
            ttk.Button(row_bve,text='选择目录',command=browse).pack(side='right')
    def begin():
        button.config(state='disabled');choice=startup.get()
        paths=[(version,value.get().strip()) for version,value in bve_vars]
        root.protocol('WM_DELETE_WINDOW',lambda:status.set('正在处理，请稍候…'))
        def worker():
            try:
                restart=uninstall() if removing else install(Path(sys._MEIPASS),choice,lambda step,text:events.put(('progress',(step,text))),paths)
                events.put(('done',restart))
            except Exception as exc:
                logging.exception('Setup failed');events.put(('error',str(exc)))
        threading.Thread(target=worker,daemon=True).start()
    row=ttk.Frame(root,padding=(24,10));row.pack(fill='x')
    button=ttk.Button(row,text='卸载' if removing else '一键安装',command=begin);button.pack(side='right')
    def show_log():
        try:os.startfile(log_path)
        except OSError:status.set('日志位置：'+str(log_path))
    def show_guide():
        guide=install_directory()/'first_steps.html'
        if not guide.exists():guide=Path(sys._MEIPASS)/'app/_internal/first_steps.html'
        try:os.startfile(guide)
        except OSError:status.set('请安装后在程序内点击“使用说明”。')
    ttk.Button(row,text='查看安装日志',command=show_log).pack(side='left')
    if not removing:ttk.Button(row,text='使用说明',command=show_guide).pack(side='left',padx=8)
    def tick():
        while not events.empty():
            kind,value=events.get_nowait()
            if kind=='progress':
                step,text=value;bar['value']=step-1;steps[step-1].set(f'{step}  {text}');status.set(text)
            elif kind=='error':
                status.set(value);button.config(text='重试',state='normal');root.protocol('WM_DELETE_WINDOW',root.destroy)
            elif kind=='done':
                bar['value']=4
                logging.info('Setup completed; restart=%s',value)
                status.set('卸载完成' if removing else ('安装完成。请先重启电脑，再从桌面打开 JR Controller；重启后程序将检查驱动连接。' if value else '安装与手柄自检通过！从桌面打开 JR Controller，连接 USB，选好游戏模式，再启动游戏。'))
                button.config(text='完成',state='normal',command=root.destroy)
                root.protocol('WM_DELETE_WINDOW',root.destroy)
        root.after(100,tick)
    tick();root.mainloop()

if __name__=='__main__':main()
