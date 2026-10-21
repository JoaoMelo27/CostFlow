"""Formatação de números no padrão brasileiro (milhar com ponto, decimal com vírgula)."""
from __future__ import annotations

import re


def num(valor: float | None, decimais: int = 1) -> str:
    """1234.5 -> '1.234,5'. Sem valor -> '—'."""
    if valor is None:
        return "—"
    texto = f"{valor:,.{decimais}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(delta: float | None, decimais: int = 1, sinal: bool = True) -> str:
    """Δ em fração -> texto: 0.084 -> '+8,4%'."""
    if delta is None:
        return "—"
    v = delta * 100
    texto = num(abs(v), decimais)
    if not sinal:
        return f"{texto}%"
    return f"{'+' if v > 0 else '-' if v < 0 else ''}{texto}%"


def valor_indicador(valor: float | None, unidade: str, decimais: int) -> str:
    """Valor como aparece no cartão (Margem ganha o '%')."""
    if valor is None:
        return "—"
    if unidade == "%":
        return f"{num(valor, decimais)}%"
    return num(valor, decimais)


def parse_ptbr(texto: str) -> float:
    """Lê um número digitado no padrão brasileiro: '21.500', '21500', '1.234,5', '-0,5'.

    Levanta ValueError se não for um número. Ponto sozinho só vale como milhar quando
    segue o padrão 1.234 / 12.345.678 (grupos de 3 dígitos); caso contrário é decimal.
    """
    t = str(texto).strip().replace(" ", "").replace("R$", "")
    if not t:
        raise ValueError("vazio")
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", t):
        t = t.replace(".", "")
    if not re.fullmatch(r"-?\d+(\.\d+)?", t):
        raise ValueError(f"'{texto}' não é um número")
    return float(t)
