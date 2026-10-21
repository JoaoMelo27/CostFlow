"""
Lê o Cash Cost G&A R$/t da aba "Meta G&A sem nexa e sem corp" (tabela
dinâmica de G&A já filtrada sem Nexa Energy e sem corporativo).

Por que esta aba e não a aba "G&A": a aba "G&A" cheia inclui Nexa Energy e
Royalties e dá um R$/t alguns por cento diferente do painel. Esta aba bate
com o painel nas 9 combinações (Month/YTD/FY × Budget/RF/Real).

A aba tem três tabelas dinâmicas empilhadas, identificadas pelo rótulo na coluna A:
    "Budget 26"  -> coluna "Budget" do painel
    "RF -1"      -> coluna "RF" do painel   (forecast anterior)
    "RF"         -> coluna "Real" do painel (forecast vigente; meses fechados já são o realizado)
Mesma convenção do arquivo OCF. Atenção: o cabeçalho interno dos três blocos diz
"Soma de Real 2026", o que engana. O que vale é o rótulo do bloco.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .planilha import SheetGrid, load_sheet, parse_pt_month_label

SHEET_NAME = "Meta G&A sem nexa e sem corp"
BLOCK_START_LABELS = {
    "budget": "Budget 26",
    "rf": "RF -1",
    "real": "RF",
}


@dataclass
class GAResult:
    budget: Dict[str, float]
    real: Dict[str, float]
    rf: Dict[str, float]


def _extract_block_rt(grid: SheetGrid, block_start_row: int, ano: int, mes: int) -> Dict[str, float]:
    """A partir da linha onde começa um bloco, acha o cabeçalho de meses e a linha 'R$/Ton'.

    - month e fy: lidos direto da linha 'R$/Ton' (já calculada na tabela).
    - ytd: média simples dos valores mensais de 'R$/Ton' de janeiro até o mês
      (mesma convenção do painel para razões).
    """
    header_row = None
    for r in range(block_start_row, block_start_row + 6):
        v = grid.cell(r, 0)
        if isinstance(v, str) and v.strip() == "Rótulos de Linha":
            header_row = r
            break
    if header_row is None:
        raise ValueError(f"Não achei o cabeçalho de meses do bloco que começa na linha {block_start_row}.")

    month_to_col: Dict[int, int] = {}
    header = grid.row(header_row)
    for col, text in header.items():
        if isinstance(text, str):
            m = parse_pt_month_label(text)
            if m:
                month_to_col[m] = col
    total_col = max(c for c, t in header.items() if isinstance(t, str))   # "Total Geral" é a última coluna

    def find_row(label: str) -> int:
        for r in range(header_row, header_row + 40):
            v = grid.cell(r, 0)
            if isinstance(v, str) and v.strip() == label:
                return r
        raise ValueError(f"Não achei a linha '{label}' no bloco da linha {block_start_row}.")

    rt_row = find_row("R$/Ton")

    def val(row: int, col: int) -> float:
        v = grid.cell(row, col)
        return float(v) if isinstance(v, (int, float)) else 0.0

    month_col = month_to_col.get(mes)
    if month_col is None:
        raise ValueError(f"Bloco na linha {block_start_row} não tem coluna para o mês {mes}.")

    ytd_vals = [val(rt_row, month_to_col[m]) for m in range(1, mes + 1) if m in month_to_col]
    return {
        "month": val(rt_row, month_col),
        "ytd": sum(ytd_vals) / len(ytd_vals) if ytd_vals else 0.0,
        "fy": val(rt_row, total_col),
    }


def extract_ga_cash_cost_rt(file_path: str, ano: int, mes: int) -> GAResult:
    grid = load_sheet(file_path, SHEET_NAME, max_rows=150)
    out = {}
    for scen, label in BLOCK_START_LABELS.items():
        start_row = grid.find_label_row(0, label, exact=True)
        if start_row is None:
            raise ValueError(f"Não achei o bloco '{label}' na aba G&A.")
        out[scen] = _extract_block_rt(grid, start_row, ano, mes)
    return GAResult(budget=out["budget"], rf=out["rf"], real=out["real"])
