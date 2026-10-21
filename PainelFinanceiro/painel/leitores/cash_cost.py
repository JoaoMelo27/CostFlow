"""
Lê a aba "Cash Cost 2026 Completo" (existe nos dois arquivos de custo) e devolve:

  - Custo (R$): linha "Custo Total (R$) | sem Efeito Corp com Nexa Energy".
        No arquivo "CUSTO TOTAL..." vira o Custo Total do painel;
        no arquivo "Gestão de Custos OPEX..." vira o Custo OPEX.
  - Cash Cost (US$/t): linha "Cash Cost (US$/t Prod. Alimentada)", mesma lógica.

Regras de cálculo (validadas contra o painel de referência):
  - Month: valor da coluna do mês pedido.
  - FY:    valor da coluna de total anual do cenário.
  - YTD de valores em R$ (que se somam): soma de janeiro até o mês pedido.
  - YTD de razões (US$/t): MÉDIA SIMPLES dos valores mensais de janeiro até o
    mês. Uma média ponderada por produção/câmbio foi testada e descartada:
    não batia com o painel.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .planilha import SheetGrid, find_scenario_blocks_by_date_row, load_sheet, months_up_to

SHEET_NAME = "Cash Cost 2026 Completo"
LABEL_COL = 1  # nesta aba os rótulos de linha ficam na coluna B

ROW_LABELS = {
    "custo": "Custo Total (R$) | sem Efeito Corp com Nexa Energy",
    "cash_cost_usdt": "Cash Cost (US$/t Prod. Alimentada)",
}

# Palavras que identificam cada bloco de colunas. A ordem importa: Budget, depois RF-1, depois Real.
SCENARIO_KEYWORDS = {
    "budget": ["BUDGET", "ORÇAMENTO"],
    "rf": ["RF-1", "RF 1"],
    "real": ["REAL", "REALIZADO"],
}


@dataclass
class CashCostResult:
    custo: Dict[str, Dict[str, float]]           # {cenario: {month, ytd, fy}} em R$
    cash_cost_usdt: Dict[str, Dict[str, float]]  # {cenario: {month, ytd, fy}} em US$/t


def _row_labels_to_index(grid: SheetGrid) -> Dict[str, int]:
    idx = {}
    for key, label in ROW_LABELS.items():
        r = grid.find_label_row(LABEL_COL, label, exact=True)
        if r is None:
            raise ValueError(f"Não achei a linha '{label}' na aba {SHEET_NAME!r}.")
        idx[key] = r
    return idx


def extract_cash_cost(file_path: str, ano: int, mes: int) -> CashCostResult:
    grid = load_sheet(file_path, SHEET_NAME, max_rows=110)
    rows = _row_labels_to_index(grid)

    blocks = find_scenario_blocks_by_date_row(
        grid,
        header_row_search_range=range(0, 6),
        fy_label_row_offset_range=range(-3, 1),
        scenario_keywords=SCENARIO_KEYWORDS,
    )
    for scen in ("budget", "rf", "real"):
        if scen not in blocks:
            raise ValueError(f"Não localizei o bloco de colunas do cenário '{scen}' em {file_path}.")

    custo_row = rows["custo"]
    cc_row = rows["cash_cost_usdt"]
    custo_out: Dict[str, Dict[str, float]] = {}
    cc_out: Dict[str, Dict[str, float]] = {}

    for scen, block in blocks.items():
        month_col = block.month_cols.get((ano, mes))
        if month_col is None:
            raise ValueError(f"O cenário '{scen}' não tem coluna para {ano}-{mes:02d} em {file_path}.")

        def val(row_idx: int, col: int) -> float:
            v = grid.cell(row_idx, col)
            return float(v) if isinstance(v, (int, float)) else 0.0

        meses_ytd = [ym for ym in months_up_to(ano, mes) if ym in block.month_cols]

        # Custo em R$: soma no YTD
        custo_out[scen] = {
            "month": val(custo_row, month_col),
            "ytd": sum(val(custo_row, block.month_cols[ym]) for ym in meses_ytd),
            "fy": val(custo_row, block.fy_col),
        }

        # Cash Cost em US$/t: média simples no YTD
        ytd_vals = [val(cc_row, block.month_cols[ym]) for ym in meses_ytd]
        cc_out[scen] = {
            "month": val(cc_row, month_col),
            "ytd": (sum(ytd_vals) / len(ytd_vals)) if ytd_vals else 0.0,
            "fy": val(cc_row, block.fy_col),
        }

    return CashCostResult(custo=custo_out, cash_cost_usdt=cc_out)
