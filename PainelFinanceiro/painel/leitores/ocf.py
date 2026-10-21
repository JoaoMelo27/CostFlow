"""
Lê do arquivo OCF (aba "BD"):

  - Receita Líquida KUSD : linha "(=) Net Revenues"
  - OCF KUSD             : linha "(=) OCF"
  - NSR                  : linha "NSR Financial" (é uma razão; YTD e FY vêm prontos da tabela)
  - Margem               : OCF / Receita Líquida, CALCULADA aqui. Não é a linha "OCF Margin"
                           da planilha, que usa outra base e dá valor diferente do painel.

Convenção de cenários deste arquivo (achado importante de regra de negócio):
    coluna "Budget" do painel = cenário BUD´AA
    coluna "RF"     do painel = cenário RF ANT´AA  (forecast anterior)
    coluna "Real"   do painel = cenário RF´AA      (forecast vigente; nos meses
                                                    fechados já é o realizado)
Não existe um cenário "Real" separado neste arquivo.

O Investimento (Capex/Opex/Oro) NÃO é lido daqui: é digitado na aba Atualizar.

A tabela agregada (MONTH / YTD / FY) é calculada pelo próprio Excel a partir
de uma célula-seletor de mês. Por isso este leitor confere se o mês do seletor
é o mês que você está processando e, se não for, dá erro em vez de gravar
números do mês errado.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .planilha import SheetGrid, excel_serial_to_date, is_plausible_date_serial, load_sheet

SHEET_NAME = "BD"
LABEL_COL = 3

ROW_LABELS = {
    "receita": "(=) Net Revenues",
    "ocf": "(=) OCF",
    "nsr": "NSR Financial",
}

SCENARIOS = ("budget", "rf", "real")
# prefixo do rótulo de cenário -> nome usado no sistema (o ano é montado a partir do ano pedido)
SCENARIO_PREFIX = {"budget": "BUD", "rf": "RF ANT", "real": "RF"}
AGG_GROUPS = {"month": "MONTH", "ytd": "YTD", "fy": "FY"}


@dataclass
class OCFResult:
    receita: Dict[str, Dict[str, float]]
    ocf: Dict[str, Dict[str, float]]
    nsr: Dict[str, Dict[str, float]]
    margem: Dict[str, Dict[str, float]]
    selector_month: Tuple[int, int]
    checks: List[str] = field(default_factory=list)


def _find_header_row(grid: SheetGrid) -> Tuple[int, int]:
    """Linha de cabeçalho = a que tem o texto 'MONTH' numa das primeiras colunas
    (ao lado da célula-seletor de mês). Devolve (linha, coluna do seletor)."""
    for r in range(0, 12):
        for c, v in grid.row(r).items():
            if c < 10 and isinstance(v, str) and v.strip() == "MONTH":
                return r, c
    raise ValueError("Não achei a linha de cabeçalho (célula 'MONTH') na aba BD.")


def _raw_blocks(grid: SheetGrid, hdr: int, ano: int) -> Dict[str, Dict[Tuple[int, int], int]]:
    """{cenario: {(ano, mes): coluna}} dos blocos mensais 'brutos' (12 colunas por cenário)."""
    labels = {c: v for c, v in grid.row(hdr).items() if isinstance(v, str) and 10 < c < 148}
    out = {}
    for scen in SCENARIOS:
        wanted = f"{SCENARIO_PREFIX[scen]} {ano}"
        starts = [c for c, v in labels.items() if v.strip() == wanted]
        if not starts:
            raise ValueError(f"Não achei o bloco '{wanted}' na aba BD.")
        start = min(starts)
        month_cols = {}
        for c in range(start, start + 12):
            d = grid.cell(hdr + 1, c)
            if is_plausible_date_serial(d):
                dt = excel_serial_to_date(d)
                month_cols[(dt.year, dt.month)] = c
        out[scen] = month_cols
    return out


def _agg_cols(grid: SheetGrid, hdr: int, ano: int) -> Dict[str, Dict[str, int]]:
    """{visao: {cenario: coluna}} na tabela agregada (grupos MONTH / YTD / FY)."""
    yy = f"{ano % 100:02d}"
    starts = sorted((c, v.strip()) for c, v in grid.row(hdr).items() if isinstance(v, str) and c >= 100)
    out: Dict[str, Dict[str, int]] = {}
    for i, (start, name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else start + 13
        for visao, group_name in AGG_GROUPS.items():
            if name != group_name:
                continue
            cols = {}
            for c in range(start, end):
                lab = grid.cell(hdr + 1, c)
                if not isinstance(lab, str):
                    continue
                for scen in SCENARIOS:
                    if lab.strip() == f"{SCENARIO_PREFIX[scen]}´{yy}":
                        cols[scen] = c
            out[visao] = cols
    for visao in AGG_GROUPS:
        for scen in SCENARIOS:
            if scen not in out.get(visao, {}):
                raise ValueError(f"Não achei a coluna agregada {visao}/{scen} na aba BD.")
    return out


def extract_ocf(file_path: str, ano: int, mes: int) -> OCFResult:
    grid = load_sheet(file_path, SHEET_NAME)
    hdr, sel_col = _find_header_row(grid)

    sel_serial = grid.cell(hdr + 1, sel_col)
    if not is_plausible_date_serial(sel_serial):
        raise ValueError("Célula-seletor de mês do arquivo OCF não tem uma data válida.")
    sel = excel_serial_to_date(sel_serial)
    selector_month = (sel.year, sel.month)
    if selector_month != (ano, mes):
        raise ValueError(
            f"O arquivo OCF está posicionado em {sel.year}-{sel.month:02d}, "
            f"mas você pediu {ano}-{mes:02d}. Ajuste o mês no arquivo OCF e salve de novo."
        )

    rows: Dict[str, int] = {}
    for key, label in ROW_LABELS.items():
        r = grid.find_label_row(LABEL_COL, label, exact=True)
        if r is None:
            raise ValueError(f"Não achei a linha '{label}' na aba BD.")
        rows[key] = r

    agg = _agg_cols(grid, hdr, ano)
    raw = _raw_blocks(grid, hdr, ano)

    def num(r: int, c: int) -> float:
        v = grid.cell(r, c)
        return float(v) if isinstance(v, (int, float)) else 0.0

    def from_agg(key: str) -> Dict[str, Dict[str, float]]:
        return {scen: {visao: num(rows[key], agg[visao][scen]) for visao in AGG_GROUPS} for scen in SCENARIOS}

    receita = from_agg("receita")
    ocf = from_agg("ocf")
    nsr = from_agg("nsr")

    # Conferência: o MONTH da tabela agregada tem que ser igual ao valor da
    # coluna do mês no bloco mensal bruto do mesmo cenário.
    checks: List[str] = []
    for scen in SCENARIOS:
        col = raw[scen].get((ano, mes))
        if col is None:
            raise ValueError(f"Cenário '{scen}' sem coluna para {ano}-{mes:02d}.")
        raw_v = num(rows["receita"], col)
        agg_v = receita[scen]["month"]
        if abs(raw_v - agg_v) > 1e-6 * max(1.0, abs(raw_v)):
            checks.append(f"Receita {scen}: tabela agregada ({agg_v:,.1f}) difere do bloco mensal ({raw_v:,.1f}).")

    # Margem = OCF / Receita Líquida, por visão e cenário.
    margem = {
        scen: {visao: (ocf[scen][visao] / receita[scen][visao]) if receita[scen][visao] else 0.0
               for visao in AGG_GROUPS}
        for scen in SCENARIOS
    }

    return OCFResult(receita=receita, ocf=ocf, nsr=nsr, margem=margem, selector_month=selector_month, checks=checks)
