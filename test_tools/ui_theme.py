"""Shared native UI palette; no additional UI dependencies."""
import ctypes
import math
import sys
import time
import tkinter as tk
from tkinter import font, ttk

FONT = 'Microsoft YaHei UI'
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
PALETTE = ('#1B1D1E', '#242728', '#E9EDEA', '#ADB6B2', '#23684D', '#191C1D',
           '#81CFAB', '#DAB477', '#F08D91')

def blend(base, tint, fraction):
    values = [(1 - fraction) * int(base[i:i+2], 16) + fraction * int(tint[i:i+2], 16)
              for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(value):02x}' for value in values)


def style_window(window, background):
    window.configure(bg=background)
    if sys.platform != 'win32':
        return

    def apply():
        dark = ctypes.c_int(int(window.cget('background')[1:3], 16) < 128)
        hwnd = ctypes.c_void_p(int(window.wm_frame(), 16))
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(dark), ctypes.sizeof(dark))

    if window.winfo_ismapped():
        apply()
    else:
        def on_map(event):
            if event.widget is window:
                apply()
        window.bind('<Map>', on_map, add='+')


def paint_surface(image, color, inset=0):
    size, radius = 18, 6 - inset
    edge = size - inset
    for y in range(inset, edge):
        distance = max(inset + radius - y - .5, y + .5 - (edge - radius), 0)
        margin = inset + round(radius - math.sqrt(radius ** 2 - distance ** 2))
        image.put(color, to=(margin, y, size - margin, y + 1))


def style_buttons(root, style, card, ink, muted, accent, green):
    owner = root._root()
    surfaces = getattr(owner, '_jr_button_surfaces', None)
    if surfaces is None:
        surfaces = owner._jr_button_surfaces = {}
        for name in ('neutral', 'accent'):
            normal, disabled, pressed, focus, hover = images = tuple(
                tk.PhotoImage(master=owner, width=18, height=18) for _ in range(5))
            surfaces[name] = images
            style.element_create(f'JR.{name}', 'image', normal,
                                 ('disabled', disabled), ('pressed', pressed),
                                 ('focus', focus), ('active', hover), border=7, padding=3, sticky='nswe')
    for name, base, foreground, names in (
        ('neutral', blend(card, ink, .055), ink, ('TButton', 'Panel.TButton', 'Home.TButton')),
        ('accent', accent, '#F4FAF7', ('Accent.TButton', 'PanelAccent.TButton')),
    ):
        normal, disabled, pressed, focus, hover = surfaces[name]
        paint_surface(normal, base)
        paint_surface(disabled, blend(card, ink, .02))
        paint_surface(pressed, blend(base, card, .45))
        paint_surface(focus, green)
        paint_surface(focus, base, inset=1)
        paint_surface(hover, blend(base, foreground, .09))
        for style_name in names:
            style.layout(style_name, [(f'JR.{name}', {'sticky': 'nswe', 'children': [
                ('Button.padding', {'sticky': 'nswe', 'children': [('Button.label', {'sticky': 'nswe'})]})
            ]})])
            style.configure(style_name, padding=(11, 5), foreground=foreground)
            style.map(style_name, foreground=[('disabled', muted)])
    style.configure('Home.TButton', font=(FONT, 15, 'bold'), padding=(12, 52))

def apply_theme(root, palette=None):
    global PALETTE
    if palette is not None:
        PALETTE = palette
    BG,CARD,INK,MUTED,ACCENT,TILE,GREEN,_,_ = PALETTE
    line = blend(CARD, INK, .10)
    style_window(root, BG)
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('.', font=(FONT, 10), background=BG, foreground=INK,
                    bordercolor=line, lightcolor=line, darkcolor=line, troughcolor=TILE)
    style.configure('Section.TLabel',font=(FONT,12,'bold'))
    style.configure('CardSection.TLabel', font=(FONT,12,'bold'), background=CARD)
    for field in ('TEntry', 'TSpinbox', 'TCombobox'):
        style.configure(field, padding=(7, 4), background=CARD, fieldbackground=CARD,
                        foreground=INK, insertcolor=INK, selectbackground=ACCENT,
                        selectforeground='#F4FAF7', arrowcolor=MUTED, arrowsize=12,
                        lightcolor=CARD, darkcolor=CARD)
        style.map(field, bordercolor=[('focus', GREEN)], foreground=[('disabled', MUTED)])
    style.map('TCheckbutton',background=[('active',TILE)])
    style.configure('TCheckbutton', indicatorbackground=TILE, indicatorforeground=INK)
    style.map('TCheckbutton', indicatorbackground=[('selected', ACCENT)])
    style.configure('TFrame',background=BG)
    style.configure('Card.TFrame',background=CARD)
    style.configure('Divider.TFrame', background=line)
    style.configure('TLabel',background=BG,foreground=INK)
    style.configure('Card.TLabel',background=CARD)
    style.configure('CardMuted.TLabel', background=CARD, foreground=MUTED)
    style.configure('Muted.TLabel',foreground=MUTED)
    style.configure('Title.TLabel',font=(FONT,18,'bold'))
    style_buttons(root, style, CARD, INK, MUTED, ACCENT, GREEN)
    style.map('TCombobox',fieldbackground=[('readonly',CARD)])
    for option, color in (('background', CARD), ('foreground', INK),
                          ('selectBackground', ACCENT), ('selectForeground', '#F4FAF7')):
        root.option_add(f'*TCombobox*Listbox.{option}', color)
    style.configure('Treeview',background=CARD,fieldbackground=CARD,rowheight=28,borderwidth=0)
    style.configure('Treeview.Heading',background=TILE,font=(FONT,10,'bold'),padding=6)
    style.map('Treeview',background=[('selected',ACCENT)],foreground=[('selected','#F4FAF7')])
    style.configure('TNotebook',background=BG,borderwidth=0)
    style.configure('TNotebook.Tab',padding=(16,7),background=TILE)
    style.map('TNotebook.Tab',background=[('selected',CARD)],foreground=[('selected',GREEN)])

def button_strip(parent, width=5):
    _,CARD,_,MUTED,_,TILE,*_ = PALETTE
    row=tk.Frame(parent,bg=CARD)
    labels=[]
    for name in 'ABXY':
        label=tk.Label(row,text=name,font=(FONT,14,'bold'),width=width,pady=7,bg=TILE,fg=MUTED)
        label.pack(side='left',padx=(0,5));labels.append(label)
    return row,labels

def update_buttons(labels,mask):
    _,_,_,MUTED,ACCENT,TILE,*_ = PALETTE
    for i,label in enumerate(labels):
        active=bool(mask&(1<<i))
        label.configure(bg=ACCENT if active else TILE,fg='#F4FAF7' if active else MUTED)


class SlidingReadout(tk.Canvas):
    """Slide between confirmed values without displaying intermediate ones."""
    DURATION = .20

    def __init__(self, parent, background, typeface, width_text):
        self.typeface = font.Font(root=parent, font=typeface)
        self.height = self.typeface.metrics('linespace') + 4
        super().__init__(parent, bg=background, height=self.height,
                         width=self.typeface.measure(width_text) + 4, highlightthickness=0)
        self.center = self.height / 2
        self.text = None
        self.rank = None
        self.current = None
        self.outgoing = None
        self.timer = None
        self.bind('<Configure>', self.center_horizontally)

    def center_horizontally(self, event):
        for item in self.find_all():
            _, y = self.coords(item)
            self.coords(item, event.width / 2, y)

    def show(self, text, color, rank, animate=True):
        if text == self.text and (animate or self.timer is None):
            return

        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        old_rank = self.rank
        self.text, self.rank = text, rank
        x = self.winfo_width() / 2
        if not animate or old_rank is None or rank is None:
            self.delete('all')
            self.current = self.create_text(x, self.center, text=text, fill=color, font=self.typeface)
            self.outgoing = None
            return

        step = self.height if rank > old_rank else -self.height
        _, old_y = self.coords(self.current)
        if self.outgoing is not None and self.itemcget(self.outgoing, 'text') == text:
            incoming = self.outgoing
            _, new_y = self.coords(incoming)
        else:
            if self.outgoing is not None:
                _, outgoing_y = self.coords(self.outgoing)
                if abs(outgoing_y - self.center) < abs(old_y - self.center):
                    self.delete(self.current)
                    self.current = self.outgoing
                    old_y = outgoing_y
                else:
                    self.delete(self.outgoing)
            new_y = old_y + step
            incoming = self.create_text(x, new_y, text=text, fill=color, font=self.typeface)
        self.outgoing, self.current = self.current, incoming
        self.tag_raise(incoming)
        self.slide(time.monotonic(), old_y, new_y, self.center - step)

    def slide(self, started, old_y, new_y, exit_y):
        progress = min((time.monotonic() - started) / self.DURATION, 1)
        eased = 1 - (1 - progress) ** 3
        x = self.winfo_width() / 2
        self.coords(self.outgoing, x, old_y + (exit_y - old_y) * eased)
        self.coords(self.current, x, new_y + (self.center - new_y) * eased)
        if progress < 1:
            self.timer = self.after(16, self.slide, started, old_y, new_y, exit_y)
        else:
            self.delete(self.outgoing)
            self.outgoing = self.timer = None

    def destroy(self):
        if self.timer is not None:
            self.after_cancel(self.timer)
        super().destroy()
