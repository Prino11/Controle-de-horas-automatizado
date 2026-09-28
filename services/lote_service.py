"""Reconhecimento estrutural, pareamento conservador e montagem mensal."""
import calendar
import hashlib
from datetime import datetime, timezone

from models.cartao_ponto import CAMPOS_HORARIO, CartaoConferido, DiaConferido
from models.extracao import CartaoExtraido, LeituraCartao, StatusLeitura, TipoLadoCartao
from models.lote import CartaoMensalFuncionario, LoteCartoes, PaginaCartao, StatusCartao
from services.validation_service import validar_cartao

A, B, DESCONHECIDO = TipoLadoCartao.LADO_A, TipoLadoCartao.LADO_B, TipoLadoCartao.DESCONHECIDO


def detectar_lado(leitura: LeituraCartao) -> TipoLadoCartao:
    if leitura.status_lado != StatusLeitura.CONFIRMADO:
        return DESCONHECIDO
    if leitura.numero_lado == 1:
        return A
    if leitura.numero_lado == 2:
        return B
    return DESCONHECIDO


def matricula_segura(leitura: LeituraCartao) -> str | None:
    campo = leitura.matricula
    return campo.valor.strip().upper() if campo.status == StatusLeitura.CONFIRMADO and campo.valor and campo.valor.strip() else None


def _competencia_compativel(leitura: LeituraCartao, lote: LoteCartoes) -> bool:
    return (leitura.mes.valor in (None, lote.mes) and leitura.ano.valor in (None, lote.ano))


def _competencia_segura(leitura: LeituraCartao, lote: LoteCartoes) -> bool:
    return (leitura.mes.valor == lote.mes and leitura.ano.valor == lote.ano and
            leitura.mes.status == leitura.ano.status == StatusLeitura.CONFIRMADO)


def _montar_conferencia(lote, pagina_a, pagina_b, anterior=None):
    paginas = [p for p in (pagina_a, pagina_b) if p]
    leitura = pagina_a.resultado
    cartao = CartaoConferido(arquivo_origem=pagina_a.arquivo_origem,
        arquivos_origem=list(dict.fromkeys(p.arquivo_origem for p in paginas)),
        funcionario_extraido=leitura.nome.valor, funcionario_confirmado=leitura.nome.valor or "",
        mes_extraido=leitura.mes.valor, ano_extraido=leitura.ano.valor,
        mes_confirmado=lote.mes, ano_confirmado=lote.ano, modelo_ia=pagina_a.modelo_ia)
    for pagina in paginas:
        bruto = CartaoExtraido(funcionario=pagina.resultado.nome.valor, registros=pagina.resultado.registros)
        parcial = CartaoConferido.da_extracao(pagina.arquivo_origem, pagina.modelo_ia or "", bruto)
        for registro in parcial.registros:
            registro.origem_lado = detectar_lado(pagina.resultado).value
            registro.origem_pagina = pagina.id
            registro.dia_extraido = registro.dia
            cartao.registros.append(registro)
    # Mantém correções já feitas quando uma segunda face chega depois.
    if anterior:
        cartao.id_cartao = anterior.id_cartao
        cartao.funcionario_confirmado = anterior.funcionario_confirmado
        anteriores = {(r.origem_pagina, r.dia_extraido): r for r in anterior.registros}
        for r in cartao.registros:
            antigo = anteriores.get((r.origem_pagina, r.dia_extraido))
            if antigo:
                r.dia = antigo.dia
                r.observacoes_confirmadas = antigo.observacoes_confirmadas
                for campo in CAMPOS_HORARIO:
                    valor = getattr(antigo, campo)
                    if valor.foi_editado or valor.valor_reanalise is not None:
                        setattr(r, campo, valor.model_copy(deep=True))
    existentes = {r.dia for r in cartao.registros}
    for dia in range(1, calendar.monthrange(lote.ano, lote.mes)[1] + 1):
        if dia not in existentes:
            origem = pagina_a if dia <= 15 else pagina_b
            registro = DiaConferido(dia=dia, origem_lado="A" if dia <= 15 else "B",
                                   origem_pagina=origem.id if origem else None)
            if anterior:
                antigo = next((r for r in anterior.registros if r.dia == dia and r.dia_extraido is None), None)
                if antigo:
                    registro = antigo.model_copy(deep=True)
                    registro.origem_pagina = origem.id if origem else None
            cartao.registros.append(registro)
    cartao.registros.sort(key=lambda r: r.dia)
    return cartao


def problemas_mensal(mensal: CartaoMensalFuncionario, lote: LoteCartoes) -> list[str]:
    problemas = [f"Dia {p.dia or '—'}: {p.mensagem}" for p in validar_cartao(mensal.conferencia)]
    if not mensal.lado_b:
        problemas.append("Associe o lado B antes de confirmar")
    if not mensal.matricula or not mensal.matricula.strip():
        problemas.append("Revise a matrícula na página do lado A")
    if (mensal.conferencia.mes_confirmado, mensal.conferencia.ano_confirmado) != (lote.mes, lote.ano):
        problemas.append("A competência deve ser a mesma do lote")
    for pid in (mensal.lado_a, mensal.lado_b):
        if pid and lote.paginas[pid].status == "POSSIVEL_DUPLICATA":
            problemas.append("Resolva a possível duplicata na lista de páginas")
    for r in mensal.conferencia.registros:
        if (r.origem_lado == "A" and not 1 <= r.dia <= 15) or (r.origem_lado == "B" and not 16 <= r.dia <= 31):
            problemas.append(f"Dia {r.dia} fora da quinzena da origem {r.origem_lado}; corrija o dia")
    return problemas


def atualizar_status(mensal, lote):
    if mensal.conferencia.status_revisao == "CONFIRMADO" and not problemas_mensal(mensal, lote):
        mensal.status = StatusCartao.CONFIRMADO
    elif not mensal.lado_b:
        mensal.status = (StatusCartao.REVISAO_NECESSARIA if mensal.alertas else StatusCartao.AGUARDANDO_LADO_B)
    else:
        incertos = any(getattr(r, c).status_leitura in (StatusLeitura.INCERTO, StatusLeitura.ILEGIVEL)
                       and not getattr(r, c).foi_editado for r in mensal.conferencia.registros for c in CAMPOS_HORARIO)
        mensal.status = (StatusCartao.REVISAO_NECESSARIA if mensal.alertas or incertos or problemas_mensal(mensal, lote)
                         else StatusCartao.COMPLETO)


def reconciliar_lote(lote: LoteCartoes) -> None:
    elegiveis = {A: [], B: []}
    chaves = {}
    for pagina in lote.paginas.values():
        pagina.alertas = []
        leitura = pagina.resultado
        if pagina.ignorada:
            pagina.status = "IGNORADO"
            continue
        if leitura is None:
            pagina.status = "ERRO_LEITURA" if pagina.erro else "AGUARDANDO_LEITURA"
            continue
        lado = detectar_lado(leitura)
        if lado == DESCONHECIDO:
            pagina.status = "NAO_RECONHECIDO"
            pagina.alertas.append("Lado desconhecido ou evidências contraditórias; revise a identificação 1/2")
            continue
        if lado != pagina.lado_esperado and not pagina.lado_aceito_manualmente:
            pagina.status = "LADO_INESPERADO"
            pagina.alertas.append(f"Detectado lado {lado.value} na importação de lados {pagina.lado_esperado.value}")
            continue
        if not _competencia_compativel(leitura, lote):
            pagina.status = "COMPETENCIA_DIFERENTE"
            pagina.alertas.append("Mês/ano diferente do lote; revise ou importe no lote correto")
            continue
        pagina.status = "LIDO"
        for r in leitura.registros:
            if (lado == A and not 1 <= r.dia <= 15) or (lado == B and not 16 <= r.dia <= calendar.monthrange(lote.ano, lote.mes)[1]):
                pagina.alertas.append(f"Dia {r.dia} fora da quinzena esperada")
        matricula = matricula_segura(leitura)
        if matricula:
            chave = (matricula, leitura.mes.valor, leitura.ano.valor, lado)
            chaves.setdefault(chave, []).append(pagina)
        elegiveis[lado].append(pagina)
    for grupo in chaves.values():
        if len(grupo) > 1:
            for pagina in grupo:
                pagina.status = "POSSIVEL_DUPLICATA"
                pagina.alertas.append("Matrícula, competência e lado repetidos; nenhuma página foi substituída")
    antigos = {f.lado_a: f for f in lote.funcionarios}
    funcionarios = []
    for pagina in elegiveis[A]:
        leitura = pagina.resultado
        mensal = antigos.get(pagina.id) or CartaoMensalFuncionario(
            nome=leitura.nome.valor or "", matricula=leitura.matricula.valor,
            mes=lote.mes, ano=lote.ano, lado_a=pagina.id,
            conferencia=_montar_conferencia(lote, pagina, None))
        mensal.nome = leitura.nome.valor or ""
        mensal.matricula = leitura.matricula.valor
        mensal.alertas = [a for a in pagina.alertas if "Dia " not in a]
        if not _competencia_segura(leitura, lote) or not matricula_segura(leitura) or leitura.nome.status != StatusLeitura.CONFIRMADO:
            if not mensal.identificacao_revisada:
                mensal.alertas.append("Identificação precisa de conferência humana")
        candidatos = []
        for pb in elegiveis[B]:
            if pb.status == "POSSIVEL_DUPLICATA" or pagina.status == "POSSIVEL_DUPLICATA":
                continue
            if pb.associar_a:
                if pb.associar_a == pagina.id:
                    candidatos.append(pb)
                continue
            mat = matricula_segura(leitura)
            mesmos_a = [pa for pa in elegiveis[A] if matricula_segura(pa.resultado) == mat]
            if (mat and len(mesmos_a) == 1 and mat == matricula_segura(pb.resultado)
                    and _competencia_segura(leitura, lote) and _competencia_segura(pb.resultado, lote)):
                candidatos.append(pb)
        pb = candidatos[0] if len(candidatos) == 1 else None
        if len(candidatos) > 1:
            mensal.alertas.append("Mais de um lado B candidato; escolha a página correta")
        assinatura = hashlib.sha256((pagina.resultado.model_dump_json() +
            (pb.id + pb.resultado.model_dump_json() if pb else "")).encode()).hexdigest()
        if assinatura != mensal.assinatura_fontes:
            mensal.conferencia = _montar_conferencia(lote, pagina, pb, mensal.conferencia)
            mensal.assinatura_fontes = assinatura
        mensal.lado_b = pb.id if pb else None
        mensal.pareamento_manual = bool(pb and pb.pareamento_manual)
        if pb:
            pb.status = "ASSOCIADO"
            if not _competencia_segura(pb.resultado, lote) and not mensal.identificacao_revisada:
                mensal.alertas.append("Confira mês/ano do lado B")
        atualizar_status(mensal, lote)
        funcionarios.append(mensal)
    lote.funcionarios = funcionarios
    for pagina in elegiveis[B]:
        if pagina.status == "LIDO":
            pagina.status = "PAREAMENTO_PENDENTE"
    lote.atualizado_em = datetime.now(timezone.utc)


def associar_manualmente(lote, pagina_b_id, funcionario_id):
    mensal = next(f for f in lote.funcionarios if f.id == funcionario_id)
    pb, pa = lote.paginas[pagina_b_id], lote.paginas[mensal.lado_a]
    if pb.ignorada or pb.resultado is None or detectar_lado(pb.resultado) != B:
        raise ValueError("Revise o lado desta página antes de associar")
    if pb.status == "POSSIVEL_DUPLICATA" or pa.status == "POSSIVEL_DUPLICATA":
        raise ValueError("Resolva as duplicatas antes de associar")
    if not _competencia_compativel(pb.resultado, lote):
        raise ValueError("A competência do lado B não corresponde ao lote")
    if mensal.lado_b and mensal.lado_b != pb.id:
        raise ValueError("O funcionário já tem lado B; ignore ou desassocie a página anterior")
    if any(f.lado_b == pb.id and f.id != mensal.id for f in lote.funcionarios):
        raise ValueError("Esta página já pertence a outro funcionário")
    ma, mb = matricula_segura(pa.resultado), matricula_segura(pb.resultado)
    if ma and mb and ma != mb:
        raise ValueError("As matrículas divergem; corrija a identificação antes de associar")
    pb.associar_a, pb.pareamento_manual, pb.lado_aceito_manualmente = pa.id, True, True
    reconciliar_lote(lote)


def confirmar_mensal(mensal, lote):
    problemas = problemas_mensal(mensal, lote)
    if not mensal.identificacao_revisada:
        problemas.append("Confirme a revisão da identificação e das duas faces")
    if problemas:
        raise ValueError("\n".join(problemas[:15]))
    mensal.conferencia.status_revisao = "CONFIRMADO"
    mensal.conferencia.data_confirmacao = datetime.now(timezone.utc)
    mensal.status = StatusCartao.CONFIRMADO


def resumo_lote(lote):
    return {"funcionarios": len(lote.funcionarios),
            "lados_a": sum(bool(f.lado_a) for f in lote.funcionarios),
            "lados_b": sum(bool(f.lado_b) for f in lote.funcionarios),
            **{s.value: sum(f.status == s for f in lote.funcionarios) for s in StatusCartao},
            "paginas_pendentes": sum(p.status not in ("LIDO", "ASSOCIADO", "IGNORADO") for p in lote.paginas.values())}
