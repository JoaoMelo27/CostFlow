"""
Exportação CSV do Painel Financeiro, pensada para abrir direto no Excel em português do Brasil.

Padrão adotado (e o porquê):
  - separador ';'            -> o Excel pt-BR usa ';' como separador de lista; com ',' tudo cairia numa coluna só;
  - decimal ','              -> números chegam ao Excel como número, não como texto;
  - sem separador de milhar  -> evita que '1.234' vire texto/data;
  - UTF-8 com BOM            -> o Excel reconhece a codificação e preserva acentos (Mês, Variação...);
  - fim de linha CRLF        -> padrão do Windows;
  - valores arredondados nas casas que o painel exibe (nada de 69,49999999);
  - Variação (%) como número em pontos percentuais (8,4 = +8,4%), sem o sinal '%'.

Cada linha = um período × um indicador × uma visão. As mesmas colunas servem para o painel de um mês
e para o histórico filtrado, então os dois arquivos se empilham sem ajuste.
"""
from __future__ import annotations

import csv
import io
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .config import INDICADORES, VISAO_LABEL, VISOES, delta_indicador

CABECALHO = [
    "Ano", "Mês", "Indicador", "Unidade", "Visão",
    "Budget", "RF", "Real", "Variação comparada com", "Variação (%)",
]

Painel = Dict[str, Dict[str, Dict[str, float]]]


def _num(valor: Optional[float], decimais: int) -> str:
    """Número no formato do Excel pt-BR, sem milhar. Vazio quando não há dado."""
    if valor is None:
        return ""
    texto = f"{round(valor, decimais):.{decimais}f}"
    if float(texto) == 0:          # evita '-0,0'
        texto = f"{0:.{decimais}f}"
    return texto.replace(".", ",")


def linhas_periodo(
    ano: int,
    mes: int,
    painel: Painel,
    indicadores: Optional[Iterable[str]] = None,
    visoes: Optional[Iterable[str]] = None,
) -> List[List[str]]:
    """Linhas (já como texto) de um período, na ordem dos indicadores do painel."""
    cods = set(indicadores) if indicadores is not None else None
    vis = [v for v in VISOES if visoes is None or v in set(visoes)]
    linhas: List[List[str]] = []
    for ind in INDICADORES:
        if cods is not None and ind.codigo not in cods:
            continue
        for visao in vis:
            d = painel.get(ind.codigo, {}).get(visao)
            if not d:
                continue
            delta = delta_indicador(ind, d.get("real"), d.get(ind.delta_ref))
            linhas.append([
                str(ano), str(mes), ind.nome, ind.unidade, VISAO_LABEL[visao],
                _num(d.get("budget"), ind.decimais), _num(d.get("rf"), ind.decimais), _num(d.get("real"), ind.decimais),
                "Budget" if ind.delta_ref == "budget" else "RF",
                _num(None if delta is None else delta * 100, 1),
            ])
    return linhas


def montar_csv(linhas: Sequence[Sequence[str]]) -> bytes:
    """Cabeçalho + linhas -> bytes UTF-8 com BOM, prontos para download."""
    buf = io.StringIO(newline="")
    w = csv.writer(buf, delimiter=";", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    w.writerow(CABECALHO)
    w.writerows(linhas)
    return buf.getvalue().encode("utf-8-sig")


def csv_painel(ano: int, mes: int, painel: Painel) -> bytes:
    """CSV do painel de UM período (o que está selecionado na tela)."""
    return montar_csv(linhas_periodo(ano, mes, painel))


def csv_historico(
    historico: Dict[Tuple[int, int], Painel],
    anos: Optional[Iterable[int]] = None,
    indicadores: Optional[Iterable[str]] = None,
    visoes: Optional[Iterable[str]] = None,
) -> bytes:
    """CSV do histórico respeitando os filtros da tela (anos, indicadores e visões), em ordem cronológica."""
    anos_set = set(anos) if anos is not None else None
    linhas: List[List[str]] = []
    for (ano, mes) in sorted(historico):
        if anos_set is not None and ano not in anos_set:
            continue
        linhas.extend(linhas_periodo(ano, mes, historico[(ano, mes)], indicadores, visoes))
    return montar_csv(linhas)
