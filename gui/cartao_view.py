"""Visualização do scan e edição humana dos dados extraídos."""
import calendar
import logging
import queue
import threading
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from config.settings import ASSETS_DIR, GEMINI_MODEL, gemini_api_key
from models.cartao_ponto import CAMPOS_HORARIO, CartaoConferido, DiaConferido
from models.extracao import StatusLeitura
from services.gemini_service import LeituraIndisponivel, analisar_cartao
from services.image_service import ImagemPreparada, girar_imagem, preparar_imagens
from services.processador_ponto import calcular_total_texto
from services.storage_service import salvar_cartao
from services.validation_service import validar_cartao, validar_dia
from services.lote_service import confirmar_mensal

LOG = logging.getLogger(__name__)
TITULOS = ("Dia", "Entrada manhã", "Saída manhã", "Entrada tarde", "Saída tarde", "Total", "Status", "Observações")
CORES = {"OK": "#ffffff", "INCERTO": "#fff0b3", "ILEGIVEL": "#ffd5d5",
         "ERRO": "#ffb5b5", "ALTERADO": "#dcefdc", "VAZIO": "#ffffff"}


class CartaoView(ttk.Frame):
    def __init__(self, master, mensal=None, lote=None, ao_salvar=None):
        super().__init__(master, padding=8)
        self.mensal, self.lote, self.ao_salvar = mensal, lote, ao_salvar
        self._salvamento = None
        self.imagem: ImagemPreparada | None = None
        self.cartao: CartaoConferido | None = None
        self.zoom = 0.65
        self._photo = None
        self._ocupado = False
        self._reanalisou = False
        self._fila = queue.Queue()
        self._linhas = []
        self._construir()
        if mensal:
            self.abrir_cartao(mensal)
        self.after(100, self._verificar_fila)

    def _construir(self):
        barra = ttk.Frame(self)
        barra.pack(fill="x", pady=(0, 8))
        self.btn_abrir = ttk.Button(barra, text="Selecionar cartão (frente/verso)", command=self.selecionar)
        self.btn_abrir.pack(side="left")
        self.btn_analisar = ttk.Button(barra, text="Analisar com IA", command=self.analisar)
        self.btn_analisar.pack(side="left", padx=5)
        self.btn_reanalisar = ttk.Button(barra, text="Reanalisar campos", command=self.reanalisar)
        self.btn_reanalisar.pack(side="left")
        self.btn_confirmar = ttk.Button(barra, text="Confirmar cartão", command=self.confirmar)
        self.btn_confirmar.pack(side="right")
        if self.mensal:
            for b in (self.btn_abrir, self.btn_analisar, self.btn_reanalisar):
                b.pack_forget()
            ttk.Button(barra, text="Salvar rascunho", command=self.salvar_rascunho).pack(side="left")
            ttk.Label(barra, text=f"Matrícula: {self.mensal.matricula or 'não lida · revise a página A'}").pack(side="left", padx=12)
            self.identificacao = tk.BooleanVar(value=self.mensal.identificacao_revisada)
            ttk.Checkbutton(barra, text="Conferi identificação e as duas faces", variable=self.identificacao,
                            command=lambda: self._alterou(0)).pack(side="left")

        painel = ttk.Panedwindow(self, orient="horizontal")
        painel.pack(fill="both", expand=True)
        esquerda = ttk.LabelFrame(painel, text="Imagem digitalizada")
        direita = ttk.LabelFrame(painel, text="Cartão extraído e conferência")
        painel.add(esquerda, weight=1)
        painel.add(direita, weight=2)

        if self.mensal:
            lados = ttk.Frame(esquerda)
            lados.pack(fill="x", pady=4)
            ttk.Button(lados, text="Lado A · 1 · dias 1–15", command=lambda: self.mostrar_lado("A")).pack(side="left")
            ttk.Button(lados, text="Lado B · 2 · dias 16–31", command=lambda: self.mostrar_lado("B")).pack(side="left", padx=3)

        controles = ttk.Frame(esquerda)
        controles.pack(fill="x")
        ttk.Button(controles, text="−", width=3, command=lambda: self._zoom(-0.15)).pack(side="left")
        self.zoom_texto = ttk.Label(controles, text="65%")
        self.zoom_texto.pack(side="left", padx=7)
        ttk.Button(controles, text="+", width=3, command=lambda: self._zoom(0.15)).pack(side="left")
        self.btn_girar_esq = ttk.Button(controles, text="Girar ↺", command=lambda: self._girar(90))
        self.btn_girar_esq.pack(side="left", padx=(8, 2))
        self.btn_girar_dir = ttk.Button(controles, text="Girar ↻", command=lambda: self._girar(-90))
        self.btn_girar_dir.pack(side="left")
        ttk.Label(controles, text="Original preservado; páginas do PDF em sequência").pack(side="right")
        imagem_frame = ttk.Frame(esquerda)
        imagem_frame.pack(fill="both", expand=True)
        self.canvas_img = tk.Canvas(imagem_frame, background="#dedede", highlightthickness=0)
        self.canvas_img.grid(row=0, column=0, sticky="nsew")
        sx = ttk.Scrollbar(imagem_frame, orient="horizontal", command=self.canvas_img.xview)
        sy = ttk.Scrollbar(imagem_frame, orient="vertical", command=self.canvas_img.yview)
        sx.grid(row=1, column=0, sticky="ew")
        sy.grid(row=0, column=1, sticky="ns")
        self.canvas_img.configure(xscrollcommand=sx.set, yscrollcommand=sy.set)
        imagem_frame.rowconfigure(0, weight=1)
        imagem_frame.columnconfigure(0, weight=1)

        cab = ttk.Frame(direita, padding=5)
        cab.pack(fill="x")
        self.nome = tk.StringVar()
        self.mes = tk.StringVar(value=str(date.today().month))
        self.ano = tk.StringVar(value=str(date.today().year))
        for label, var, largura in (("Funcionário", self.nome, 28), ("Mês", self.mes, 4), ("Ano", self.ano, 6)):
            ttk.Label(cab, text=label).pack(side="left", padx=(4, 2))
            entry = ttk.Entry(cab, textvariable=var, width=largura,
                              state="readonly" if self.mensal and label in ("Mês", "Ano") else "normal")
            entry.pack(side="left")
            if self.mensal and label == "Funcionário":
                entry.bind("<KeyRelease>", lambda e: self._alterou(0))
        if not self.mensal:
            ttk.Button(cab, text="Aplicar mês/ano", command=self.aplicar_mes).pack(side="left", padx=7)

        tabela = ttk.Frame(direita)
        tabela.pack(fill="both", expand=True)
        self.canvas_tabela = tk.Canvas(tabela, highlightthickness=0)
        barra_y = ttk.Scrollbar(tabela, orient="vertical", command=self.canvas_tabela.yview)
        barra_x = ttk.Scrollbar(tabela, orient="horizontal", command=self.canvas_tabela.xview)
        self.canvas_tabela.configure(yscrollcommand=barra_y.set, xscrollcommand=barra_x.set)
        self.canvas_tabela.grid(row=0, column=0, sticky="nsew")
        barra_y.grid(row=0, column=1, sticky="ns")
        barra_x.grid(row=1, column=0, sticky="ew")
        tabela.rowconfigure(0, weight=1)
        tabela.columnconfigure(0, weight=1)
        self.corpo = ttk.Frame(self.canvas_tabela)
        self.janela_corpo = self.canvas_tabela.create_window((0, 0), window=self.corpo, anchor="nw")
        self.corpo.bind("<Configure>", lambda e: self.canvas_tabela.configure(scrollregion=self.canvas_tabela.bbox("all")))
        self.canvas_tabela.bind("<Configure>", self._ajustar_largura_tabela)
        for col, titulo in enumerate(TITULOS):
            ttk.Label(self.corpo, text=titulo, padding=5, anchor="center").grid(row=0, column=col, sticky="ew")
        for col in range(1, 5):
            self.corpo.columnconfigure(col, weight=1)
        self.corpo.columnconfigure(6, weight=2)
        self.corpo.columnconfigure(7, weight=2)

        self.status = tk.StringVar(value="Aguardando arquivo")
        ttk.Label(self, textvariable=self.status, padding=(3, 7)).pack(fill="x")
        self.aviso_ia = ttk.Label(self, text="A análise envia a imagem do cartão para a API externa do Google.")
        self.aviso_ia.pack(fill="x")
        if not gemini_api_key():
            self.status.set("Aguardando arquivo · leitura por IA indisponível: configure GEMINI_API_KEY")
        self._atualizar_botoes()

    def abrir_cartao(self, mensal):
        self.cartao = mensal.conferencia
        self.nome.set(self.cartao.funcionario_confirmado)
        self.mes.set(str(self.cartao.mes_confirmado))
        self.ano.set(str(self.cartao.ano_confirmado))
        self._montar_linhas()
        self.mostrar_lado("A")
        self._atualizar_estado()

    def mostrar_lado(self, lado):
        pid = self.mensal.lado_a if lado == "A" else self.mensal.lado_b
        if not pid:
            self.imagem = None
            self.canvas_img.delete("all")
            self.canvas_img.create_text(15, 15, anchor="nw", text=f"Aguardando associação do lado {lado}")
            self._atualizar_botoes()
            return
        pagina = self.lote.paginas[pid]
        try:
            with Image.open(pagina.imagem_processada) as imagem:
                preview = imagem.copy()
            self.imagem = ImagemPreparada(Path(pagina.arquivo_origem), [Path(pagina.arquivo_origem)],
                                         Path(pagina.imagem_processada), preview)
            self._desenhar_imagem()
        except (OSError, ValueError):
            LOG.exception("Falha ao abrir imagem do cartão")
            self.imagem = None
            self.canvas_img.delete("all")
            self.canvas_img.create_text(15, 15, anchor="nw", text="Imagem indisponível; confira a pasta do lote")
        self._atualizar_botoes()

    def salvar_rascunho(self):
        if not self.mensal:
            return True
        if self._salvamento:
            self.after_cancel(self._salvamento)
            self._salvamento = None
        self._sincronizar()
        self.mensal.nome = self.cartao.funcionario_confirmado
        self.mensal.identificacao_revisada = self.identificacao.get()
        return self.ao_salvar()

    def _ajustar_largura_tabela(self, evento):
        self.canvas_tabela.itemconfigure(self.janela_corpo,
                                         width=max(evento.width, self.corpo.winfo_reqwidth()))
        self.canvas_tabela.configure(scrollregion=self.canvas_tabela.bbox("all"))

    def _atualizar_botoes(self):
        self.btn_abrir.configure(state="disabled" if self._ocupado else "normal")
        self.btn_analisar.configure(state="normal" if self.imagem and gemini_api_key() and not self._ocupado else "disabled")
        for botao in (self.btn_girar_esq, self.btn_girar_dir):
            botao.configure(state="normal" if self.imagem and not self._ocupado else "disabled")
        self.btn_confirmar.configure(state="normal" if self.cartao and not self._ocupado else "disabled")
        duvidosos = bool(self.cartao and self._campos_duvidosos())
        self.btn_reanalisar.configure(state="normal" if duvidosos and not self._reanalisou and gemini_api_key() and not self._ocupado else "disabled")

    def _trabalho(self, funcao, concluido):
        self._ocupado = True
        self._atualizar_botoes()
        def executar():
            try:
                self._fila.put((concluido, funcao(), None))
            except LeituraIndisponivel as exc:
                LOG.error("Leitura por IA indisponível: %s; causa=%s", exc,
                          type(exc.__cause__).__name__ if exc.__cause__ else "não informada")
                self._fila.put((concluido, None, exc))
            except Exception as exc:
                LOG.exception("Operação do cartão falhou")
                self._fila.put((concluido, None, exc))
        threading.Thread(target=executar, daemon=True).start()

    def _verificar_fila(self):
        try:
            while True:
                concluido, resultado, erro = self._fila.get_nowait()
                self._ocupado = False
                concluido(resultado, erro)
                self._atualizar_botoes()
        except queue.Empty:
            pass
        self.after(100, self._verificar_fila)

    def selecionar(self):
        caminhos = filedialog.askopenfilenames(title="Selecionar frente e verso (até dois arquivos)",
            initialdir=ASSETS_DIR, filetypes=[("Cartões digitalizados", "*.png *.jpg *.jpeg *.pdf")])
        if not caminhos:
            return
        if len(caminhos) > 2:
            messagebox.showwarning("Seleção", "Selecione no máximo dois arquivos do mesmo cartão")
            return
        caminhos = sorted(caminhos, key=lambda p: 0 if Path(p).stem.lower().startswith("lado_a") else
                          1 if Path(p).stem.lower().startswith("lado b") else 2)
        LOG.info("Arquivo selecionado")
        self.status.set("Preparando imagem")
        self._trabalho(lambda: preparar_imagens(caminhos), self._imagem_pronta)

    def _imagem_pronta(self, imagem, erro):
        if erro:
            messagebox.showerror("Arquivo", str(erro))
            self.status.set("Aguardando arquivo")
            return
        self.imagem = imagem
        self._reanalisou = False
        self._desenhar_imagem()
        self.cartao = CartaoConferido(arquivo_origem=str(imagem.original),
                                     arquivos_origem=[str(p) for p in imagem.originais])
        self.nome.set("")
        self.aplicar_mes()
        self.status.set("Imagem preparada. Clique em Analisar com IA ou preencha manualmente."
                        + (f" PDF com {imagem.paginas} páginas carregadas." if imagem.paginas > 1 else ""))

    def _girar(self, graus):
        if not self.imagem or self._ocupado:
            return
        try:
            if self.mensal:
                girada = self.imagem.preview.rotate(graus, expand=True)
                girada.save(self.imagem.processada)
                self.imagem.preview = girada
            else:
                girar_imagem(self.imagem, graus)
        except OSError:
            LOG.exception("Falha ao girar imagem")
            messagebox.showerror("Imagem", "Não foi possível girar a cópia para análise")
            return
        self._desenhar_imagem()

    def _zoom(self, delta):
        self.zoom = max(0.2, min(3.0, round(self.zoom + delta, 2)))
        self.zoom_texto.configure(text=f"{self.zoom:.0%}")
        self._desenhar_imagem()

    def _desenhar_imagem(self):
        if not self.imagem:
            return
        original = self.imagem.preview
        tamanho = (max(1, int(original.width * self.zoom)), max(1, int(original.height * self.zoom)))
        self._photo = ImageTk.PhotoImage(original.resize(tamanho, Image.Resampling.LANCZOS))
        self.canvas_img.delete("all")
        self.canvas_img.create_image(0, 0, image=self._photo, anchor="nw")
        self.canvas_img.configure(scrollregion=(0, 0, *tamanho))

    def analisar(self):
        if not self.imagem or not gemini_api_key():
            self.status.set("Leitura por IA indisponível: configure GEMINI_API_KEY")
            return
        LOG.info("Análise de cartão iniciada")
        self.status.set("Analisando cartão...")
        self._trabalho(lambda: analisar_cartao(self.imagem.processada), self._analise_pronta)

    def _analise_pronta(self, extracao, erro):
        if erro:
            messagebox.showerror("Leitura por IA", str(erro))
            self.status.set("Falha na leitura; você pode preencher manualmente ou tentar novamente")
            return
        self.cartao = CartaoConferido.da_extracao(str(self.imagem.original), GEMINI_MODEL, extracao)
        self.cartao.arquivos_origem = [str(p) for p in self.imagem.originais]
        self.nome.set(self.cartao.funcionario_confirmado)
        self.mes.set(str(self.cartao.mes_confirmado or ""))
        self.ano.set(str(self.cartao.ano_confirmado or ""))
        if self.cartao.mes_confirmado and self.cartao.ano_confirmado:
            self.aplicar_mes()
        else:
            existentes = {r.dia for r in self.cartao.registros}
            self.cartao.registros.extend(DiaConferido(dia=d) for d in range(1, 32) if d not in existentes)
            self.cartao.registros.sort(key=lambda r: r.dia)
            self._montar_linhas()
            self._atualizar_estado()
        LOG.info("Validação executada; %s campos suspeitos", len(self._campos_duvidosos()))

    def aplicar_mes(self):
        if not self.cartao:
            return
        self._sincronizar()
        try:
            ano, mes = int(self.ano.get()), int(self.mes.get())
            if not 1900 <= ano <= 2200:
                raise ValueError()
            dias = calendar.monthrange(ano, mes)[1]
        except ValueError:
            messagebox.showwarning("Mês e ano", "Informe mês de 1 a 12 e ano válido")
            return
        self.cartao.mes_confirmado, self.cartao.ano_confirmado = mes, ano
        self.cartao.registros = [r for r in self.cartao.registros if r.dia <= dias or
                                any(getattr(r, c).valor_confirmado or getattr(r, c).valor_extraido
                                    for c in CAMPOS_HORARIO) or r.observacoes_confirmadas or r.observacoes_extraidas]
        existentes = {registro.dia for registro in self.cartao.registros}
        for dia in range(1, dias + 1):
            if dia not in existentes:
                self.cartao.registros.append(DiaConferido(dia=dia))
        self.cartao.registros.sort(key=lambda r: r.dia)
        self._montar_linhas()
        self._atualizar_estado()

    def _montar_linhas(self):
        for widgets in self._linhas:
            for widget in widgets["widgets"]:
                widget.destroy()
        self._linhas.clear()
        dias_mes = (calendar.monthrange(self.cartao.ano_confirmado, self.cartao.mes_confirmado)[1]
                    if self.cartao.ano_confirmado and self.cartao.mes_confirmado else 31)
        for indice, registro in enumerate(self.cartao.registros, 1):
            if (not self.mensal and registro.dia > dias_mes and
                    all(not getattr(registro, c).valor_confirmado for c in CAMPOS_HORARIO) and
                    not registro.observacoes_confirmadas):
                continue
            widgets = []
            dia_label = ttk.Frame(self.corpo)
            dia_entry = None
            if self.mensal:
                dia_entry = ttk.Entry(dia_label, width=3)
                dia_entry.insert(0, str(registro.dia))
                dia_entry.pack(side="left")
                dia_entry.bind("<KeyRelease>", lambda e: self._alterou(0))
                ttk.Label(dia_label, text=registro.origem_lado or "?").pack(side="left")
            else:
                ttk.Label(dia_label, text=f"{registro.dia:02d}", anchor="center").pack()
            dia_label.grid(row=indice, column=0, sticky="ew", padx=2, pady=2)
            widgets.append(dia_label)
            entradas = {}
            for col, nome in enumerate(CAMPOS_HORARIO, 1):
                campo = getattr(registro, nome)
                entrada = tk.Entry(self.corpo, width=9, justify="center")
                entrada.insert(0, campo.valor_confirmado or "")
                entrada.grid(row=indice, column=col, sticky="ew", padx=2, pady=2)
                entrada.bind("<KeyRelease>", lambda e, i=indice: self._alterou(i))
                entrada.bind("<FocusOut>", lambda e, i=indice: self._alterou(i))
                entradas[nome] = entrada
                widgets.append(entrada)
            total = ttk.Label(self.corpo, width=7, anchor="center")
            total.grid(row=indice, column=5, sticky="ew")
            estado = ttk.Label(self.corpo, width=22, anchor="center")
            estado.grid(row=indice, column=6, sticky="ew")
            observacoes = ttk.Entry(self.corpo, width=22)
            observacoes.insert(0, registro.observacoes_confirmadas or "")
            observacoes.grid(row=indice, column=7, sticky="ew", padx=2)
            observacoes.bind("<KeyRelease>", lambda e, i=indice: self._alterou(i))
            observacoes.bind("<FocusOut>", lambda e, i=indice: self._alterou(i))
            widgets += [total, estado, observacoes]
            self._linhas.append({"registro": registro, "entradas": entradas,
                                 "total": total, "estado": estado, "observacoes": observacoes,
                                 "widgets": widgets, "dia_entry": dia_entry})
        self._atualizar_linhas()

    def _alterou(self, indice):
        self._sincronizar()
        self.cartao.status_revisao = "PENDENTE"
        self._atualizar_linhas()
        self._atualizar_estado()
        if self.mensal:
            if self._salvamento:
                self.after_cancel(self._salvamento)
            self._salvamento = self.after(600, self.salvar_rascunho)

    def _sincronizar(self):
        if not self.cartao:
            return
        self.cartao.funcionario_confirmado = self.nome.get().strip()
        for linha in self._linhas:
            if linha.get("dia_entry"):
                try:
                    linha["registro"].dia = int(linha["dia_entry"].get())
                except ValueError:
                    linha["registro"].dia = 0
            linha["registro"].observacoes_confirmadas = linha["observacoes"].get().strip() or None
            for nome, entrada in linha["entradas"].items():
                campo = getattr(linha["registro"], nome)
                valor = entrada.get().strip() or None
                campo.valor_confirmado = valor
                campo.foi_editado = valor != (campo.valor_reanalise if campo.valor_reanalise is not None else campo.valor_extraido)

    def _atualizar_linhas(self):
        for linha in self._linhas:
            registro = linha["registro"]
            problemas = validar_dia(registro)
            ruins = {p.campo for p in problemas}
            estados = set()
            for nome, entrada in linha["entradas"].items():
                campo = getattr(registro, nome)
                estado = "ERRO" if nome in ruins else "ALTERADO" if campo.foi_editado else campo.status_leitura.value
                entrada.configure(bg=CORES.get(estado, "#ffffff"))
                if estado not in ("OK", "CONFIRMADO", "VAZIO"):
                    estados.add(estado)
            try:
                total = calcular_total_texto({nome: getattr(registro, nome).valor_confirmado for nome in CAMPOS_HORARIO})
            except ValueError:
                total = "—"
            linha["total"].configure(text=total)
            linha["estado"].configure(text=", ".join(sorted(estados)) or "OK")

    def _campos_duvidosos(self):
        if not self.cartao:
            return []
        return [f"dia {r.dia} {nome}" for r in self.cartao.registros for nome in CAMPOS_HORARIO
                if getattr(r, nome).status_leitura in (StatusLeitura.INCERTO, StatusLeitura.ILEGIVEL)
                and not getattr(r, nome).foi_editado]

    def _atualizar_estado(self):
        if not self.cartao:
            return
        problemas = validar_cartao(self.cartao)
        suspeitos = self._campos_duvidosos()
        if problemas or suspeitos:
            self.status.set(f"Existem {len(problemas)} problemas de validação e {len(suspeitos)} campos para revisão")
        else:
            self.status.set("Leitura concluída · cartão pronto para conferência")
        self._atualizar_botoes()

    def reanalisar(self):
        if not self.imagem or not self.cartao or self._reanalisou:
            return
        campos = self._campos_duvidosos()
        if not campos:
            return
        self._reanalisou = True
        LOG.info("Reanálise de cartão iniciada: campos=%d", len(campos))
        self.status.set("Reanalisando campos duvidosos...")
        self._trabalho(lambda: analisar_cartao(self.imagem.processada, campos), self._reanalise_pronta)

    def _reanalise_pronta(self, extracao, erro):
        if erro:
            messagebox.showerror("Reanálise", str(erro))
            self._atualizar_estado()
            return
        por_dia = {r.dia: r for r in extracao.registros}
        for registro in self.cartao.registros:
            novo = por_dia.get(registro.dia)
            if not novo:
                continue
            for nome in CAMPOS_HORARIO:
                atual, sugestao = getattr(registro, nome), getattr(novo, nome)
                if atual.status_leitura in (StatusLeitura.INCERTO, StatusLeitura.ILEGIVEL) and not atual.foi_editado:
                    atual.valor_reanalise = sugestao.valor
                    atual.valor_confirmado = sugestao.valor
                    atual.status_leitura = sugestao.status
                    atual.observacao = sugestao.observacao
        self._montar_linhas()
        self._atualizar_estado()

    def confirmar(self):
        if not self.cartao:
            return
        self._sincronizar()
        try:
            self.cartao.mes_confirmado = int(self.mes.get())
            self.cartao.ano_confirmado = int(self.ano.get())
        except ValueError:
            messagebox.showwarning("Dados inválidos", "Informe mês e ano numéricos")
            return
        problemas = validar_cartao(self.cartao)
        if problemas:
            LOG.warning("Confirmação bloqueada: problemas de validação=%d", len(problemas))
            resumo = "\n".join(f"Dia {p.dia or '—'} · {p.campo}: {p.mensagem}" for p in problemas[:12])
            messagebox.showwarning("Corrija antes de confirmar", resumo)
            self._atualizar_estado()
            return
        suspeitos = self._campos_duvidosos()
        if suspeitos and not messagebox.askyesno("Campos duvidosos",
                f"Ainda há {len(suspeitos)} campos incertos ou ilegíveis. Você conferiu a imagem e deseja confirmar assim mesmo?"):
            return
        try:
            if self.mensal:
                self.mensal.identificacao_revisada = self.identificacao.get()
                confirmar_mensal(self.mensal, self.lote)
                if not self.salvar_rascunho():
                    self.cartao.status_revisao = "PENDENTE"
                    return
                destino = "Lote atual · registro mensal confirmado"
            else:
                destino = salvar_cartao(self.cartao)
        except ValueError as exc:
            messagebox.showwarning("Conferência mensal", str(exc))
            return
        except OSError:
            LOG.exception("Erro ao salvar cartão")
            messagebox.showerror("Salvar", "Não foi possível salvar o cartão. Verifique a pasta de dados.")
            return
        LOG.info("Cartão confirmado")
        self.status.set("Cartão conferido e salvo")
        messagebox.showinfo("Cartão salvo", f"Resultado salvo em:\n{destino}")
