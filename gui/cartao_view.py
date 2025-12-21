import tkinter as tk
from PIL import Image, ImageTk
import os

class CartaoView(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)

        self.title("Cartão de Ponto")
        self.geometry("900x700")

        # ===== Canvas =====
        self.canvas = tk.Canvas(self, width=850, height=600)
        self.canvas.pack(pady=10)

        # ===== Imagem do cartão =====
        caminho_imagem = os.path.join("assets", "cartao.png")
        imagem = Image.open(caminho_imagem)
        imagem = imagem.resize((850, 600))
        self.bg_img = ImageTk.PhotoImage(imagem)
        self.canvas.create_image(0, 0, image=self.bg_img, anchor="nw")

        # ===== Criar campos =====
        self.criar_campos()

    # =========================
    # CRIAÇÃO DOS CAMPOS
    # =========================
    def criar_campos(self):
        # ===== Cabeçalho =====
        self.nome = self._campo(260, 140, 280)
        self.mes = self._campo(560, 140, 100)

        # ===== Linhas do cartão (dias) =====
        self.linhas = []

        y_inicial = 300
        altura_linha = 28
        total_dias = 31  # depois podemos variar pelo mês

        for dia in range(1, total_dias + 1):
            y = y_inicial + (dia - 1) * altura_linha

            linha = {
                "dia": self._campo(80, y, 60),
                "entrada_manha": self._campo(170, y, 70),
                "saida_manha": self._campo(260, y, 70),
                "entrada_tarde": self._campo(360, y, 70),
                "saida_tarde": self._campo(450, y, 70),
                "total": self._campo(550, y, 70),
            }

            # Preenche automaticamente o dia
            linha["dia"].insert(0, str(dia))

            self.linhas.append(linha)

    # =========================
    # CAMPO PADRÃO
    # =========================
    def _campo(self, x, y, largura):
        entry = tk.Entry(self)
        self.canvas.create_window(x, y, window=entry, width=largura)
        return entry
