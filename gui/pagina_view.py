"""Revisão de páginas sem identificação segura e associação manual de lados B."""
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from PIL import Image, ImageTk

from models.extracao import CampoExtraido, CampoNumeroExtraido, LeituraCartao, StatusLeitura, TipoLadoCartao
from services.lote_service import associar_manualmente, reconciliar_lote

LOG = logging.getLogger(__name__)


class PaginaView(tk.Toplevel):
    def __init__(self, master, lote, pagina, salvar):
        super().__init__(master)
        self.lote, self.pagina, self.salvar = lote, pagina, salvar
        self.title(f"Revisar página {pagina.pagina_origem} · {pagina.nome_arquivo}")
        self.geometry("1080x760")
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.zoom = 0.6
        self.imagem = None
        self.photo = None
        esquerda = ttk.Frame(self, padding=5)
        esquerda.pack(side="left", fill="both", expand=True)
        controles = ttk.Frame(esquerda)
        controles.pack(fill="x")
        for texto, comando in (("−", lambda: self.redimensionar(-0.15)), ("+", lambda: self.redimensionar(0.15)),
                               ("Girar ↺", lambda: self.girar(90)), ("Girar ↻", lambda: self.girar(-90))):
            ttk.Button(controles, text=texto, command=comando).pack(side="left")
        area = ttk.Frame(esquerda)
        area.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(area, bg="#ddd", highlightthickness=0)
        sx = ttk.Scrollbar(area, orient="horizontal", command=self.canvas.xview)
        sy = ttk.Scrollbar(area, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=sx.set, yscrollcommand=sy.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        sx.grid(row=1, column=0, sticky="ew")
        sy.grid(row=0, column=1, sticky="ns")
        area.rowconfigure(0, weight=1)
        area.columnconfigure(0, weight=1)
        try:
            with Image.open(pagina.imagem_processada or pagina.imagem_original) as imagem:
                self.imagem = imagem.copy()
            self.desenhar()
        except (OSError, ValueError):
            LOG.exception("Falha ao abrir imagem da página: id=%s", pagina.id)
            self.canvas.create_text(20, 20, anchor="nw", text="Preview indisponível; confira o arquivo original")
        direita = ttk.Frame(self, padding=12)
        direita.pack(side="right", fill="y")
        ttk.Label(direita, text=pagina.status, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(direita, text="\n".join(pagina.alertas) or pagina.erro or "Confira a identificação visível",
                  wraplength=340).pack(anchor="w", pady=10)
        leitura = pagina.resultado
        self.campos = {}
        for nome, titulo in (("lado", "Lado: A = número 1 / B = número 2"), ("matricula", "Matrícula"),
                              ("nome", "Nome"), ("mes", "Mês"), ("ano", "Ano")):
            ttk.Label(direita, text=titulo).pack(anchor="w", pady=(5, 1))
            valor = (leitura.lado.value if nome == "lado" else getattr(leitura, nome).valor) if leitura else ""
            var = tk.StringVar(value="" if valor is None else str(valor))
            self.campos[nome] = var
            if nome == "lado":
                ttk.Combobox(direita, textvariable=var, values=["A", "B", "DESCONHECIDO"], state="readonly").pack(fill="x")
            else:
                ttk.Entry(direita, textvariable=var).pack(fill="x")
        ttk.Label(direita, text="Salvar registra esta identificação como conferida por você.\nNão preencha valores ilegíveis por suposição.",
                  wraplength=340).pack(anchor="w", pady=10)
        ttk.Button(direita, text="Salvar identificação / aceitar lado", command=self.gravar).pack(fill="x", pady=4)
        self.destino = tk.StringVar()
        self.opcoes = {f"{f.matricula or '?'} · {f.conferencia.funcionario_confirmado or 'Sem nome'} · {f.id[:6]}": f.id
                       for f in lote.funcionarios if not f.lado_b or f.lado_b == pagina.id}
        ttk.Label(direita, text="Associar lado B ao funcionário:").pack(anchor="w", pady=(18, 3))
        ttk.Combobox(direita, textvariable=self.destino, values=list(self.opcoes), state="readonly", width=40).pack(fill="x")
        ttk.Button(direita, text="Associar lado B", command=self.associar).pack(fill="x", pady=4)
        ttk.Button(direita, text="Restaurar página" if pagina.ignorada else "Ignorar página", command=self.ignorar).pack(fill="x", pady=(18, 4))
        ttk.Button(direita, text="Fechar", command=self.destroy).pack(fill="x")

    def desenhar(self):
        if self.imagem:
            tamanho = (max(1, int(self.imagem.width * self.zoom)), max(1, int(self.imagem.height * self.zoom)))
            self.photo = ImageTk.PhotoImage(self.imagem.resize(tamanho, Image.Resampling.LANCZOS))
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, image=self.photo, anchor="nw")
            self.canvas.configure(scrollregion=(0, 0, *tamanho))

    def redimensionar(self, delta):
        self.zoom = max(0.15, min(3, self.zoom + delta))
        self.desenhar()

    def girar(self, graus):
        if self.imagem:
            try:
                girada = self.imagem.rotate(graus, expand=True)
                girada.save(self.pagina.imagem_processada)
                self.imagem = girada
                self.desenhar()
            except OSError:
                LOG.exception("Falha ao salvar imagem girada: id=%s", self.pagina.id)
                messagebox.showerror("Imagem", "Não foi possível salvar o giro", parent=self)

    def gravar(self):
        try:
            lado = TipoLadoCartao(self.campos["lado"].get())
            def texto(nome):
                valor = self.campos[nome].get().strip() or None
                return CampoExtraido(valor=valor, status=StatusLeitura.CONFIRMADO if valor else StatusLeitura.VAZIO)
            def numero(nome, minimo, maximo):
                valor = self.campos[nome].get().strip()
                valor = int(valor) if valor else None
                if valor is not None and not minimo <= valor <= maximo:
                    raise ValueError(f"{nome}: valor fora do intervalo")
                return CampoNumeroExtraido(valor=valor, status=StatusLeitura.CONFIRMADO if valor is not None else StatusLeitura.VAZIO)
            leitura = LeituraCartao(lado=lado, numero_lado=1 if lado.value == "A" else 2 if lado.value == "B" else None,
                status_lado=StatusLeitura.CONFIRMADO if lado.value != "DESCONHECIDO" else StatusLeitura.INCERTO,
                matricula=texto("matricula"), nome=texto("nome"), mes=numero("mes", 1, 12), ano=numero("ano", 1900, 2200),
                registros=self.pagina.resultado.registros if self.pagina.resultado else [])
        except ValueError as exc:
            messagebox.showwarning("Identificação", str(exc), parent=self)
            return False
        self.pagina.revisao_manual = leitura
        self.pagina.lado_aceito_manualmente = True
        self.pagina.erro = None
        reconciliar_lote(self.lote)
        return self.salvar()

    def associar(self):
        if self.destino.get() not in self.opcoes:
            messagebox.showwarning("Pareamento", "Escolha o funcionário", parent=self)
            return
        if not self.gravar():
            return
        try:
            associar_manualmente(self.lote, self.pagina.id, self.opcoes[self.destino.get()])
        except (ValueError, StopIteration) as exc:
            messagebox.showwarning("Pareamento", str(exc) or "Funcionário indisponível", parent=self)
            return
        if self.salvar():
            self.destroy()

    def ignorar(self):
        self.pagina.ignorada = not self.pagina.ignorada
        reconciliar_lote(self.lote)
        if self.salvar():
            self.destroy()
