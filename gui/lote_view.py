"""Tela principal: lotes, progresso, funcionários e páginas pendentes."""
import logging
import queue
import threading
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from config.settings import ASSETS_DIR, LOTES_DIR, gemini_api_key
from gui.cartao_view import CartaoView
from gui.pagina_view import PaginaView
from models.extracao import TipoLadoCartao
from models.lote import LoteCartoes
from services.batch_service import processar_importacao, processar_paginas
from services.lote_service import atualizar_status, reconciliar_lote, resumo_lote
from services.lote_storage import carregar_lote, pasta_lote, salvar_lote

LOG = logging.getLogger(__name__)
FILTROS = {"Todos": None, "Aguardando lado B": "AGUARDANDO_LADO_B", "Revisão necessária": "REVISAO_NECESSARIA",
           "Completos": "COMPLETO", "Confirmados": "CONFIRMADO", "Pareamento pendente": "PAREAMENTO_PENDENTE"}


class LoteView(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=12)
        self.lote = None
        self.pasta = None
        self.ocupado = False
        self.fila = queue.Queue()
        self.cancelar = threading.Event()
        self.fechar_ao_terminar = False
        self.processados = self.sucessos = self.total = 0
        self.falha_salvar = False
        barra = ttk.Frame(self)
        barra.pack(fill="x")
        self.mes = tk.StringVar(value=str(date.today().month))
        self.ano = tk.StringVar(value=str(date.today().year))
        for texto, var in (("Mês", self.mes), ("Ano", self.ano)):
            ttk.Label(barra, text=texto).pack(side="left", padx=3)
            ttk.Entry(barra, textvariable=var, width=6).pack(side="left")
        self.botoes = []
        for texto, comando in (("Criar/abrir competência", self.criar), ("Abrir lote salvo", self.abrir)):
            botao = ttk.Button(barra, text=texto, command=comando)
            botao.pack(side="left", padx=5)
            self.botoes.append(botao)
        self.titulo = ttk.Label(self, text="Crie ou abra um lote para começar", font=("Segoe UI", 15, "bold"))
        self.titulo.pack(anchor="w", pady=14)
        acoes = ttk.Frame(self)
        acoes.pack(fill="x")
        self.acoes_lote = []
        for texto, comando in (("Importar lados A · 1", lambda: self.importar(TipoLadoCartao.LADO_A)),
                               ("Importar lados B · 2", lambda: self.importar(TipoLadoCartao.LADO_B)),
                               ("Retomar leituras pendentes", self.retomar), ("Salvar lote", self.guardar)):
            botao = ttk.Button(acoes, text=texto, command=comando)
            botao.pack(side="left", padx=(0, 7))
            self.acoes_lote.append(botao)
        self.btn_parar = ttk.Button(acoes, text="Parar após leituras atuais", command=self.parar)
        self.btn_parar.pack(side="right")
        self.resumo = tk.StringVar()
        ttk.Label(self, textvariable=self.resumo, wraplength=1180).pack(anchor="w", pady=10)
        filtro = ttk.Frame(self)
        filtro.pack(fill="x")
        ttk.Label(filtro, text="Filtrar:").pack(side="left")
        self.filtro = tk.StringVar(value="Todos")
        combo = ttk.Combobox(filtro, textvariable=self.filtro, values=list(FILTROS), state="readonly", width=27)
        combo.pack(side="left", padx=5)
        combo.bind("<<ComboboxSelected>>", lambda e: self.atualizar())
        self.abas = ttk.Notebook(self)
        self.abas.pack(fill="both", expand=True, pady=8)
        self.arvores = []
        for titulo, colunas in (("Funcionários", ("matricula", "nome", "lado_a", "lado_b", "status")),
                                ("Páginas / pendências", ("arquivo", "pagina", "importado", "detectado", "matricula", "status"))):
            frame = ttk.Frame(self.abas)
            self.abas.add(frame, text=titulo)
            tree = ttk.Treeview(frame, columns=colunas, show="headings", selectmode="browse")
            for coluna in colunas:
                tree.heading(coluna, text=coluna.replace("_", " ").title())
                tree.column(coluna, width=170 if coluna in ("nome", "arquivo", "status") else 90, minwidth=60)
            scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scroll.set)
            tree.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")
            self.arvores.append(tree)
        self.funcionarios, self.paginas = self.arvores
        self.funcionarios.bind("<Double-1>", lambda e: self.conferir())
        self.paginas.bind("<Double-1>", lambda e: self.revisar_pagina())
        rodape = ttk.Frame(self)
        rodape.pack(fill="x")
        for texto, comando in (("Abrir conferência mensal", self.conferir), ("Revisar / associar página", self.revisar_pagina)):
            botao = ttk.Button(rodape, text=texto, command=comando)
            botao.pack(side="left", padx=(0, 8))
            self.acoes_lote.append(botao)
        self.progresso = ttk.Progressbar(self, mode="determinate")
        self.progresso.pack(fill="x", pady=(10, 5))
        self.status = tk.StringVar(value="Aguardando lote" if gemini_api_key() else "Configure GEMINI_API_KEY para a leitura por IA; revisão local disponível")
        ttk.Label(self, textvariable=self.status).pack(anchor="w")
        ttk.Label(self, text="Ao importar ou retomar leituras, cada página selecionada será enviada à API externa do Google.").pack(anchor="w", pady=4)
        self.controles()
        self.after(100, self.verificar_fila)
        master.protocol("WM_DELETE_WINDOW", self.fechar)

    def controles(self):
        for b in self.botoes:
            b.configure(state="disabled" if self.ocupado else "normal")
        for b in self.acoes_lote:
            b.configure(state="normal" if self.lote and not self.ocupado else "disabled")
        self.btn_parar.configure(state="normal" if self.ocupado else "disabled")

    def criar(self):
        try:
            lote = LoteCartoes(mes=int(self.mes.get()), ano=int(self.ano.get()))
            pasta = pasta_lote(lote)
            if (pasta / "lote.json").exists():
                lote = carregar_lote(pasta / "lote.json")
            self.lote, self.pasta = lote, pasta
            reconciliar_lote(lote)
            self.guardar()
            self.controles()
            LOG.info("Lote aberto: competência=%02d/%d", lote.mes, lote.ano)
        except (ValueError, OSError):
            LOG.exception("Falha ao criar ou abrir lote")
            messagebox.showerror("Lote", "Não foi possível criar/abrir o lote. Confira mês, ano e acesso à pasta.")

    def abrir(self):
        caminho = filedialog.askopenfilename(initialdir=LOTES_DIR, title="Abrir lote.json", filetypes=[("Lote", "*.json")])
        if caminho:
            try:
                lote = carregar_lote(Path(caminho))
                self.lote, self.pasta = lote, Path(caminho).parent
                self.mes.set(str(lote.mes))
                self.ano.set(str(lote.ano))
                reconciliar_lote(lote)
                self.atualizar()
                self.controles()
                self.status.set("Lote carregado. Leituras interrompidas podem ser retomadas.")
                LOG.info("Lote carregado: competência=%02d/%d", lote.mes, lote.ano)
            except (ValueError, OSError):
                LOG.exception("Falha ao carregar lote salvo")
                messagebox.showerror("Lote", "O arquivo não contém um lote válido ou não pôde ser lido")

    def guardar(self):
        if not self.lote:
            return True
        try:
            salvar_lote(self.lote, self.pasta)
            self.falha_salvar = False
            self.atualizar()
            return True
        except OSError:
            LOG.exception("Falha ao salvar lote: competência=%02d/%d", self.lote.mes, self.lote.ano)
            self.cancelar.set()
            if not self.falha_salvar:
                messagebox.showerror("Salvar", "Não foi possível salvar o lote. Os dados continuam na memória; verifique a pasta e clique em Salvar lote.")
            self.falha_salvar = True
            self.status.set("Falha ao salvar: não feche antes de salvar o lote")
            return False

    def atualizar(self):
        if not self.lote:
            return
        self.titulo.configure(text=f"Controle de cartões · {self.lote.mes:02d}/{self.lote.ano}")
        selecoes = [t.selection() for t in self.arvores]
        for tree in self.arvores:
            tree.delete(*tree.get_children())
        filtro = FILTROS[self.filtro.get()]
        for f in self.lote.funcionarios:
            if filtro and f.status.value != filtro:
                continue
            self.funcionarios.insert("", "end", iid=f.id, values=(f.matricula or "?", f.conferencia.funcionario_confirmado or "Nome não lido",
                "OK", "OK" if f.lado_b else "—", f.status.value))
        for p in self.lote.paginas.values():
            if filtro == "PAREAMENTO_PENDENTE" and p.status != filtro:
                continue
            r = p.resultado
            self.paginas.insert("", "end", iid=p.id, values=(p.nome_arquivo, p.pagina_origem, p.lado_esperado.value,
                r.lado.value if r else "—", r.matricula.valor if r else "—", p.status))
        for tree, sel in zip(self.arvores, selecoes):
            if sel and tree.exists(sel[0]):
                tree.selection_set(sel[0])
        if filtro == "PAREAMENTO_PENDENTE":
            self.abas.select(1)
        r = resumo_lote(self.lote)
        self.resumo.set(f"Funcionários: {r['funcionarios']} · Lados A: {r['lados_a']} · Lados B: {r['lados_b']} · "
            f"Completos: {r['COMPLETO']} · Aguardando B: {r['AGUARDANDO_LADO_B']} · Revisar: {r['REVISAO_NECESSARIA']} · "
            f"Confirmados: {r['CONFIRMADO']} · Páginas pendentes: {r['paginas_pendentes']}")

    def importar(self, lado):
        if self.ocupado or not self.lote:
            return
        caminhos = filedialog.askopenfilenames(initialdir=ASSETS_DIR, title=f"Importar lados {lado.value}: um cartão por página",
                                              filetypes=[("PDF e imagens", "*.pdf *.png *.jpg *.jpeg")])
        if caminhos:
            LOG.info("Importação iniciada: competência=%02d/%d lado=%s arquivos=%d", self.lote.mes,
                     self.lote.ano, lado.value, len(caminhos))
            self.iniciar(lambda emitir: processar_importacao(caminhos, lado, self.pasta, emitir, self.cancelar))

    def retomar(self):
        paginas = [p.model_copy(deep=True) for p in self.lote.paginas.values()
                   if not p.ignorada and p.resultado is None and p.imagem_processada]
        if not paginas:
            self.status.set("Não há leituras interrompidas ou com erro para retomar")
            return
        LOG.info("Retomando leituras: páginas=%d", len(paginas))
        self.iniciar(lambda emitir: processar_paginas(paginas, emitir, self.cancelar))

    def iniciar(self, tarefa):
        self.ocupado = True
        self.cancelar.clear()
        self.processados = self.sucessos = self.total = 0
        self.progresso.configure(value=0, maximum=1)
        self.status.set("Preparando páginas do lote...")
        self.controles()
        def executar():
            try:
                tarefa(lambda tipo, valor: self.fila.put((tipo, valor)))
            except Exception:
                LOG.exception("Falha ao processar lote")
                self.fila.put(("erro", "Falha ao processar o lote; os resultados já salvos foram preservados"))
            finally:
                self.fila.put(("fim", None))
        threading.Thread(target=executar, daemon=True).start()

    def verificar_fila(self):
        try:
            while True:
                tipo, valor = self.fila.get_nowait()
                if tipo in ("pagina", "resultado"):
                    self.lote.paginas[valor.id] = valor
                    reconciliar_lote(self.lote)
                    self.guardar()
                    if tipo == "resultado":
                        LOG.info("Leitura de página concluída: id=%s status=%s", valor.id,
                                 "sucesso" if valor.leitura is not None else "erro")
                        self.processados += 1
                        self.sucessos += int(valor.leitura is not None)
                        self.progresso.configure(value=self.processados)
                        self.status.set(f"{self.processados}/{self.total} processados · {self.sucessos} lidos · "
                                        f"{self.processados-self.sucessos} erros · resultados salvos")
                    else:
                        self.status.set(f"Preparando páginas · {len(self.lote.paginas)} páginas no lote")
                elif tipo == "total":
                    self.total = valor
                    self.progresso.configure(maximum=max(1, valor))
                elif tipo == "erro":
                    messagebox.showerror("Processamento", valor)
                elif tipo == "fim":
                    LOG.info("Processamento do lote encerrado: processadas=%d total=%d sucessos=%d interrompido=%s",
                             self.processados, self.total, self.sucessos, self.cancelar.is_set())
                    self.ocupado = False
                    self.controles()
                    self.status.set(f"{'Interrompido' if self.cancelar.is_set() else 'Leitura concluída'} · {self.processados}/{self.total} processados")
                    if self.fechar_ao_terminar:
                        self.fechar()
                        return
        except queue.Empty:
            pass
        self.after(100, self.verificar_fila)

    def parar(self):
        self.cancelar.set()
        self.status.set("Aguardando as leituras atuais terminarem; o progresso será preservado")

    def conferir(self):
        if self.ocupado or not self.funcionarios.selection():
            return
        mensal = next(f for f in self.lote.funcionarios if f.id == self.funcionarios.selection()[0])
        janela = tk.Toplevel(self)
        janela.title(f"Conferência mensal · {mensal.conferencia.funcionario_confirmado}")
        janela.geometry("1350x820")
        janela.transient(self.winfo_toplevel())
        janela.grab_set()
        def salvar():
            atualizar_status(mensal, self.lote)
            return self.guardar()
        view = CartaoView(janela, mensal=mensal, lote=self.lote, ao_salvar=salvar)
        view.pack(fill="both", expand=True)
        def fechar():
            if view.salvar_rascunho():
                janela.destroy()
        janela.protocol("WM_DELETE_WINDOW", fechar)

    def revisar_pagina(self):
        if self.ocupado or not self.paginas.selection():
            return
        pagina = self.lote.paginas[self.paginas.selection()[0]]
        PaginaView(self, self.lote, pagina, self.guardar)

    def fechar(self):
        if self.ocupado:
            self.fechar_ao_terminar = True
            self.parar()
            return
        if self.guardar():
            self.winfo_toplevel().destroy()
