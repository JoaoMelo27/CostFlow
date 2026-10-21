"""
Configuração dos indicadores do Painel Financeiro.

Tudo que é regra visual ou de negócio do painel fica aqui, num lugar só, para
facilitar a manutenção e a conferência com os responsáveis.

Regras de Δ% e de cor (reproduzidas do painel usado hoje no fechamento):
  - Δ% é sempre relativo: Real / referência - 1.
  - A referência é o Budget nos cartões de custo e cash cost (ΔBud) e o RF
    nos cartões financeiros e no investimento (ΔRF).
  - Cor dos pontos: ver cor_do_delta. Os 3 cartões de Cash Cost usam os faróis
    Meta 500 / 300 / 100 / 0 (ver farol_cash_cost), comparando o Real com o
    Budget na mesma visão (Month, YTD ou FY).
"""
from __future__ import annotations

from dataclasses import dataclass

# O painel de referência calcula o Δ% em cima dos valores JÁ ARREDONDADOS que
# exibe (o Δ bate com a conta feita "de cabeça" sobre os números do cartão e pode
# diferir em 0,1 p.p. da conta com todas as casas). True = reproduz o painel;
# False = Δ com valores exatos.
DELTA_SOBRE_VALOR_ARREDONDADO = True

CENARIOS = ("budget", "rf", "real")
VISOES = ("month", "ytd", "fy")
CENARIO_LABEL = {"budget": "Budget", "rf": "RF", "real": "Real"}
VISAO_LABEL = {"month": "Month", "ytd": "YTD", "fy": "FY"}
MESES_PT = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
            "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
MES_ABREV = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


# Faróis dos 3 cartões de Cash Cost (Total USD/t, OPEX USD/t e G&A R$/t).
# Δ = Real / Budget - 1, na MESMA visão (Month, YTD ou FY) e já arredondado como no painel.
# É o único lugar com esses limites: cartões, tabelas, gráficos, insights, histórico e PDF leem daqui.
#   Meta 500 (verde)    : Δ <= FAROL_META_500_ATE    -> custo 2% ou mais abaixo do orçamento   [regra recebida]
#   Meta 300 (amarelo)  : até FAROL_META_300_ATE     -> próximo do orçamento
#   Meta 100 (vermelho) : até FAROL_META_100_ATE     -> acima do orçamento, até ~4% acima       [regra recebida]
#   Meta 0   (preto)    : acima de FAROL_META_100_ATE -> muito acima do orçamento
# O 0% (fim do amarelo) e o 4% como início do preto vêm da leitura do texto da regra, não de um
# parâmetro da base original: confirmar com os responsáveis e, se mudar, mudar só aqui.
FAROL_META_500_ATE = -0.02
FAROL_META_300_ATE = 0.0
FAROL_META_100_ATE = 0.04
_EPS = 1e-9

# Limiares usados SÓ nos insights, no histórico e nos gráficos (os pontos dos
# cartões seguem a regra do painel, em cor_do_delta).
# 5% é a mesma faixa que o painel já usa para Investimento; 10% para "crítico"
# é uma sugestão inicial - confirmar com os responsáveis.
LIMIAR_RELEVANTE = 0.05   # variação mínima (em módulo) para entrar nos destaques
LIMIAR_CRITICO = 0.10     # desvio desfavorável a partir daqui = vermelho


@dataclass(frozen=True)
class Indicador:
    codigo: str
    nome: str             # título do cartão
    unidade: str          # unidade em que o valor é ARMAZENADO
    decimais: int         # casas decimais exibidas no painel
    delta_ref: str        # 'budget' ou 'rf': contra o que o Δ% é calculado
    cor: str              # regra de cor: 'custo' | 'invest' | 'beneficio' | 'cashcost'
    grupo: str            # 'custos' ou 'financeiro'
    fonte: str            # rastreabilidade: de onde vem o número
    manual: bool = False  # True = não vem das planilhas; é digitado na aba Atualizar


INDICADORES = [
    Indicador("custo_total_mbrl", "Custo Total MBRL", "MBRL", 1, "budget", "custo", "custos",
              "Arquivo CUSTO TOTAL > aba Cash Cost 2026 Completo > 'Custo Total (R$) | sem Efeito Corp com Nexa Energy'"),
    Indicador("custo_opex_mbrl", "Custo OPEX MBRL", "MBRL", 1, "budget", "custo", "custos",
              "Arquivo Gestão de Custos OPEX 26 > aba Cash Cost 2026 Completo > 'Custo Total (R$) | sem Efeito Corp com Nexa Energy'"),
    Indicador("investimento_kbrl", "Investimento (Capex/Opex/Oro) KBRL", "KBRL", 0, "rf", "invest", "custos",
              "Preenchimento manual na aba Atualizar (os 3 arquivos de entrada não trazem este dado)", manual=True),
    Indicador("receita_liquida_kusd", "Receita Líquida KUSD", "KUSD", 0, "rf", "beneficio", "financeiro",
              "Arquivo OCF > aba BD > '(=) Net Revenues'"),
    Indicador("ocf_kusd", "OCF KUSD", "KUSD", 0, "rf", "beneficio", "financeiro",
              "Arquivo OCF > aba BD > '(=) OCF'"),
    Indicador("cash_cost_total_usdt", "Cash Cost Total Vazante USD/t", "USD/t", 2, "budget", "cashcost", "custos",
              "Arquivo CUSTO TOTAL > aba Cash Cost 2026 Completo > 'Cash Cost (US$/t Prod. Alimentada)'"),
    Indicador("cash_cost_opex_usdt", "Cash Cost OPEX Vazante USD/t", "USD/t", 2, "budget", "cashcost", "custos",
              "Arquivo Gestão de Custos OPEX 26 > aba Cash Cost 2026 Completo > 'Cash Cost (US$/t Prod. Alimentada)'"),
    Indicador("cash_cost_ga_rt", "Cash Cost G&A R$/t", "R$/t", 1, "budget", "cashcost", "custos",
              "Arquivo Gestão de Custos OPEX 26 > aba 'Meta G&A sem nexa e sem corp' > linha 'R$/Ton'"),
    Indicador("margem_pct", "Margem", "%", 1, "rf", "beneficio", "financeiro",
              "Calculado: OCF / Receita Líquida (arquivo OCF)"),
    Indicador("nsr", "NSR", "NSR", 2, "rf", "beneficio", "financeiro",
              "Arquivo OCF > aba BD > 'NSR Financial'"),
]
POR_CODIGO = {i.codigo: i for i in INDICADORES}
MANUAIS = [i for i in INDICADORES if i.manual]            # digitados à mão (hoje: Investimento)
AUTOMATICOS = [i for i in INDICADORES if not i.manual]    # vêm das planilhas da pasta entrada

# Ordem dos cartões no painel (mesma do painel de referência).
CARTOES_CUSTOS = ["custo_total_mbrl", "custo_opex_mbrl", "investimento_kbrl",
                  "cash_cost_total_usdt", "cash_cost_opex_usdt", "cash_cost_ga_rt"]
CARTOES_FINANCEIROS = ["receita_liquida_kusd", "ocf_kusd", "margem_pct", "nsr"]


def cor_do_delta(regra: str, delta: float | None) -> str:
    """Cor do ponto ao lado do Δ%: 'verde' | 'vermelho' | 'amarelo' | 'preto' | 'cinza' (sem dado)."""
    if delta is None:
        return "cinza"
    if regra == "custo":        # menor é melhor
        return "vermelho" if delta > 0 else "verde"
    if regra == "invest":       # dentro de ±5% está ok
        return "vermelho" if (delta < -0.05 or delta > 0.05) else "verde"
    if regra == "beneficio":    # maior é melhor
        return "verde" if delta > 0 else "vermelho"
    if regra == "cashcost":
        return farol_cash_cost(delta)
    return "cinza"


def farol_cash_cost(delta: float | None) -> str:
    """Farol do Cash Cost: 'verde' (Meta 500) | 'amarelo' (Meta 300) | 'vermelho' (Meta 100) | 'preto' (Meta 0).

    Sem orçamento válido (delta None) devolve 'cinza' = indisponível, nunca um farol inventado.
    """
    if delta is None:
        return "cinza"
    if delta <= FAROL_META_500_ATE + _EPS:
        return "verde"
    if delta <= FAROL_META_300_ATE + _EPS:
        return "amarelo"
    if delta <= FAROL_META_100_ATE + _EPS:
        return "vermelho"
    return "preto"


def delta_relativo(real: float | None, ref: float | None) -> float | None:
    if real is None or ref in (None, 0):
        return None
    return real / ref - 1.0


def delta_indicador(ind: Indicador, real: float | None, ref: float | None) -> float | None:
    """Δ% de um indicador do painel, seguindo DELTA_SOBRE_VALOR_ARREDONDADO."""
    if real is None or ref is None:
        return None
    if DELTA_SOBRE_VALOR_ARREDONDADO:
        real, ref = round(real, ind.decimais), round(ref, ind.decimais)
    return delta_relativo(real, ref)


def favoravel(ind: Indicador, delta: float | None) -> bool | None:
    """Leitura favorável/desfavorável do Δ (direção do indicador, não causa)."""
    if delta is None:
        return None
    if ind.cor in ("custo", "cashcost"):
        return delta <= 0
    if ind.cor == "invest":
        return -0.05 <= delta <= 0.05
    return delta > 0


def severidade(ind: Indicador, delta: float | None) -> str:
    """'verde' | 'amarelo' | 'vermelho' | 'preto' | 'cinza' para insights, histórico e gráficos.

    verde = favorável · amarelo = desfavorável abaixo de LIMIAR_CRITICO ·
    vermelho = desfavorável a partir de LIMIAR_CRITICO. Nos Cash Costs vale o farol dos cartões.
    """
    if ind.cor == "cashcost":
        return farol_cash_cost(delta)
    fav = favoravel(ind, delta)
    if fav is None:
        return "cinza"
    if fav:
        return "verde"
    return "vermelho" if abs(delta) >= LIMIAR_CRITICO else "amarelo"
