"""
Atualização mensal do Painel Financeiro.

O fluxo espelha a rotina pedida ("colocar na pasta -> Atualizar -> validar"):

    localizar_arquivos(pasta) -> detectar_periodo(...) -> processar(...)   calcula e VALIDA, sem gravar
    salvar(...)                                                            só grava depois de o usuário confirmar

Separar "processar" de "salvar" é o passo de validação: nada entra no
histórico sem alguém ter visto o resultado e os avisos.
"""
from __future__ import annotations

import os
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .config import CENARIOS, POR_CODIGO, VISOES
from .leitores.cash_cost import extract_cash_cost
from .leitores.ga import extract_ga_cash_cost_rt
from .leitores.ocf import _find_header_row, extract_ocf
from .leitores.planilha import excel_serial_to_date, is_plausible_date_serial, load_sheet

EXTENSOES = (".xlsb", ".xlsx")


class ArquivoProtegidoError(Exception):
    """Arquivo com rótulo de sensibilidade/IRM (Microsoft Purview): não pode ser lido fora do Office."""


class ArquivoComProblemaError(ValueError):
    """Erro de leitura ligado a UM arquivo; a mensagem sempre diz qual."""


def _ler(rotulo: str, caminho: str, fn, *args):
    """Roda um leitor e, se falhar, devolve um erro que diz o arquivo e o que deu errado."""
    nome = os.path.basename(caminho)
    try:
        return fn(caminho, *args)
    except ArquivoComProblemaError:
        raise
    except PermissionError:
        raise ArquivoComProblemaError(
            f"Arquivo '{nome}' ({rotulo}): não consegui abrir. Feche-o no Excel e tente de novo."
        ) from None
    except FileNotFoundError:
        raise ArquivoComProblemaError(f"Arquivo '{nome}' ({rotulo}): o arquivo sumiu da pasta durante a leitura.") from None
    except zipfile.BadZipFile:
        raise ArquivoComProblemaError(
            f"Arquivo '{nome}' ({rotulo}): o arquivo está corrompido ou não é um .xlsb/.xlsx válido."
        ) from None
    except KeyError as e:
        raise ArquivoComProblemaError(f"Arquivo '{nome}' ({rotulo}): aba não encontrada — {e.args[0] if e.args else e}.") from None
    except Exception as e:
        raise ArquivoComProblemaError(f"Arquivo '{nome}' ({rotulo}): {e}") from None


@dataclass
class Arquivos:
    custo_total: str
    custo_opex: str
    ocf: str

    def nomes(self) -> List[str]:
        return [os.path.basename(p) for p in (self.custo_total, self.custo_opex, self.ocf)]


@dataclass
class Validacao:
    nivel: str      # 'ok' | 'aviso' | 'erro'
    mensagem: str


@dataclass
class Resultado:
    ano: int
    mes: int
    arquivos: Arquivos
    valores: Dict[str, Dict[str, Dict[str, float]]]   # {indicador: {visao: {cenario: valor}}}
    validacoes: List[Validacao] = field(default_factory=list)

    @property
    def tem_erro(self) -> bool:
        return any(v.nivel == "erro" for v in self.validacoes)

    def registros(self) -> List[Tuple[str, str, str, float, str]]:
        """Linhas prontas para o banco: (indicador, cenario, visao, valor, unidade)."""
        out = []
        for cod, por_visao in self.valores.items():
            for visao, por_cen in por_visao.items():
                for cen, val in por_cen.items():
                    out.append((cod, cen, visao, float(val), POR_CODIGO[cod].unidade))
        return out


# --------------------------------------------------------------------------- localizar os arquivos
def _norm(nome: str) -> str:
    """Nome sem acento, minúsculo e com espaços normalizados (para comparar nomes de arquivo)."""
    s = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[\s_\-]+", " ", s).lower()


def _protegido(path: str) -> bool:
    """.xlsx/.xlsb de verdade são ZIP ('PK'). Se começa com a assinatura OLE2,
    é um .xls antigo ou um arquivo protegido por IRM salvo com a extensão errada."""
    with open(path, "rb") as f:
        return f.read(8) == bytes.fromhex("D0CF11E0A1B11AE1")


def localizar_arquivos(pasta: str) -> Arquivos:
    """Acha os 3 arquivos do mês pelo nome. Se houver mais de um candidato, usa o mais recente."""
    if not os.path.isdir(pasta):
        raise FileNotFoundError(f"Pasta não encontrada: {pasta}")
    candidatos = [
        os.path.join(pasta, f) for f in os.listdir(pasta)
        if f.lower().endswith(EXTENSOES) and not f.startswith("~$")
    ]

    def mais_recente(lista: List[str]) -> Optional[str]:
        return max(lista, key=os.path.getmtime) if lista else None

    total = mais_recente([p for p in candidatos if "custo total" in _norm(os.path.basename(p))])
    opex = mais_recente([
        p for p in candidatos
        if "gestao de custos opex" in _norm(os.path.basename(p)) and "custo total" not in _norm(os.path.basename(p))
    ])
    ocf_todos = [p for p in candidatos if _norm(os.path.basename(p)).startswith("ocf")]
    ocf_ok = [p for p in ocf_todos if not _protegido(p)]      # prefere um OCF legível (o original vem protegido)
    ocf = mais_recente(ocf_ok)

    faltando = []
    if not total:
        faltando.append("CUSTO TOTAL - Gestão de Custos OPEX ... (.xlsb)")
    if not opex:
        faltando.append("Gestão de Custos OPEX ... (.xlsb)")
    if not ocf:
        if ocf_todos:
            raise ArquivoProtegidoError(
                "O arquivo OCF da pasta está protegido (rótulo de sensibilidade/IRM) e não pode ser lido "
                "fora do Office. Abra-o no Excel e use 'Salvar como' .xlsb (ou uma cópia sem o rótulo), "
                "e coloque essa cópia na pasta."
            )
        faltando.append("OCF Report ... (.xlsb)")
    if faltando:
        presentes = sorted(os.path.basename(c) for c in candidatos)
        achados = ("Arquivos .xlsb/.xlsx que estão na pasta: " + "; ".join(presentes)) if presentes \
            else "A pasta não tem nenhum .xlsb/.xlsx."
        raise FileNotFoundError(
            f"Arquivo(s) não encontrado(s) na pasta '{pasta}': " + "; ".join(faltando) + ". " + achados
        )
    return Arquivos(custo_total=total, custo_opex=opex, ocf=ocf)


def detectar_periodo(arquivos: Arquivos) -> Tuple[int, int]:
    """O período de fechamento é o mês gravado na célula-seletor do arquivo OCF."""
    def _ler_periodo(caminho: str) -> Tuple[int, int]:
        grid = load_sheet(caminho, "BD", max_rows=12)
        hdr, col = _find_header_row(grid)
        serial = grid.cell(hdr + 1, col)
        if not is_plausible_date_serial(serial):
            raise ValueError("não consegui ler o mês de fechamento (célula-seletor da aba BD).")
        d = excel_serial_to_date(serial)
        return d.year, d.month

    return _ler("OCF", arquivos.ocf, _ler_periodo)


# --------------------------------------------------------------------------- calcular e validar
def _v(d: Dict[str, Dict[str, float]], escala: float = 1.0) -> Dict[str, Dict[str, float]]:
    """Troca a ordem das chaves e aplica a escala: {cenario: {visao: v}} -> {visao: {cenario: v * escala}}."""
    return {visao: {cen: d[cen][visao] * escala for cen in CENARIOS} for visao in VISOES}


def processar(arquivos: Arquivos, ano: int, mes: int) -> Resultado:
    """Lê os 3 arquivos, calcula os 9 indicadores automáticos e roda as validações. Não grava nada."""
    val: List[Validacao] = []

    cc_total = _ler("CUSTO TOTAL", arquivos.custo_total, extract_cash_cost, ano, mes)
    cc_opex = _ler("Gestão de Custos OPEX", arquivos.custo_opex, extract_cash_cost, ano, mes)
    ga = _ler("Gestão de Custos OPEX · aba G&A", arquivos.custo_opex, extract_ga_cash_cost_rt, ano, mes)
    ocf = _ler("OCF", arquivos.ocf, extract_ocf, ano, mes)

    ga_dict = {"budget": ga.budget, "rf": ga.rf, "real": ga.real}
    valores = {
        "custo_total_mbrl": _v(cc_total.custo, 1e-6),          # R$ -> milhões de R$
        "custo_opex_mbrl": _v(cc_opex.custo, 1e-6),
        "receita_liquida_kusd": _v(ocf.receita),
        "ocf_kusd": _v(ocf.ocf),
        "cash_cost_total_usdt": _v(cc_total.cash_cost_usdt),
        "cash_cost_opex_usdt": _v(cc_opex.cash_cost_usdt),
        "cash_cost_ga_rt": _v(ga_dict),
        "margem_pct": _v(ocf.margem, 100.0),                    # fração -> %
        "nsr": _v(ocf.nsr),
    }

    # ---------------- validações determinísticas ----------------
    for c in ocf.checks:
        val.append(Validacao("aviso", c))

    # 1) todo indicador automático tem os 9 valores (3 visões x 3 cenários); o Investimento é manual
    for cod in valores:
        n = sum(len(valores[cod][v]) for v in VISOES)
        if n != 9:
            val.append(Validacao("erro", f"{POR_CODIGO[cod].nome}: esperava 9 valores, veio {n}."))

    # 2) Real e Budget do mês não podem ser zero (indicaria coluna errada ou mês sem dado)
    for cod in valores:
        for cen in ("budget", "real"):
            if valores[cod]["month"][cen] == 0:
                val.append(Validacao("aviso", f"{POR_CODIGO[cod].nome}: valor {cen} do mês está zerado."))

    # 3) Custo Total >= Custo OPEX (o Total contém o OPEX)
    for visao in VISOES:
        for cen in CENARIOS:
            t = valores["custo_total_mbrl"][visao][cen]
            o = valores["custo_opex_mbrl"][visao][cen]
            if t < o:
                val.append(Validacao("aviso", f"Custo Total menor que Custo OPEX em {visao}/{cen} ({t:.1f} < {o:.1f})."))

    # 4) Month <= YTD <= FY nos custos (custos são positivos e acumulam)
    for cod in ("custo_total_mbrl", "custo_opex_mbrl"):
        for cen in CENARIOS:
            m, y, f = (valores[cod][v][cen] for v in VISOES)
            if not (m <= y + 1e-9 and y <= f + 1e-9):
                val.append(Validacao("aviso", f"{POR_CODIGO[cod].nome}/{cen}: sequência Month<=YTD<=FY violada."))

    # 5) Margem coerente com OCF / Receita
    for visao in VISOES:
        for cen in CENARIOS:
            r = valores["receita_liquida_kusd"][visao][cen]
            o = valores["ocf_kusd"][visao][cen]
            m = valores["margem_pct"][visao][cen]
            if r and abs(m - 100 * o / r) > 1e-6:
                val.append(Validacao("erro", f"Margem inconsistente em {visao}/{cen}."))

    # 6) Mês do OCF confere (o leitor do OCF já recusa se não conferir)
    val.append(Validacao("ok", f"Mês do arquivo OCF confere com o período pedido ({mes:02d}/{ano})."))

    # 7) Lembrete: o Investimento não vem dos arquivos
    val.append(Validacao("aviso", "Investimento (Capex/Opex/Oro) não vem dos arquivos: preencha-o na seção própria "
                                  "da aba Atualizar depois de confirmar."))

    # 8) Conferência humana
    val.append(Validacao("ok", "Cálculos concluídos. A conferência final dos números é dos responsáveis."))

    return Resultado(ano=ano, mes=mes, arquivos=arquivos, valores=valores, validacoes=val)


def salvar(conn, resultado: Resultado) -> Dict[str, int]:
    """Grava o resultado no histórico (só se não houver erro de validação)."""
    from .banco import gravar_periodo
    if resultado.tem_erro:
        raise ValueError("Há erros de validação; corrija antes de salvar.")
    avisos = [v.mensagem for v in resultado.validacoes if v.nivel == "aviso"]
    return gravar_periodo(conn, resultado.ano, resultado.mes, resultado.registros(),
                          arquivos=resultado.arquivos.nomes(), avisos=avisos)
