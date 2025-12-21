import tkinter as tk
from PIL import Image, ImageTk
import os

class CartaoView(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)

        self.title("Cartão de Ponto")

        caminho_imagem = os.path.join("assets", "cartao.png")
        imagem = Image.open(caminho_imagem)

        escala = 1.5
        largura_img, altura_img = imagem.size
        largura_img = int(largura_img * escala)
        altura_img = int(altura_img * escala)


        imagem = imagem.resize((largura_img, altura_img), Image.LANCZOS)
        self.bg_img = ImageTk.PhotoImage(imagem)

        self.geometry(f"{largura_img}x{altura_img}")
        self.resizable(False, False)

        self.canvas = tk.Canvas(self, width=largura_img, height=altura_img)
        self.canvas.pack()

        self.canvas.create_image(0, 0, image=self.bg_img, anchor="nw")

        self.criar_campos()

    def criar_campos(self):
        self.nome = self._campo(200, 60, 250)
        self.mes = self._campo(500, 60, 90)

        self.linhas = []

        y_inicial = 115
        altura_linha = 18
        total_dias = 31

        for dia in range(1, total_dias + 1):
            y = y_inicial + (dia - 1) * altura_linha

            linha = {
                "dia": self._campo(90, y, 40),
                "entrada_manha": self._campo(140, y, 50),
                "saida_manha": self._campo(190, y, 50),
                "entrada_tarde": self._campo(240, y, 50),
                "saida_tarde": self._campo(290, y, 50),
                "total": self._campo(350, y, 60),
            }

            linha["dia"].insert(0, str(dia))
            self.linhas.append(linha)

    def _campo(self, x, y, largura):
        entry = tk.Entry(self)
        self.canvas.create_window(x, y, window=entry, width=largura)
        return entry
