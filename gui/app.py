import tkinter as tk
from gui.cartao_view import CartaoView


class AppPonto(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Sistema de Ponto - Anfora")
        self.geometry("400x200")
        self.resizable(False, False)

        self.criar_widgets()

    def criar_widgets(self):
        titulo = tk.Label(
            self,
            text="Sistema de Ponto",
            font=("Arial", 16, "bold")
        )
        titulo.pack(pady=20)

        btn_cartao = tk.Button(
            self,
            text="Abrir Cartão de Ponto",
            width=25,
            height=2,
            command=self.abrir_cartao
        )
        btn_cartao.pack(pady=10)

        btn_sair = tk.Button(
            self,
            text="Sair",
            width=25,
            command=self.destroy
        )
        btn_sair.pack(pady=5)

    def abrir_cartao(self):
        CartaoView(self)
