"""Identify controller models and update the supported C3 application partition."""
import hashlib
import json
from pathlib import Path
import queue
import re
import struct
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

MODEL = 'JR-C3-AS5600-R1'
APP_OFFSET = 0x10000
APP_SIZE = 0x140000
MODELS = {
    MODEL: 'Hikari 1',
    'JR-C3-HIDARI-2': 'Hidari 2',
    'JR-S3-AS5600': 'JR 控制器 · S3 磁编码器版',
    'JR-S3-ADC': 'JR 控制器 · S3 电位器版',
}

def hardware_name(sample):
    return MODELS.get(sample.model, sample.model or f'旧版控制器 · {sample.board}')

def hardware_details(sample):
    serial = f'  ·  设备 {sample.device_id[-6:].upper()}' if sample.device_id else ''
    return f"固件 {sample.firmware or '未报告版本'}{serial}"

def bundle_path():
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1] / 'build'))
    return base / 'firmware_update'

def usb_device_id(port):
    from serial.tools import list_ports
    for device in list_ports.comports():
        if device.device == port and (device.vid, device.pid) == (0x303a, 0x1001):
            number = (device.serial_number or '').replace(':', '').replace('-', '').lower()
            if re.fullmatch('[a-f0-9]{12}', number):
                return number
    return None

def validate_layout(table, ota, length):
    expected = {(1, 2, 0x9000, 0x5000), (1, 0, 0xe000, 0x2000),
                (0, 16, APP_OFFSET, APP_SIZE), (0, 17, 0x150000, APP_SIZE)}
    entries = set()
    for offset in range(0, len(table) - 31, 32):
        magic, kind, subtype, address, size = struct.unpack_from('<HBBII', table, offset)
        if magic != 0x50aa:
            break
        entries.add((kind, subtype, address, size))
    if len(table) != 0x1000 or len(ota) != 0x2000 or not expected <= entries or not 0 < length <= APP_SIZE:
        raise RuntimeError('设备分区与本更新包不匹配。')
    # Reject boards that may boot from the second OTA slot.
    for offset in (0, 0x1000):
        sequence = struct.unpack_from('<I', ota, offset)[0]
        if sequence not in (0, 0xffffffff) and sequence % 2 == 0:
            raise RuntimeError('设备使用了其他启动分区，无法用此更新包更新。')

def firmware_files(model):
    folder = bundle_path()
    catalog = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    if not isinstance(catalog, dict):
        raise RuntimeError('固件清单格式不正确。')
    metadata = catalog.get(model)
    if metadata is None:
        return None
    if not isinstance(metadata, dict):
        raise RuntimeError('固件清单格式不正确。')
    series, version = metadata.get('series'), metadata.get('version')
    if (not isinstance(series, str) or not re.fullmatch(r'hidari[1-9][0-9]*', series)
            or not isinstance(version, str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version)):
        raise RuntimeError('固件清单中的系列或版本不正确。')
    image = folder / f'{series}-v{version}-app.bin'
    flasher = folder / 'esptool.exe'
    data = image.read_bytes()
    if (not flasher.is_file() or hashlib.sha256(data).hexdigest() != metadata.get('sha256')
            or model.encode('ascii') + b'\0' not in data or version.encode('ascii') + b'\0' not in data):
        raise RuntimeError('固件更新包不完整或校验失败。')
    return image, flasher, series, version

def flash_application(port, device_id, image, flasher):
    def run(*command, before='no-reset', after='no-reset'):
        result = subprocess.run(
            [str(flasher), '--chip', 'esp32c3', '--port', port, '--baud', '115200',
             '--before', before, '--after', after, *command],
            capture_output=True, encoding='utf-8', errors='replace', timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = result.stdout + result.stderr
        match = re.search(r'(?im)^\s*(?:MAC(?: address)?):\s*([0-9a-f:]{17})', output)
        if result.returncode:
            raise RuntimeError(output.strip()[-1000:])
        if not match or match[1].replace(':', '').lower() != device_id:
            raise RuntimeError('串口芯片编号与当前控制器不一致。')

    run('read-mac', before='default-reset')
    try:
        with tempfile.TemporaryDirectory(prefix='jr-layout-') as temp:
            table = Path(temp) / 'partitions.bin'
            ota = Path(temp) / 'ota.bin'
            run('read-flash', '0x8000', '0x1000', str(table))
            run('read-flash', '0xe000', '0x2000', str(ota))
            validate_layout(table.read_bytes(), ota.read_bytes(), image.stat().st_size)
        if usb_device_id(port) != device_id:
            raise RuntimeError('USB 设备在更新期间发生变化。')
        run('write-flash', '0x10000', str(image), after='hard-reset')
    except Exception:
        # Leave a checked, unmodified device in normal boot after a failed preflight.
        if usb_device_id(port) == device_id:
            try:
                run('read-mac', after='hard-reset')
            except Exception:
                pass
        raise

class HardwareUpdater:
    def __init__(self, app):
        self.app = app
        self.busy = False
        self.pending = None
        self.status = tk.StringVar(value='连接控制器后可检查固件版本。')

    def add_controls(self, parent):
        ttk.Label(parent, textvariable=self.app.hardware_name, style='Section.TLabel').pack(anchor='w')
        ttk.Label(parent, textvariable=self.app.hardware_text, wraplength=540).pack(anchor='w', pady=(4, 8))
        ttk.Label(parent, textvariable=self.status, wraplength=540, justify='left').pack(anchor='w', pady=(0, 10))
        ttk.Button(parent, text='检查并更新固件', command=lambda: self.start(parent)).pack(anchor='w')
        ttk.Label(parent, text='根据设备上报的型号选择固件。请先退出游戏，连接一台控制器。'
                              '更新期间保持 USB 连接。写入应用区，保留板上校准。',
                  wraplength=540).pack(anchor='w', pady=12)

    def start(self, parent):
        app = self.app
        if self.busy or self.pending or app.calibration:
            return
        sample, reader = app.gate.sample, app.reader
        if not reader or not sample or time.monotonic() - app.last_sample_at > .3:
            self.status.set('请先连接控制器，等软件识别后再更新。')
            return
        model = sample.model
        if not model or sample.board != 'C3' or sample.sensor != 'AS5600':
            self.status.set('当前板型暂无匹配的固件更新包。')
            return
        try:
            files = firmware_files(model)
        except (OSError, ValueError, RuntimeError) as error:
            self.status.set(f'固件更新包不可用。{error}')
            return
        if files is None:
            self.status.set('当前板型暂无匹配的固件更新包。')
            return
        image, flasher, series, version = files
        current_version = tuple(map(int, sample.firmware.split('.'))) if sample.firmware else None
        target_version = tuple(map(int, version.split('.')))
        if current_version == target_version:
            self.status.set('控制器已是此更新包的版本。')
            return
        if current_version and current_version > target_version:
            self.status.set('设备固件比此更新包更新。')
            return
        port = reader.port
        device_id = usb_device_id(port)
        if not device_id or sample.device_id != device_id:
            self.status.set('无法核对 USB 设备编号，请重新插拔控制器后重试。')
            return
        if not messagebox.askyesno('确认更新固件',
                                  f'{series}（{model}） · {port} · 设备 {device_id[-6:].upper()}\n'
                                  f'写入固件 {version}，保留板上校准。\n'
                                  '请退出游戏，确认硬件型号无误后继续。', parent=parent):
            return
        current = app.gate.sample
        if (app.reader is not reader or not current or current.model != model or current.device_id != device_id
                or time.monotonic() - app.last_sample_at > .3):
            self.status.set('确认期间设备已更换或断开，请重新检查。')
            return
        app.disconnect()
        if reader.is_alive():
            self.status.set('串口仍在释放，请稍后重试。')
            return
        self.busy = True
        self.status.set('正在核对板型与分区，然后写入固件。请保持 USB 连接…')
        result = queue.Queue(maxsize=1)

        def worker():
            try:
                flash_application(port, device_id, image, flasher)
                result.put(None)
            except Exception as error:
                result.put(str(error))

        def poll():
            try:
                error = result.get_nowait()
            except queue.Empty:
                app.root.after(100, poll)
                return
            self.busy = False
            app.retry_at = 0
            if error is None:
                self.pending = (device_id, model, version, time.monotonic() + 12)
                self.status.set('写入校验通过，等待设备重启并报告新版本…')
            else:
                self.status.set('更新失败。请重新插拔 USB 后重试。 ' + error[-350:])

        threading.Thread(target=worker, daemon=True).start()
        app.root.after(100, poll)

    def observe(self, sample, now):
        if not self.pending:
            return
        device_id, model, version, deadline = self.pending
        if sample and (sample.device_id, sample.model, sample.firmware) == (device_id, model, version):
            self.status.set(f'更新成功。设备已启动固件 {sample.firmware}。')
        elif now >= deadline:
            self.status.set('写入已校验，暂未收到新版启动报告。请松开 BOOT 并重新插拔 USB。')
        else:
            return
        self.pending = None
