"""
Monta o conteúdo de cada aba da interface, já calculado e formatado.

Por que este módulo existe: toda regra (Δ%, cor, farol, arredondamento,
formatação brasileira) continua em Python, num lugar só. A interface em
HTML/CSS/JS só desenha o que recebe daqui, sem refazer conta nenhuma. Assim
o número que aparece na tela é o mesmo do CSV, do PDF e dos insights.

Cada função devolve dicionários e listas simples (viram JSON na API do Flask).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from . import banco
from . import formatacao as fmt
from .config import (CARTOES_CUSTOS, CARTOES_FINANCEIROS, CENARIO_LABEL, CENARIOS, DELTA_SOBRE_VALOR_ARREDONDADO,
                     FAROL_META_100_ATE, FAROL_META_300_ATE, FAROL_META_500_ATE, INDICADORES, LIMIAR_CRITICO,
                     MES_ABREV, MESES_PT, POR_CODIGO, VISAO_LABEL, VISOES, Indicador, cor_do_delta, delta_indicador,
                     severidade)
from .insights import gerar_insights, quadro_variacoes

Painel = Dict[str, Dict[str, Dict[str, float]]]
Historico = Dict[Tuple[int, int], Painel]


# --------------------------------------------------------------------------- textos curtos
def periodo_txt(ano: int, mes: int) -> str:
    return f"{MESES_PT[mes - 1]}/{ano}"


def periodo_abrev(ano: int, mes: int) -> str:
    return f"{MES_ABREV[mes - 1]}/{str(ano)[2:]}"


def ref_txt(ind: Indicador) -> str:
    return "Budget" if ind.delta_ref == "budget" else "RF"


def nota_delta() -> str:
    return ("Δ% calculado sobre os valores arredondados exibidos, como no painel de referência."
            if DELTA_SOBRE_VALOR_ARREDONDADO else "Δ% calculado sobre os valores exatos.")


# --------------------------------------------------------------------------- legendas dos cartões
def _legenda_farol() -> List[Dict[str, str]]:
    """Faróis do Cash Cost no formato usado na empresa: ● Meta 100 ● Meta 300 ● Meta 500 ● Meta 0."""
    return [
        {"cor": "vermelho", "texto": "Meta 100",
         "dica": f"Vermelho: acima do orçamento, até {fmt.pct(FAROL_META_100_ATE, 0)}"},
        {"cor": "amarelo", "texto": "Meta 300",
         "dica": f"Amarelo: próximo do orçamento (Δ entre {fmt.pct(FAROL_META_500_ATE, 0)} e "
                 f"{fmt.pct(FAROL_META_300_ATE, 0)})"},
        {"cor": "verde", "texto": "Meta 500",
         "dica": f"Verde: {fmt.pct(abs(FAROL_META_500_ATE), 0, sinal=False)} ou mais abaixo do orçamento"},
        {"cor": "preto", "texto": "Meta 0",
         "dica": f"Preto: mais de {fmt.pct(FAROL_META_100_ATE, 0, sinal=False)} acima do orçamento"},
    ]


LEGENDA = {
    "custo": [{"cor": "vermelho", "texto": "Δ > 0%"}, {"cor": "verde", "texto": "Δ ≤ 0%"}],
    "invest": [{"cor": "vermelho", "texto": "Δ < -5% ou > +5%"}, {"cor": "verde", "texto": "entre -5% e +5%"}],
    "beneficio": [{"cor": "verde", "texto": "Δ > 0%"}, {"cor": "vermelho", "texto": "Δ ≤ 0%"}],
    "cashcost": _legenda_farol(),
}

# Mesma regra em texto corrido (tabela de rastreabilidade da aba Sobre).
LEGENDA_TXT = {
    "custo": "Vermelho: Δ > 0% · Verde: Δ ≤ 0%",
    "invest": "Vermelho: Δ < -5% ou > +5% · Verde: entre -5% e +5%",
    "beneficio": "Verde: Δ > 0% · Vermelho: Δ ≤ 0%",
    "cashcost": (f"Δ contra o Budget na visão do cartão. Meta 500 (verde): Δ ≤ {fmt.pct(FAROL_META_500_ATE, 0)} · "
                 f"Meta 300 (amarelo): acima de {fmt.pct(FAROL_META_500_ATE, 0)} até {fmt.pct(FAROL_META_300_ATE, 0)} · "
                 f"Meta 100 (vermelho): até {fmt.pct(FAROL_META_100_ATE, 0)} · Meta 0 (preto): acima disso · "
                 "sem orçamento válido: indisponível"),
}


# --------------------------------------------------------------------------- estado geral (filtro do topo)
def estado(conn) -> Dict[str, object]:
    """Períodos gravados, para montar os seletores de Ano e Mês."""
    periodos = banco.periodos_disponiveis(conn)
    anos = sorted({a for a, _ in periodos}, reverse=True)
    return {
        "periodos": [list(p) for p in periodos],
        "anos": anos,
        "meses_por_ano": {str(a): sorted((m for aa, m in periodos if aa == a), reverse=True) for a in anos},
        "nomes_meses": MESES_PT,
    }


# --------------------------------------------------------------------------- aba Painel
def cartao(ind: Indicador, painel: Painel) -> Dict[str, object]:
    """Um cartão do painel: título, legenda e as três visões (Month, YTD, FY)."""
    pendente = ind.manual and not any(painel.get(ind.codigo, {}).get(v) for v in VISOES)
    visoes = []
    for visao in VISOES:
        d = painel.get(ind.codigo, {}).get(visao, {})
        delta = delta_indicador(ind, d.get("real"), d.get(ind.delta_ref))
        visoes.append({
            "nome": VISAO_LABEL[visao],
            "budget": fmt.valor_indicador(d.get("budget"), ind.unidade, ind.decimais),
            "rf": fmt.valor_indicador(d.get("rf"), ind.unidade, ind.decimais),
            "real": fmt.valor_indicador(d.get("real"), ind.unidade, ind.decimais),
            "delta": fmt.pct(delta),
            "cor": cor_do_delta(ind.cor, delta),
        })
    return {
        "codigo": ind.codigo,
        "nome": ind.nome,
        "pendente": pendente,
        "farol": ind.cor == "cashcost",
        "legenda": LEGENDA[ind.cor],
        "rotulo_delta": "ΔBud" if ind.delta_ref == "budget" else "ΔRF",
        "visoes": visoes,
    }


def tela_painel(painel: Painel, ano: int, mes: int) -> Dict[str, object]:
    return {
        "titulo": periodo_txt(ano, mes).upper(),
        "custos": [cartao(POR_CODIGO[c], painel) for c in CARTOES_CUSTOS],
        "financeiros": [cartao(POR_CODIGO[c], painel) for c in CARTOES_FINANCEIROS],
        "nota": nota_delta(),
    }


def tabela_previa(painel: Painel) -> List[Dict[str, str]]:
    """Tabela de conferência (prévia na aba Atualizar), já no padrão brasileiro."""
    linhas = []
    for ind in INDICADORES:
        if ind.manual and ind.codigo not in painel:
            continue
        for visao in VISOES:
            d = painel.get(ind.codigo, {}).get(visao, {})
            delta = delta_indicador(ind, d.get("real"), d.get(ind.delta_ref))
            linhas.append({
                "Indicador": ind.nome, "Unidade": ind.unidade, "Visão": VISAO_LABEL[visao],
                "Budget": fmt.valor_indicador(d.get("budget"), ind.unidade, ind.decimais),
                "RF": fmt.valor_indicador(d.get("rf"), ind.unidade, ind.decimais),
                "Real": fmt.valor_indicador(d.get("real"), ind.unidade, ind.decimais),
                "Variação": fmt.pct(delta),
                "Comparada com": ref_txt(ind),
            })
    return linhas


# --------------------------------------------------------------------------- gráficos (só dados; o desenho é no JS)
def grafico_variacoes(painel: Painel, visao: str) -> List[Dict[str, object]]:
    """Onde o Real mais se afasta da referência (Budget nos custos, RF nos financeiros)?"""
    barras = []
    for ind in INDICADORES:
        d = painel.get(ind.codigo, {}).get(visao, {})
        delta = delta_indicador(ind, d.get("real"), d.get(ind.delta_ref))
        if delta is None:
            continue
        barras.append({
            "indicador": ind.nome,
            "valor": delta * 100,
            "nivel": severidade(ind, delta),
            "rotulo": fmt.pct(delta),
            "real": fmt.valor_indicador(d.get("real"), ind.unidade, ind.decimais),
            "referencia": f"{CENARIO_LABEL[ind.delta_ref]}: "
                          f"{fmt.valor_indicador(d.get(ind.delta_ref), ind.unidade, ind.decimais)}",
        })
    return sorted(barras, key=lambda b: b["valor"], reverse=True)


def grafico_real_x_budget(painel: Painel, visao: str) -> List[Dict[str, object]]:
    """O custo realizado está acima ou abaixo do orçamento (e do forecast anterior)?"""
    grupos = []
    for cod in ("custo_total_mbrl", "custo_opex_mbrl"):
        ind = POR_CODIGO[cod]
        d = painel.get(cod, {}).get(visao, {})
        barras = [{"cenario": CENARIO_LABEL[c], "valor": d[c], "rotulo": fmt.num(d[c], ind.decimais)}
                  for c in CENARIOS if d.get(c) is not None]
        if barras:
            grupos.append({"indicador": ind.nome, "barras": barras})
    return grupos


def grafico_evolucao(hist: Historico, cod: str, visao: str = "month") -> Optional[Dict[str, object]]:
    """Como o indicador evolui mês a mês frente ao Budget e ao RF?"""
    ind = POR_CODIGO[cod]
    periodos = [p for p in sorted(hist) if any(hist[p].get(cod, {}).get(visao, {}).get(c) is not None for c in CENARIOS)]
    if not periodos:
        return None
    series = []
    for cen in CENARIOS:
        valores = [hist[p].get(cod, {}).get(visao, {}).get(cen) for p in periodos]
        series.append({
            "cenario": CENARIO_LABEL[cen],
            "valores": valores,
            "rotulos": [fmt.valor_indicador(v, ind.unidade, ind.decimais) if v is not None else None for v in valores],
        })
    return {
        "unidade": ind.unidade,
        "decimais_eixo": ind.decimais if ind.decimais <= 1 else 1,
        "periodos": [periodo_abrev(*p) for p in periodos],
        "series": series,
    }


# --------------------------------------------------------------------------- aba Overview / Insights
def _quadro(painel: Painel, visao: str) -> List[Dict[str, object]]:
    """Quadro 'Real x Budget x RF' com diferença em valor e em %."""
    linhas = []
    for r in quadro_variacoes(painel, visao):
        ind = r["ind"]
        linha = {"indicador": ind.nome, "real": fmt.valor_indicador(r["real"], ind.unidade, ind.decimais)}
        for ref in ("budget", "rf"):
            dif = r[f"dif_{ref}"]
            if dif is None:
                dif_txt = "—"
            else:
                arred = round(dif, ind.decimais)
                sinal = "+" if arred > 0 else "-" if arred < 0 else ""
                dif_txt = sinal + fmt.num(abs(dif), ind.decimais) + (" p.p." if ind.unidade == "%" else "")
            linha[ref] = fmt.valor_indicador(r[ref], ind.unidade, ind.decimais)
            linha[f"dif_{ref}"] = dif_txt
            linha[f"pct_{ref}"] = fmt.pct(r[f"pct_{ref}"])
            linha[f"nivel_{ref}"] = r[f"nivel_{ref}"]
        linhas.append(linha)
    return linhas


def tela_insights(conn, ano: int, mes: int, visao: str) -> Dict[str, object]:
    painel = banco.carregar_painel(conn, ano, mes)
    hist = banco.carregar_todos(conn)
    secoes = gerar_insights(ano, mes, painel, hist)
    comentarios = []
    for c in banco.listar_comentarios(conn, ano, mes):
        sobre = POR_CODIGO[c["indicador"]].nome if c["indicador"] in POR_CODIGO else "Geral"
        comentarios.append({"autor": c["autor"], "sobre": sobre, "quando": c["criado_em"], "texto": c["texto"]})
    return {
        "titulo": f"Overview — {periodo_txt(ano, mes)}",
        "visao": VISAO_LABEL[visao],
        "secoes": [
            {"titulo": titulo, "aberta": titulo == "Destaques do período",
             "itens": [{"titulo": i.titulo, "texto": i.texto, "nivel": i.nivel} for i in itens]}
            for titulo, itens in secoes.items()
        ],
        "limiar_critico": fmt.pct(LIMIAR_CRITICO, 0, sinal=False),
        "variacoes": grafico_variacoes(painel, visao),
        "real_x_budget": grafico_real_x_budget(painel, visao),
        "evolucao": [
            {"rotulo": rot, "unidade": POR_CODIGO[cod].unidade, "grafico": grafico_evolucao(hist, cod)}
            for cod, rot in (("custo_opex_mbrl", "Custo OPEX"), ("investimento_kbrl", "Investimento (CAPEX)"),
                             ("ocf_kusd", "OCF"))
        ],
        "um_mes_so": len(hist) == 1,
        "quadro": _quadro(painel, visao),
        "comentarios": comentarios,
        "alvos_comentario": [{"codigo": "geral", "nome": "Geral"}]
                            + [{"codigo": i.codigo, "nome": i.nome} for i in INDICADORES],
    }


# --------------------------------------------------------------------------- aba Atualizar
def tela_previa(resultado, ja_existe: bool) -> Dict[str, object]:
    """O que a aba Atualizar mostra depois de ler os arquivos (antes de gravar)."""
    return {
        "periodo": periodo_txt(resultado.ano, resultado.mes),
        "ano": resultado.ano,
        "mes": resultado.mes,
        "arquivos": resultado.arquivos.nomes(),
        "ja_existe": ja_existe,
        "validacoes": [{"nivel": v.nivel, "mensagem": v.mensagem} for v in resultado.validacoes],
        "tem_erro": resultado.tem_erro,
        "previa": tabela_previa(resultado.valores),
    }


def tela_investimento(conn, ano: int, mes: int) -> Dict[str, object]:
    """Os 9 campos do Investimento manual, preenchidos com o que já está gravado."""
    ind = POR_CODIGO["investimento_kbrl"]
    gravado = banco.carregar_painel(conn, ano, mes).get(ind.codigo, {})
    quando = banco.ultima_gravacao(conn, ano, mes, ind.codigo)
    return {
        "periodo": periodo_txt(ano, mes),
        "ultima_gravacao": quando.replace("T", " ") if quando else None,
        "linhas": [
            {"visao": visao, "nome": VISAO_LABEL[visao],
             "campos": [{"cenario": cen, "nome": CENARIO_LABEL[cen],
                         "valor": "" if gravado.get(visao, {}).get(cen) is None
                         else fmt.num(gravado[visao][cen], ind.decimais)} for cen in CENARIOS]}
            for visao in VISOES
        ],
    }


def ler_investimento(textos: Dict[str, Dict[str, str]]) -> Tuple[Dict[str, Dict[str, float]], List[str], List[str]]:
    """Converte os 9 textos digitados em números.

    Devolve (valores, campos com problema, avisos de coerência Month <= YTD <= FY).
    """
    lidos: Dict[str, Dict[str, float]] = {}
    problemas = []
    for visao in VISOES:
        for cen in CENARIOS:
            try:
                lidos.setdefault(visao, {})[cen] = fmt.parse_ptbr(textos.get(visao, {}).get(cen, ""))
            except ValueError:
                problemas.append(f"{VISAO_LABEL[visao]} · {CENARIO_LABEL[cen]}")
    avisos = []
    if not problemas:
        avisos = [
            f"{CENARIO_LABEL[cen]}: o valor do mês é maior que o acumulado (YTD) ou o YTD é maior que o FY."
            for cen in CENARIOS
            if not (lidos["month"][cen] <= lidos["ytd"][cen] + 1e-9 <= lidos["fy"][cen] + 2e-9)
        ]
    return lidos, problemas, avisos


# --------------------------------------------------------------------------- aba Histórico
def tela_historico(conn, anos: Sequence[int], cod: str, visao: str, recentes_primeiro: bool) -> Dict[str, object]:
    hist = banco.carregar_todos(conn)
    todos_anos = sorted({a for a, _ in hist})
    cods = [i.codigo for i in INDICADORES] if cod == "todos" else [cod]
    unico = len(cods) == 1

    linhas: List[Dict[str, object]] = []
    for per in sorted([p for p in hist if p[0] in anos], reverse=recentes_primeiro):
        if not unico:
            linhas.append({"grupo": periodo_txt(*per)})
        for ind in INDICADORES:
            if ind.codigo not in cods:
                continue
            d = hist[per].get(ind.codigo, {}).get(visao)
            if not d:
                continue
            delta = delta_indicador(ind, d.get("real"), d.get(ind.delta_ref))
            linhas.append({
                "periodo": periodo_txt(*per), "indicador": ind.nome, "unidade": ind.unidade,
                "budget": fmt.valor_indicador(d.get("budget"), ind.unidade, ind.decimais),
                "rf": fmt.valor_indicador(d.get("rf"), ind.unidade, ind.decimais),
                "real": fmt.valor_indicador(d.get("real"), ind.unidade, ind.decimais),
                "variacao": fmt.pct(delta), "nivel": severidade(ind, delta), "comparada": ref_txt(ind),
            })
    grafico = None
    if unico and anos:      # gráfico de evolução só quando um indicador é escolhido
        hist_f = {p: v for p, v in hist.items() if p[0] in anos}
        g = grafico_evolucao(hist_f, cod, visao)
        if g is not None:
            grafico = {"titulo": f"{POR_CODIGO[cod].nome} — {VISAO_LABEL[visao]}", **g}

    return {
        "resumo": (f"{len(hist)} mês(es) gravado(s), de {periodo_txt(*min(hist))} a {periodo_txt(*max(hist))}. "
                   "Cada fechamento processado é somado ao histórico; reprocessar um mês atualiza os valores dele "
                   "sem duplicar e sem tocar nos outros.") if hist else "",
        "anos": todos_anos,
        "indicadores": [{"codigo": "todos", "nome": "Todos os indicadores"}]
                       + [{"codigo": i.codigo, "nome": i.nome} for i in INDICADORES],
        "visoes": [{"codigo": v, "nome": VISAO_LABEL[v]} for v in VISOES],
        "unico": unico,
        "linhas": linhas,
        "grafico": grafico,
        "processamentos": [
            {"periodo": periodo_txt(r["ano"], r["mes"]), "quando": r["processado_em"], "vezes": r["vezes"],
             "alterados": r["n_alterados"], "arquivos": r["arquivos"]}
            for r in banco.resumo_processamentos(conn)
        ],
    }


# --------------------------------------------------------------------------- aba Sobre
def tela_sobre(conn, ano: Optional[int], mes: Optional[int], db_path: str, somente_leitura: bool) -> Dict[str, object]:
    out: Dict[str, object] = {
        "rastreabilidade": [
            {"Indicador": i.nome, "Unidade": i.unidade, "Δ contra": ref_txt(i),
             "Regra de cor": LEGENDA_TXT[i.cor], "Fonte": i.fonte}
            for i in INDICADORES
        ],
        "base": f"Base de dados em uso: {db_path}" + (" · modo somente consulta" if somente_leitura else ""),
        "ultimo": None,
    }
    if ano and mes:
        log = banco.ultimo_log(conn, ano, mes)
        out["ultimo"] = {
            "periodo": periodo_txt(ano, mes),
            "quando": log["processado_em"] if log else None,
            "registros": log["n_registros"] if log else None,
            "alterados": log["n_alterados"] if log else None,
            "arquivos": log["arquivos"] if log else None,
            "avisos": log["avisos"] if log else None,
            "auditoria": banco.contar_auditoria(conn, ano, mes),
        }
    return out
