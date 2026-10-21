"""
Overview / Insights - 100% determinístico.

Cada frase é montada a partir dos números já calculados (nenhuma IA gera
número ou explicação). Regra do projeto: NUNCA afirmar a CAUSA de uma
variação. O texto descreve o que os números mostram (quanto, contra o quê,
quanto do desvio vem de cada parte); causas entram depois, como comentário
humano (gestão de custos e financeiro/CAPEX).

O banco guarda os números por indicador (10 indicadores x Month/YTD/FY x
Budget/RF/Real). Por isso a "contribuição" aqui é entre indicadores que se
somam de verdade (Custo Total = Custo OPEX + restante; Receita -> OCF), e não
por centro de custo ou conta contábil: essa abertura não está no banco.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from . import formatacao as fmt
from .config import (CENARIO_LABEL, INDICADORES, LIMIAR_CRITICO, LIMIAR_RELEVANTE, MESES_PT, POR_CODIGO,
                    VISAO_LABEL, VISOES, Indicador, cor_do_delta, delta_indicador, delta_relativo, favoravel,
                    severidade)

Painel = Dict[str, Dict[str, Dict[str, float]]]   # {indicador: {visao: {cenario: valor}}}
Historico = Dict[Tuple[int, int], Painel]         # {(ano, mes): painel}

# Mudança mínima (em pontos percentuais do Δ) entre dois meses para dizer que o desvio "ampliou"/"diminuiu".
LIMIAR_MUDANCA_DESVIO = 0.03
# Para o critério estatístico de "fora do padrão": meses anteriores mínimos e nº de desvios-padrão.
MIN_MESES_ESTATISTICA = 4
Z_FORA_DO_PADRAO = 2.0

_UNID_TXT = {"MBRL": "MBRL", "KBRL": "KBRL", "KUSD": "KUSD", "USD/t": "USD/t", "R$/t": "R$/t", "%": "p.p.", "NSR": ""}
_VISAO_TXT = {"month": "no mês", "ytd": "no acumulado (YTD)", "fy": "no ano (FY)"}


@dataclass
class Insight:
    texto: str
    nivel: str = "neutro"     # 'verde' | 'amarelo' | 'vermelho' | 'preto' | 'neutro'
    titulo: str = ""


@dataclass
class Linha:
    ind: Indicador
    visao: str
    real: Optional[float]
    ref: Optional[float]
    delta: Optional[float]
    cor: str
    fav: Optional[bool]
    nivel: str


# --------------------------------------------------------------------------- utilidades de texto
def _s(valor: float, dec: int) -> str:
    """Número com sinal explícito no padrão brasileiro: +4,3 / -0,4 / 0,0."""
    r = round(valor, dec)
    if r == 0:
        return fmt.num(0, dec)
    return ("+" if r > 0 else "-") + fmt.num(abs(r), dec)


def _dif_txt(ind: Indicador, dif: float) -> str:
    unid = _UNID_TXT.get(ind.unidade, ind.unidade)
    return f"{_s(dif, ind.decimais)} {unid}".strip()


def _var_txt(ind: Indicador, real: Optional[float], ref: Optional[float]) -> Optional[str]:
    """'+4,3 MBRL (+8,4%)'. Margem: em pontos percentuais (a variação relativa de uma razão confunde)."""
    if real is None or ref is None:
        return None
    dif = real - ref
    if ind.unidade == "%":
        rel = delta_indicador(ind, real, ref)
        extra = f" ({fmt.pct(rel)} relativo)" if rel is not None else ""
        return f"{_dif_txt(ind, dif)}{extra}"
    delta = delta_indicador(ind, real, ref)
    return f"{_dif_txt(ind, dif)} ({fmt.pct(delta)})" if delta is not None else _dif_txt(ind, dif)


def _val(ind: Indicador, v: Optional[float]) -> str:
    u = "" if ind.unidade in ("NSR", "%") else f" {ind.unidade}"
    return f"{fmt.valor_indicador(v, ind.unidade, ind.decimais)}{u}"


def _periodo_txt(ano: int, mes: int) -> str:
    return f"{MESES_PT[mes - 1]}/{ano}"


def _ref_nome(ind: Indicador) -> str:
    return CENARIO_LABEL[ind.delta_ref]


# --------------------------------------------------------------------------- cálculo base
def calcular(painel: Painel) -> List[Linha]:
    out = []
    for ind in INDICADORES:
        for visao in VISOES:
            d = painel.get(ind.codigo, {}).get(visao, {})
            real, ref = d.get("real"), d.get(ind.delta_ref)
            delta = delta_indicador(ind, real, ref)
            out.append(Linha(ind, visao, real, ref, delta, cor_do_delta(ind.cor, delta),
                             favoravel(ind, delta), severidade(ind, delta)))
    return out


def quadro_variacoes(painel: Painel, visao: str) -> List[Dict[str, object]]:
    """Linhas do quadro 'Real x Budget x RF' de uma visão (usado pela tela de insights)."""
    rows = []
    for ind in INDICADORES:
        d = painel.get(ind.codigo, {}).get(visao, {})
        real = d.get("real")
        linha: Dict[str, object] = {"ind": ind, "real": real, "budget": d.get("budget"), "rf": d.get("rf")}
        for ref in ("budget", "rf"):
            v = d.get(ref)
            delta = delta_indicador(ind, real, v)
            linha[f"dif_{ref}"] = None if real is None or v is None else real - v
            linha[f"pct_{ref}"] = delta
            linha[f"nivel_{ref}"] = "cinza" if (ind.cor == "cashcost" and ref != "budget") else severidade(ind, delta)
        rows.append(linha)
    return rows


# --------------------------------------------------------------------------- blocos de insight
def _destaques(linhas: List[Linha], painel: Painel, periodo: str) -> List[Insight]:
    out: List[Insight] = []
    validas = [l for l in linhas if l.delta is not None]
    desf = sorted([l for l in validas if l.fav is False and abs(l.delta) >= LIMIAR_RELEVANTE],
                  key=lambda l: abs(l.delta), reverse=True)[:3]
    fav = sorted([l for l in validas if l.fav and l.ind.cor != "invest" and abs(l.delta) >= LIMIAR_RELEVANTE],
                 key=lambda l: abs(l.delta), reverse=True)[:2]

    n_mes = [l for l in validas if l.visao == "month"]
    n_fav = sum(1 for l in n_mes if l.fav)
    out.append(Insight(
        f"Em {periodo}, {n_fav} de {len(n_mes)} indicadores estão em leitura favorável no mês "
        f"(Δ contra Budget nos cartões de custo e cash cost; contra RF nos financeiros e no investimento).",
        "verde" if n_fav == len(n_mes) else "neutro", "Visão geral"))

    for l in desf:
        out.append(Insight(
            f"Real {_val(l.ind, l.real)} {_VISAO_TXT[l.visao]} contra {_ref_nome(l.ind)} {_val(l.ind, l.ref)}: "
            f"{_var_txt(l.ind, l.real, l.ref)}.",
            l.nivel, f"Atenção · {l.ind.nome}"))
    for l in fav:
        out.append(Insight(
            f"Real {_val(l.ind, l.real)} {_VISAO_TXT[l.visao]} contra {_ref_nome(l.ind)} {_val(l.ind, l.ref)}: "
            f"{_var_txt(l.ind, l.real, l.ref)}.",
            "verde", f"Favorável · {l.ind.nome}"))
    for comp in (
        _composicao(painel, "custo_total_mbrl", "custo_opex_mbrl", "Custo OPEX",
                    "restante (Custo Total − Custo OPEX)", "month", "budget"),
        _composicao_ocf(painel, "month", "rf"),
    ):
        if comp is not None:
            comp.titulo = "De onde vem · " + comp.titulo
            out.append(comp)
    if not desf and not fav:
        out.append(Insight(
            f"Nenhum indicador tem desvio igual ou acima de {fmt.pct(LIMIAR_RELEVANTE, 0, sinal=False)} "
            "contra a referência em nenhuma das três visões.", "verde"))
    return out


def _aumentos_reducoes(linhas: List[Linha]) -> List[Insight]:
    validas = [l for l in linhas if l.delta is not None and l.delta != 0]
    aum = sorted([l for l in validas if l.delta > 0], key=lambda l: l.delta, reverse=True)[:3]
    red = sorted([l for l in validas if l.delta < 0], key=lambda l: l.delta)[:3]
    out: List[Insight] = []
    for l in aum:
        out.append(Insight(f"{_val(l.ind, l.real)} contra {_ref_nome(l.ind)} {_val(l.ind, l.ref)}: "
                           f"{_var_txt(l.ind, l.real, l.ref)}.",
                           l.nivel, f"Maior aumento · {l.ind.nome} · {VISAO_LABEL[l.visao]}"))
    for l in red:
        out.append(Insight(f"{_val(l.ind, l.real)} contra {_ref_nome(l.ind)} {_val(l.ind, l.ref)}: "
                           f"{_var_txt(l.ind, l.real, l.ref)}.",
                           l.nivel, f"Maior redução · {l.ind.nome} · {VISAO_LABEL[l.visao]}"))
    return out


def _partilha(parte: float, total: float) -> str:
    return f"{fmt.num(abs(parte / total) * 100, 0)}% do desvio"


def _composicao(painel: Painel, total_cod: str, parte_cod: str, parte_rot: str, resto_rot: str,
                visao: str, ref: str) -> Optional[Insight]:
    """Decompõe o desvio do indicador-total em parte + restante (aditivos nos arquivos-fonte)."""
    t = painel.get(total_cod, {}).get(visao, {})
    p = painel.get(parte_cod, {}).get(visao, {})
    if any(x is None for x in (t.get("real"), t.get(ref), p.get("real"), p.get(ref))):
        return None
    ind = POR_CODIGO[total_cod]
    dt = t["real"] - t[ref]
    dp = p["real"] - p[ref]
    dr = dt - dp
    if round(dt, ind.decimais) == 0:
        return None
    delta = delta_indicador(ind, t["real"], t[ref])
    return _frase_composicao(ind, f"{ind.nome} · {VISAO_LABEL[visao]} vs {CENARIO_LABEL[ref]}",
                             dt, dp, dr, parte_rot, resto_rot, delta)


def _frase_composicao(ind: Indicador, titulo: str, dt: float, dp: float, dr: float,
                      parte_rot: str, resto_rot: str, delta: Optional[float]) -> Insight:
    cab = f"Desvio de {_dif_txt(ind, dt)}" + (f" ({fmt.pct(delta)})" if delta is not None else "")
    if dp * dt >= 0 and dr * dt >= 0:   # as duas partes empurram no mesmo sentido do total
        corpo = (f"{parte_rot}: {_dif_txt(ind, dp)} ({_partilha(dp, dt)}); "
                 f"{resto_rot}: {_dif_txt(ind, dr)} ({_partilha(dr, dt)}).")
    else:                                # sentidos opostos: percentual de partilha confundiria
        corpo = (f"{parte_rot}: {_dif_txt(ind, dp)}; {resto_rot}: {_dif_txt(ind, dr)} "
                 "— efeitos em sentidos opostos.")
    corpo = corpo[0].upper() + corpo[1:]
    return Insight(f"{cab}. {corpo}", severidade(ind, delta), titulo)


def _composicao_ocf(painel: Painel, visao: str, ref: str) -> Optional[Insight]:
    """OCF = Receita − demais itens: separa o efeito da receita do efeito dos demais itens."""
    ocf_ind = POR_CODIGO["ocf_kusd"]
    o = painel.get("ocf_kusd", {}).get(visao, {})
    r = painel.get("receita_liquida_kusd", {}).get(visao, {})
    if any(x is None for x in (o.get("real"), o.get(ref), r.get("real"), r.get(ref))):
        return None
    d_ocf = o["real"] - o[ref]
    d_rec = r["real"] - r[ref]
    if round(d_ocf, ocf_ind.decimais) == 0:
        return None
    delta = delta_indicador(ocf_ind, o["real"], o[ref])
    return _frase_composicao(
        ocf_ind, f"OCF · {VISAO_LABEL[visao]} vs {CENARIO_LABEL[ref]}", d_ocf, d_rec, d_ocf - d_rec,
        "efeito da Receita Líquida", "efeito dos demais itens (diferença Receita − OCF)", delta)


def _composicoes(painel: Painel) -> List[Insight]:
    out: List[Optional[Insight]] = []
    for visao, ref in (("month", "budget"), ("month", "rf"), ("ytd", "budget"), ("ytd", "rf"), ("fy", "budget")):
        out.append(_composicao(painel, "custo_total_mbrl", "custo_opex_mbrl", "Custo OPEX",
                               "restante (Custo Total − Custo OPEX)", visao, ref))
    for visao, ref in (("month", "budget"), ("ytd", "budget"), ("fy", "budget")):
        out.append(_composicao(painel, "cash_cost_total_usdt", "cash_cost_opex_usdt", "Cash Cost OPEX",
                               "restante (Cash Cost Total − OPEX)", visao, ref))
    for visao, ref in (("month", "rf"), ("ytd", "rf"), ("fy", "rf"), ("month", "budget")):
        out.append(_composicao_ocf(painel, visao, ref))
    return [i for i in out if i is not None]


def _comparar(atual: Painel, base: Painel, rotulo_base: str) -> List[Insight]:
    """Real do mês: variação contra outro período (mês anterior / mesmo mês do ano anterior)."""
    var: List[Tuple[Indicador, float, float, float]] = []
    for ind in INDICADORES:
        a = atual.get(ind.codigo, {}).get("month", {}).get("real")
        b = base.get(ind.codigo, {}).get("month", {}).get("real")
        v = delta_relativo(a, b)
        if v is None or v == 0:
            continue
        var.append((ind, a, b, v))
    relevantes = [x for x in var if abs(x[3]) >= LIMIAR_RELEVANTE]
    out: List[Insight] = []
    aum = sorted([x for x in relevantes if x[3] > 0], key=lambda x: x[3], reverse=True)[:3]
    red = sorted([x for x in relevantes if x[3] < 0], key=lambda x: x[3])[:3]
    for rot, lista in (("Aumento", aum), ("Redução", red)):
        for ind, a, b, v in lista:
            if ind.unidade == "%":
                var_txt = f"{_dif_txt(ind, a - b)} ({fmt.pct(v)} relativo)"
            else:
                var_txt = f"{_dif_txt(ind, a - b)} ({fmt.pct(v)})"
            nivel = "neutro" if ind.cor in ("invest", "cashcost") else severidade(ind, v)
            out.append(Insight(f"{_val(ind, b)} → {_val(ind, a)}: {var_txt}.", nivel,
                               f"{rot} · {ind.nome} · vs {rotulo_base}"))
    if not out:
        out.append(Insight(f"Nenhum indicador variou {fmt.pct(LIMIAR_RELEVANTE, 0, sinal=False)} ou mais "
                           f"(Real do mês) frente a {rotulo_base}.", "neutro"))
    return out


def _serie_real_mes(historico: Historico, ate: Tuple[int, int], cod: str) -> List[Tuple[Tuple[int, int], float]]:
    out = []
    for per in sorted(historico):
        if per > ate:
            continue
        v = historico[per].get(cod, {}).get("month", {}).get("real")
        if v is not None:
            out.append((per, v))
    return out


def _tendencias(historico: Historico, atual: Tuple[int, int]) -> List[Insight]:
    n_per = len([p for p in historico if p <= atual])
    if n_per < 2:
        return [Insight("Há apenas 1 mês no histórico. Comparação com meses anteriores e tendências aparecem "
                        "conforme novos fechamentos forem gravados (tendência exige 3 meses).")]
    out: List[Insight] = []
    # (a) sequência de meses consecutivos na mesma direção (Real do mês)
    for ind in INDICADORES:
        serie = _serie_real_mes(historico, atual, ind.codigo)
        if len(serie) < 3:
            continue
        vals = [v for _, v in serie]
        sentido = 1 if vals[-1] > vals[-2] else -1 if vals[-1] < vals[-2] else 0
        if sentido == 0:
            continue
        n = 1
        for i in range(len(vals) - 2, 0, -1):
            if (vals[i] - vals[i - 1]) * sentido > 0:
                n += 1
            else:
                break
        if n < 2:
            continue
        trecho = " → ".join(fmt.valor_indicador(v, ind.unidade, ind.decimais) for v in vals[-(n + 1):])
        total = delta_relativo(vals[-1], vals[-(n + 1)])
        nivel = "neutro" if ind.cor in ("invest", "cashcost") else severidade(ind, total if total is not None else 0)
        unid = _UNID_TXT.get(ind.unidade, ind.unidade)
        trecho = f"{trecho} {unid}".strip()
        no_periodo = f" — {fmt.pct(total)} no período" if total is not None else ""
        out.append(Insight(
            f"Real do mês {'subiu' if sentido > 0 else 'caiu'} {n} meses seguidos ({trecho}){no_periodo}.",
            nivel, f"Sequência · {ind.nome}"))
    # (b) desvio do mês contra a referência: ampliou ou diminuiu frente ao mês anterior do histórico
    anterior = max(p for p in historico if p < atual)
    mud: List[Tuple[float, Indicador, float, float]] = []
    for ind in INDICADORES:
        da = historico[atual].get(ind.codigo, {}).get("month", {})
        db_ = historico[anterior].get(ind.codigo, {}).get("month", {})
        x = delta_indicador(ind, da.get("real"), da.get(ind.delta_ref))
        y = delta_indicador(ind, db_.get("real"), db_.get(ind.delta_ref))
        if x is None or y is None:
            continue
        if abs(abs(x) - abs(y)) >= LIMIAR_MUDANCA_DESVIO:
            mud.append((abs(x) - abs(y), ind, x, y))
    for diff, ind, x, y in sorted(mud, key=lambda t: abs(t[0]), reverse=True)[:4]:
        out.append(Insight(
            f"Desvio do mês contra {_ref_nome(ind)}: {fmt.pct(y)} em {_periodo_txt(*anterior)} → {fmt.pct(x)} em "
            f"{_periodo_txt(*atual)} ({'ampliou' if diff > 0 else 'diminuiu'}).",
            severidade(ind, x), f"Desvio · {ind.nome}"))
    if not out:
        out.append(Insight("Sem sequências de 2 ou mais meses na mesma direção e sem mudança relevante no desvio "
                           f"(mínimo de {fmt.pct(LIMIAR_MUDANCA_DESVIO, 0, sinal=False)} de diferença no Δ)."))
    return out


def _fora_do_padrao(linhas: List[Linha], historico: Historico, atual: Tuple[int, int]) -> List[Insight]:
    out: List[Insight] = []
    crit = sorted([l for l in linhas if l.fav is False and l.delta is not None and abs(l.delta) >= LIMIAR_CRITICO],
                  key=lambda l: abs(l.delta), reverse=True)
    for l in crit[:6]:
        out.append(Insight(
            f"Real {_val(l.ind, l.real)} {_VISAO_TXT[l.visao]} contra {_ref_nome(l.ind)} {_val(l.ind, l.ref)}: "
            f"{_var_txt(l.ind, l.real, l.ref)} — desvio desfavorável a partir de {fmt.pct(LIMIAR_CRITICO, 0, sinal=False)}.",
            l.nivel, f"{l.ind.nome} · {VISAO_LABEL[l.visao]}"))
    if len(crit) > 6:
        out.append(Insight(f"Mais {len(crit) - 6} combinações indicador/visão acima do mesmo limite (ver quadro abaixo)."))

    # sentido do desvio muda entre as visões
    por = {(l.ind.codigo, l.visao): l for l in linhas}
    for ind in INDICADORES:
        ds = [por[(ind.codigo, v)].delta for v in VISOES]
        if any(d is None for d in ds) or ind.cor == "invest":
            continue
        if len({d > 0 for d in ds if d != 0}) > 1:
            out.append(Insight(
                f"O sentido do desvio contra {_ref_nome(ind)} muda entre as visões "
                f"(Month {fmt.pct(ds[0])}, YTD {fmt.pct(ds[1])}, FY {fmt.pct(ds[2])}).",
                "amarelo", ind.nome))

    # critério estatístico: Real do mês contra a média dos meses anteriores do histórico
    for ind in INDICADORES:
        serie = _serie_real_mes(historico, atual, ind.codigo)
        if len(serie) < MIN_MESES_ESTATISTICA + 1:
            continue
        anteriores = [v for _, v in serie[:-1]][-12:]
        media = statistics.fmean(anteriores)
        dp = statistics.pstdev(anteriores)
        atual_v = serie[-1][1]
        if dp == 0 or media == 0:
            continue
        z = (atual_v - media) / dp
        if abs(z) >= Z_FORA_DO_PADRAO and abs(atual_v / media - 1) >= LIMIAR_RELEVANTE:
            out.append(Insight(
                f"Real do mês {_val(ind, atual_v)} está {fmt.num(abs(z), 1)} desvios-padrão "
                f"{'acima' if z > 0 else 'abaixo'} da média dos {len(anteriores)} meses anteriores "
                f"({_val(ind, media)}); diferença de {fmt.pct(atual_v / media - 1)}. "
                "Comparação simples, sem ajuste de sazonalidade.",
                "amarelo", f"Fora do histórico · {ind.nome}"))
    if not out:
        out.append(Insight("Nenhuma situação fora do padrão pelos critérios: desvio desfavorável ≥ "
                           f"{fmt.pct(LIMIAR_CRITICO, 0, sinal=False)}, inversão de sentido entre visões ou "
                           "distância estatística do histórico.", "verde"))
    return out


# --------------------------------------------------------------------------- API principal
def gerar_insights(ano: int, mes: int, painel: Painel, historico: Optional[Historico] = None) -> Dict[str, List[Insight]]:
    """Retorna {titulo da seção: [Insight]}.

    historico: {(ano, mes): painel} com TODOS os períodos gravados (pode incluir o atual).
    """
    historico = dict(historico or {})
    historico[(ano, mes)] = painel
    atual = (ano, mes)
    linhas = calcular(painel)
    periodo = _periodo_txt(ano, mes)
    secoes: Dict[str, List[Insight]] = {}

    secoes["Destaques do período"] = _destaques(linhas, painel, periodo)
    secoes["Maiores aumentos e reduções contra a referência"] = _aumentos_reducoes(linhas)
    comp = _composicoes(painel)
    if comp:
        secoes["De onde vem o desvio"] = comp

    anteriores = [p for p in historico if p < atual]
    evo: List[Insight] = []
    if anteriores:
        ant = max(anteriores)
        evo.extend(_comparar(painel, historico[ant], _periodo_txt(*ant)))
    ano_ant = (ano - 1, mes)
    if ano_ant in historico:
        evo.extend(_comparar(painel, historico[ano_ant], f"{_periodo_txt(*ano_ant)} (mesmo mês do ano anterior)"))
    if evo:
        secoes["Evolução frente a períodos anteriores"] = evo

    secoes["Tendências"] = _tendencias(historico, atual)
    secoes["Situações fora do padrão"] = _fora_do_padrao(linhas, historico, atual)
    secoes["Como ler"] = [Insight(
        "Os textos descrevem apenas o que os números mostram; nenhuma causa é atribuída. Real = forecast vigente "
        "(nos meses fechados já reflete o realizado); em FY, Real é a projeção do ano. As causas devem ser "
        "informadas pelos responsáveis na área de comentários. "
        f"Faixas de cor: verde = favorável; amarelo = desfavorável abaixo de {fmt.pct(LIMIAR_CRITICO, 0, sinal=False)}; "
        f"vermelho = desfavorável a partir de {fmt.pct(LIMIAR_CRITICO, 0, sinal=False)}. Nos três Cash Costs vale o farol "
        "Meta 500 (verde) / 300 (amarelo) / 100 (vermelho) / 0 (preto) contra o Budget, igual aos cartões (limites em config.py).")]
    return secoes
