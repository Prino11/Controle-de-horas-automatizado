"""Janela principal da conferência."""
import logging
import tkinter as tk
from tkinter import ttk

from gui.lote_view import LoteView


class AppPonto(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Controle de cartões de ponto · Lotes")
        self.geometry("1280x800")
        self.minsize(900, 600)
        ttk.Style(self).theme_use("clam")
        LoteView(self).pack(fill="both", expand=True)

    def report_callback_exception(self, exc_type, exc_value, exc_traceback):
        logging.getLogger(__name__).error("Erro inesperado na interface", exc_info=(exc_type, exc_value, exc_traceback))
        from tkinter import messagebox
        messagebox.showerror("Erro inesperado", "Ocorreu um erro na interface. Consulte o arquivo de logs para detalhes.")
