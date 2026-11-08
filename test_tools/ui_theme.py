"""Shared native UI palette; no additional UI dependencies."""
import tkinter as tk
from tkinter import ttk

BG='#F3F6FC';CARD='#FFFFFF';INK='#14243B';MUTED='#69788E';BLUE='#2563EB'
LINE='#DFE6F0';GREEN='#16846A';AMBER='#B37412';RED='#D34C5E'

PALETTE = (BG,CARD,INK,MUTED,BLUE,'#EDF2FA',GREEN,AMBER,RED)

def apply_theme(root, palette=None):
    global PALETTE
    if palette is not None:
        PALETTE = palette
    BG,CARD,INK,MUTED,BLUE,TILE,GREEN,AMBER,RED = PALETTE
    root.configure(bg=BG)
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('.',font=('Microsoft YaHei UI',10),background=BG,foreground=INK)
    style.configure('Section.TLabel',font=('Microsoft YaHei UI',13,'bold'))
    style.configure('TEntry',fieldbackground=CARD,foreground=INK,insertcolor=INK)
    style.configure('TSpinbox',fieldbackground=CARD,foreground=INK,insertcolor=INK)
    style.map('TCheckbutton',background=[('active',TILE)])
    style.configure('TFrame',background=BG)
    style.configure('Card.TFrame',background=CARD)
    style.configure('TLabel',background=BG,foreground=INK)
    style.configure('Card.TLabel',background=CARD)
    style.configure('Muted.TLabel',foreground=MUTED)
    style.configure('Title.TLabel',font=('Microsoft YaHei UI',22,'bold'))
    style.configure('TButton',padding=(16,9),background=CARD,borderwidth=0,foreground=INK)
    style.map('TButton',background=[('active',TILE)])
    style.configure('Accent.TButton',background=BLUE,foreground='white')
    style.map('Accent.TButton',background=[('active',BLUE),('disabled',TILE)],foreground=[('disabled',MUTED)])
    style.configure('TCombobox',padding=6,fieldbackground=CARD,selectbackground=BLUE)
    style.map('TCombobox',fieldbackground=[('readonly',CARD)],foreground=[('readonly',INK)])
    style.configure('Treeview',background=CARD,fieldbackground=CARD,rowheight=32,borderwidth=0)
    style.configure('Treeview.Heading',background=TILE,font=('Microsoft YaHei UI',10,'bold'),padding=8)
    style.map('Treeview',background=[('selected',BLUE)],foreground=[('selected','white')])
    style.configure('TNotebook',background=BG,borderwidth=0)
    style.configure('TNotebook.Tab',padding=(23,11),background=TILE)
    style.map('TNotebook.Tab',background=[('selected',CARD)],foreground=[('selected',BLUE)])

def button_strip(parent):
    _,CARD,_,MUTED,_,TILE,*_ = PALETTE
    row=tk.Frame(parent,bg=CARD)
    labels=[]
    for name in 'ABXY':
        label=tk.Label(row,text=name,font=('Segoe UI',17,'bold'),width=5,pady=9,bg=TILE,fg=MUTED)
        label.pack(side='left',padx=6);labels.append(label)
    return row,labels

def update_buttons(labels,mask):
    _,_,_,MUTED,BLUE,TILE,*_ = PALETTE
    for i,label in enumerate(labels):
        active=bool(mask&(1<<i))
        label.configure(bg=BLUE if active else TILE,fg='white' if active else MUTED)
