"""Display calibrated AS5600 travel without making notch decisions."""
import math
import queue
import tkinter as tk

from serial_protocol import NOTCH_ORDER


class HandleTravel:
    def __init__(self):
        self.session = None
        self.centers = []
        self.endpoints = None
        self.retry_at = 0

    def angle(self, reader, sample, now):
        if reader is None or sample is None:
            return None
        session = (reader, sample.boot)
        if session != self.session:
            self.session = session
            self.centers.clear()
            self.endpoints = None
            self.retry_at = 0
        if sample.sensor != 'AS5600' or not sample.sensor_ok or not sample.calibrated:
            return None
        if self.endpoints is None:
            if now >= self.retry_at:
                try:
                    reader.commands.put_nowait('DUMP')
                except queue.Full:
                    return None
                self.centers.clear()
                self.retry_at = now + 1
            return None
        if sample.notch == 'N':
            return 0.0
        eb, neutral, power = self.endpoints
        direction = 1 if power > eb else -1
        adc = min(max(sample.adc, min(eb, power)), max(eb, power))
        travel = max(abs(eb - neutral), abs(power - neutral))
        # Fit the longer side on screen while preserving the actual angular spacing.
        return -54 * direction * (adc - neutral) / travel

    def read_center(self, reader, response):
        if self.session is None or reader is not self.session[0] or self.endpoints is not None:
            return
        notch, adc = response.get('notch'), response.get('adc')
        if notch == NOTCH_ORDER[0]:
            self.centers.clear()
        if notch != NOTCH_ORDER[len(self.centers)] or type(adc) is not int or not 0 <= adc < 4096:
            self.centers.clear()
            return
        self.centers.append(adc)
        if len(self.centers) == len(NOTCH_ORDER):
            direction = 1 if self.centers[-1] > self.centers[0] else -1
            if all(direction * (right - left) >= 12 for left, right in zip(self.centers, self.centers[1:])):
                self.endpoints = self.centers[0], self.centers[NOTCH_ORDER.index('N')], self.centers[-1]
            self.centers.clear()


class MasconView(tk.Canvas):
    PIVOT = (65, 64)

    def __init__(self, parent, background):
        super().__init__(parent, width=130, height=84, bg=background, highlightthickness=0)
        self.create_polygon(31, 65, 43, 60, 87, 60, 99, 65, 101, 76, 29, 76,
                            fill='#333939', outline='#151919')
        self.create_rectangle(27, 74, 103, 79, fill='#272C2C', outline='#151919')
        self.create_line(34, 68, 96, 68, fill='#555D5A')
        self.create_oval(52, 51, 78, 77, fill='#3C4442', outline='#181C1C')
        self.lever = []
        for points, fill, outline in (
            ((-5, 4, -5, -10, -4, -46, 4, -46, 5, -10, 5, 4), '#9BA5A2', '#525D59'),
            ((1, -9, 1, -43, 3, -43, 3, -9), '#B7C0BC', ''),
            ((-17, -50, -12, -55, 12, -55, 17, -50, 17, -43, 13, -39, -13, -39, -17, -43),
             '#3D4543', '#141919'),
            ((-13, -50, -10, -52, 10, -52, 13, -50, 13, -48, -13, -48), '#59635F', ''),
        ):
            part = self.create_polygon(*points, fill=fill, outline=outline, state='hidden')
            self.lever.append((part, tuple(zip(points[::2], points[1::2]))))
        self.create_oval(57, 56, 73, 72, fill='#697470', outline='#262C2B')
        self.create_oval(60, 59, 70, 69, fill='#404947', outline='#89938F')
        self.create_line(62, 64, 68, 64, fill='#89938F')
        self.angle = None

    def show(self, angle):
        if angle == self.angle:
            return
        self.angle = angle
        if angle is None:
            for part, _ in self.lever:
                self.itemconfigure(part, state='hidden')
            return
        radians = math.radians(angle)
        cosine, sine = math.cos(radians), math.sin(radians)
        pivot_x, pivot_y = self.PIVOT
        for part, points in self.lever:
            self.coords(part, *[coordinate for x, y in points for coordinate in
                                (pivot_x + x * cosine - y * sine, pivot_y + x * sine + y * cosine)])
            self.itemconfigure(part, state='normal')
