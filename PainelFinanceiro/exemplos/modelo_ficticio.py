"""
Modelo financeiro FICTÍCIO usado para gerar as planilhas de exemplo.

Nada aqui vem da empresa: os números são inventados (com semente fixa, para
saírem sempre iguais) só para o painel ter o que mostrar no Codespace e nas
apresentações. O que importa é que as planilhas geradas tenham o MESMO
layout das planilhas reais, para que os leitores do sistema funcionem igual.

Como os cenários funcionam (igual ao fechamento real):
  - Budget: orçamento definido no início do ano. Não muda.
  - Forecast do ciclo k: meses 1..k já são realizado; meses k+1..12 são
    projeção feita a partir do orçamento ajustado pelo desvio recente.
  - No fechamento do mês M:
        coluna "Real" do painel = forecast do ciclo M      (forecast vigente)
        coluna "RF"   do painel = forecast do ciclo M - 1  (forecast anterior)
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List

ANO = 2026
MESES = list(range(1, 13))
SEMENTE = 2026

# Sazonalidade da produção (fator sobre a média) - inventada.
SAZONALIDADE = [0.95, 0.92, 1.00, 1.02, 1.04, 1.00, 1.03, 1.05, 1.00, 1.02, 0.98, 0.99]

# Linhas de custo OPEX (R$ por mês, valor médio do orçamento) - inventadas.
LINHAS_OPEX = {
    "Pessoal Próprio": 13_500_000,
    "Materiais e Insumos": 11_800_000,
    "Serviços de Terceiros": 9_600_000,
    "Energia Elétrica": 7_900_000,
    "Manutenção": 5_700_000,
}
# Itens que só entram no Custo Total (fora do OPEX) - inventados.
LINHAS_FORA_OPEX = {
    "Frete e Logística": 4_300_000,
    "Royalties e CFEM": 3_100_000,
    "Rateio Corporativo": 2_600_000,
}
# Centros de custo de G&A (R$ por mês) - inventados. O total de G&A também entra no OPEX.
LINHAS_GA = {
    "Gerência Geral": 820_000,
    "Administrativo": 1_550_000,
    "Recursos Humanos": 1_080_000,
    "Tecnologia da Informação": 990_000,
    "Suprimentos": 760_000,
    "Jurídico": 480_000,
    "Segurança Patrimonial": 870_000,
}

PRODUCAO_MEDIA_T = 152_000      # toneladas alimentadas por mês
CAMBIO_BUDGET = 5.20            # R$ por US$
PRECO_BUDGET = 2_300.0          # US$ por tonelada de metal contido
TEOR_RECUPERADO = 0.118         # t de metal por t alimentada
DEDUCOES = 0.30                 # parcela da receita bruta que sai como deduções (TC/RC etc.)
INVESTIMENTO_MEDIO_KBRL = 21_000


Serie = Dict[int, float]        # {mes: valor}


def _forecast(budget: Serie, realizado: Serie, ciclo: int) -> Serie:
    """Forecast feito depois de fechar o mês `ciclo`.

    Meses já fechados repetem o realizado. Meses futuros = orçamento corrigido
    por 70% do desvio médio dos últimos 3 meses fechados (um jeito simples e
    comum de projetar). Ciclo 0 = orçamento puro.
    """
    if ciclo <= 0:
        return dict(budget)
    ultimos = [m for m in MESES if m <= ciclo][-3:]
    desvio = sum(realizado[m] / budget[m] - 1 for m in ultimos) / len(ultimos)
    return {m: realizado[m] if m <= ciclo else budget[m] * (1 + 0.7 * desvio) for m in MESES}


@dataclass
class Base:
    """Séries mensais 'de verdade' do ano fictício: orçamento e realizado."""
    budget: Dict[str, Serie]
    realizado: Dict[str, Serie]

    def cenario(self, item: str, ciclo: int) -> Serie:
        return _forecast(self.budget[item], self.realizado[item], ciclo)


def gerar_base(semente: int = SEMENTE) -> Base:
    """Monta orçamento e realizado de todas as séries que as planilhas usam."""
    rng = random.Random(semente)
    budget: Dict[str, Serie] = {}
    realizado: Dict[str, Serie] = {}

    def serie(nome: str, orcado: Serie, desvio_medio: float, oscilacao: float) -> None:
        budget[nome] = orcado
        realizado[nome] = {m: v * (1 + rng.gauss(desvio_medio, oscilacao)) for m, v in orcado.items()}

    serie("producao_t", {m: PRODUCAO_MEDIA_T * SAZONALIDADE[m - 1] for m in MESES}, -0.03, 0.035)
    serie("cambio", {m: CAMBIO_BUDGET for m in MESES}, 0.03, 0.04)
    serie("preco_usd_t", {m: PRECO_BUDGET for m in MESES}, 0.05, 0.05)

    # custos: parte fixa + parte que acompanha a produção
    for grupo, desvio in ((LINHAS_OPEX, 0.05), (LINHAS_FORA_OPEX, 0.03), (LINHAS_GA, -0.02)):
        for nome, media in grupo.items():
            serie(nome, {m: media * (0.65 + 0.35 * SAZONALIDADE[m - 1]) for m in MESES}, desvio, 0.06)

    serie("outros_ocf_kusd", {m: 5_200.0 for m in MESES}, 0.05, 0.15)
    serie("investimento_kbrl", {m: INVESTIMENTO_MEDIO_KBRL * (0.7 + 0.6 * rng.random()) for m in MESES}, -0.08, 0.15)
    return Base(budget=budget, realizado=realizado)


# --------------------------------------------------------------------------- séries derivadas de um cenário
@dataclass
class Cenario:
    """Todas as séries mensais de UM cenário (Budget, RF ou Real), já derivadas."""
    producao: Serie
    cambio: Serie
    linhas_opex: Dict[str, Serie]
    linhas_fora_opex: Dict[str, Serie]
    linhas_ga: Dict[str, Serie]
    ga_total: Serie
    custo_opex: Serie
    custo_total: Serie
    receita_bruta: Serie        # KUSD
    receita_liquida: Serie      # KUSD
    custo_kusd: Serie
    outros_kusd: Serie
    ocf: Serie                  # KUSD
    investimento: Serie         # KBRL


def montar_cenario(base: Base, ciclo: int) -> Cenario:
    """ciclo = -1 devolve o Budget; ciclo k >= 0 devolve o forecast feito depois do mês k."""
    def s(item: str) -> Serie:
        return dict(base.budget[item]) if ciclo < 0 else base.cenario(item, ciclo)

    producao, cambio, preco = s("producao_t"), s("cambio"), s("preco_usd_t")
    linhas_ga = {n: s(n) for n in LINHAS_GA}
    ga_total = {m: sum(l[m] for l in linhas_ga.values()) for m in MESES}
    linhas_opex = {n: s(n) for n in LINHAS_OPEX}
    linhas_fora = {n: s(n) for n in LINHAS_FORA_OPEX}
    custo_opex = {m: sum(l[m] for l in linhas_opex.values()) + ga_total[m] for m in MESES}
    custo_total = {m: custo_opex[m] + sum(l[m] for l in linhas_fora.values()) for m in MESES}
    receita_bruta = {m: producao[m] * TEOR_RECUPERADO * preco[m] / 1000 for m in MESES}
    receita_liquida = {m: receita_bruta[m] * (1 - DEDUCOES) for m in MESES}
    custo_kusd = {m: custo_total[m] / cambio[m] / 1000 for m in MESES}
    outros = s("outros_ocf_kusd")
    ocf = {m: receita_liquida[m] - custo_kusd[m] - outros[m] for m in MESES}
    return Cenario(producao, cambio, linhas_opex, linhas_fora, linhas_ga, ga_total, custo_opex, custo_total,
                   receita_bruta, receita_liquida, custo_kusd, outros, ocf, s("investimento_kbrl"))


def cenarios_do_fechamento(base: Base, mes: int) -> Dict[str, Cenario]:
    """Os três cenários que as planilhas do fechamento do mês `mes` trazem."""
    return {"budget": montar_cenario(base, -1), "rf": montar_cenario(base, mes - 1), "real": montar_cenario(base, mes)}


# --------------------------------------------------------------------------- razões (US$/t, R$/t)
def cash_cost_usd_t(custo: Serie, cambio: Serie, producao: Serie) -> Serie:
    return {m: custo[m] / cambio[m] / producao[m] for m in MESES}


def razao_ano(numerador: Serie, denominador: Serie) -> float:
    """Razão do ano inteiro (coluna de total anual da planilha)."""
    return sum(numerador.values()) / sum(denominador.values())


def custo_em_usd(custo: Serie, cambio: Serie) -> Serie:
    return {m: custo[m] / cambio[m] for m in MESES}


# --------------------------------------------------------------------------- valores que o painel deve mostrar
def valores_esperados(mes: int, base: Base | None = None) -> Dict[str, Dict[str, Dict[str, float]]]:
    """O que o painel deve mostrar no fechamento de `mes`, calculado direto pelo modelo.

    Serve de gabarito para o teste de regressão: segue as regras de negócio
    documentadas (Month = mês; YTD de valores = soma; YTD de razões = média
    simples dos meses; FY = coluna de total anual) sem passar pelos leitores
    de planilha, então se um leitor quebrar o teste acusa.
    """
    base = base or gerar_base()
    cen = cenarios_do_fechamento(base, mes)
    ate = [m for m in MESES if m <= mes]
    out: Dict[str, Dict[str, Dict[str, float]]] = {}

    def guardar(cod: str, cenario: str, month: float, ytd: float, fy: float) -> None:
        for visao, v in (("month", month), ("ytd", ytd), ("fy", fy)):
            out.setdefault(cod, {}).setdefault(visao, {})[cenario] = v

    for nome, c in cen.items():
        for cod, custo in (("custo_total_mbrl", c.custo_total), ("custo_opex_mbrl", c.custo_opex)):
            guardar(cod, nome, custo[mes] / 1e6, sum(custo[m] for m in ate) / 1e6, sum(custo.values()) / 1e6)
        for cod, custo in (("cash_cost_total_usdt", c.custo_total), ("cash_cost_opex_usdt", c.custo_opex)):
            cc = cash_cost_usd_t(custo, c.cambio, c.producao)
            guardar(cod, nome, cc[mes], sum(cc[m] for m in ate) / len(ate),
                    razao_ano(custo_em_usd(custo, c.cambio), c.producao))
        ga_rt = {m: c.ga_total[m] / c.producao[m] for m in MESES}
        guardar("cash_cost_ga_rt", nome, ga_rt[mes], sum(ga_rt[m] for m in ate) / len(ate),
                razao_ano(c.ga_total, c.producao))
        rl, ocf = c.receita_liquida, c.ocf
        rl_v = (rl[mes], sum(rl[m] for m in ate), sum(rl.values()))
        ocf_v = (ocf[mes], sum(ocf[m] for m in ate), sum(ocf.values()))
        guardar("receita_liquida_kusd", nome, *rl_v)
        guardar("ocf_kusd", nome, *ocf_v)
        guardar("margem_pct", nome, *(100 * o / r for o, r in zip(ocf_v, rl_v)))
        nsr = {m: rl[m] * 1000 / c.producao[m] for m in MESES}
        guardar("nsr", nome, nsr[mes],
                sum(rl[m] for m in ate) * 1000 / sum(c.producao[m] for m in ate),
                razao_ano({m: rl[m] * 1000 for m in MESES}, c.producao))
    return out


def investimento_do_fechamento(mes: int, base: Base | None = None) -> Dict[str, Dict[str, float]]:
    """Os 9 valores de Investimento (KBRL) que alguém digitaria à mão no fechamento de `mes`."""
    base = base or gerar_base()
    out: Dict[str, Dict[str, float]] = {"month": {}, "ytd": {}, "fy": {}}
    for nome, c in cenarios_do_fechamento(base, mes).items():
        inv = c.investimento
        out["month"][nome] = round(inv[mes])
        out["ytd"][nome] = round(sum(inv[m] for m in MESES if m <= mes))
        out["fy"][nome] = round(sum(inv.values()))
    return out


def lista_meses(ate: int) -> List[int]:
    return [m for m in MESES if m <= ate]
