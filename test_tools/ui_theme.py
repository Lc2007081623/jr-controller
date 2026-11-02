"""Shared native UI palette; no additional UI dependencies."""
import tkinter as tk
from tkinter import ttk

BG='#F3F6FC';CARD='#FFFFFF';INK='#14243B';MUTED='#69788E';BLUE='#2563EB'
LINE='#DFE6F0';GREEN='#16846A';AMBER='#B37412';RED='#D34C5E'

def apply_theme(root):
    root.configure(bg=BG)
    style=ttk.Style(root);style.theme_use('clam')
    style.configure('.',font=('Microsoft YaHei UI',10),background=BG,foreground=INK)
    style.configure('TFrame',background=BG)
    style.configure('Card.TFrame',background=CARD)
    style.configure('TLabel',background=BG,foreground=INK)
    style.configure('Card.TLabel',background=CARD)
    style.configure('Muted.TLabel',foreground=MUTED)
    style.configure('Title.TLabel',font=('Microsoft YaHei UI',22,'bold'))
    style.configure('TButton',padding=(16,9),background=CARD,borderwidth=0,foreground=INK)
    style.map('TButton',background=[('active','#E6EEFC')])
    style.configure('Accent.TButton',background=BLUE,foreground='white')
    style.map('Accent.TButton',background=[('active','#1D4ED8'),('disabled','#B9C9E8')],foreground=[('disabled','white')])
    style.configure('TCombobox',padding=6,fieldbackground=CARD,selectbackground=BLUE)
    style.configure('Treeview',background=CARD,fieldbackground=CARD,rowheight=32,borderwidth=0)
    style.configure('Treeview.Heading',background='#EDF2FA',font=('Microsoft YaHei UI',10,'bold'),padding=8)
    style.map('Treeview',background=[('selected','#DCE8FF')],foreground=[('selected',INK)])
    style.configure('TNotebook',background=BG,borderwidth=0)
    style.configure('TNotebook.Tab',padding=(23,11),background='#E8EEF8')
    style.map('TNotebook.Tab',background=[('selected',CARD)],foreground=[('selected',BLUE)])

def button_strip(parent):
    row=tk.Frame(parent,bg=CARD)
    labels=[]
    for name in 'ABXY':
        label=tk.Label(row,text=name,font=('Segoe UI',17,'bold'),width=5,pady=9,bg='#EDF2FA',fg=MUTED)
        label.pack(side='left',padx=6);labels.append(label)
    return row,labels

def update_buttons(labels,mask):
    for i,label in enumerate(labels):
        active=bool(mask&(1<<i))
        label.configure(bg=BLUE if active else '#EDF2FA',fg='white' if active else MUTED)
