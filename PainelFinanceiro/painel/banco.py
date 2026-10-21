"""
Banco SQLite do Painel Financeiro.

Decisões (e o porquê):

1. Chave primária natural (ano, mes, indicador, cenario, visao) + UPSERT.
   Reprocessar um mês sobrescreve os MESMOS registros daquele mês, nunca cria
   linha duplicada, e os outros meses ficam intactos (histórico preservado).

2. Tabela de auditoria. Se um mês é reprocessado e algum valor muda, o valor
   anterior fica guardado em fato_auditoria. Assim "o histórico nunca se
   perde" vale também para correções: dá para ver o que mudou, quando e quanto.

3. Um período inteiro é gravado numa única transação: ou entram todos os
   indicadores do mês, ou nenhum. Nunca fica um mês pela metade.

4. journal_mode padrão (DELETE), não WAL: em produção o arquivo fica numa pasta
   de rede compartilhada, onde o WAL não é confiável. Uso esperado: UMA pessoa
   roda "Atualizar" por vez; as demais só consultam. O timeout de 30 s reduz
   erros de "database is locked" durante consultas.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

SCHEMA = """
CREATE TABLE IF NOT EXISTS fato_indicador (
    ano            INTEGER NOT NULL,
    mes            INTEGER NOT NULL,
    indicador      TEXT    NOT NULL,
    cenario        TEXT    NOT NULL,   -- budget | rf | real
    visao          TEXT    NOT NULL,   -- month | ytd | fy
    valor          REAL    NOT NULL,
    unidade        TEXT    NOT NULL,
    processado_em  TEXT    NOT NULL,
    PRIMARY KEY (ano, mes, indicador, cenario, visao)
);

CREATE TABLE IF NOT EXISTS fato_auditoria (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ano             INTEGER NOT NULL,
    mes             INTEGER NOT NULL,
    indicador       TEXT    NOT NULL,
    cenario         TEXT    NOT NULL,
    visao           TEXT    NOT NULL,
    valor_anterior  REAL    NOT NULL,
    valor_novo      REAL    NOT NULL,
    alterado_em     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS processamento_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ano             INTEGER NOT NULL,
    mes             INTEGER NOT NULL,
    arquivos        TEXT    NOT NULL,   -- nomes dos arquivos usados (rastreabilidade)
    n_registros     INTEGER NOT NULL,
    n_alterados     INTEGER NOT NULL,   -- quantos valores já existiam e mudaram
    avisos          TEXT,
    processado_em   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS comentario (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ano         INTEGER NOT NULL,
    mes         INTEGER NOT NULL,
    indicador   TEXT    NOT NULL,       -- código do indicador ou 'geral'
    autor       TEXT    NOT NULL,
    texto       TEXT    NOT NULL,
    criado_em   TEXT    NOT NULL
);
"""

# Diferença mínima para considerar que um valor "mudou" num reprocessamento
# (evita registrar ruído de ponto flutuante na auditoria).
EPS = 1e-9

Painel = Dict[str, Dict[str, Dict[str, float]]]   # {indicador: {visao: {cenario: valor}}}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def connect(db_path: str) -> sqlite3.Connection:
    """Abre (e cria, se preciso) o banco. A pasta é criada automaticamente."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Tudo dentro do `with` entra junto ou nada entra."""
    try:
        conn.execute("BEGIN")
        yield
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def _upsert(conn, ano, mes, indicador, cenario, visao, valor, unidade, agora) -> int:
    """Grava um valor. Se já existia e mudou, guarda o anterior na auditoria. Retorna 1 se mudou, senão 0."""
    atual = conn.execute(
        "SELECT valor FROM fato_indicador WHERE ano=? AND mes=? AND indicador=? AND cenario=? AND visao=?",
        (ano, mes, indicador, cenario, visao),
    ).fetchone()
    mudou = 0
    if atual is not None and abs(atual["valor"] - valor) > EPS:
        mudou = 1
        conn.execute(
            "INSERT INTO fato_auditoria (ano, mes, indicador, cenario, visao, valor_anterior, valor_novo, alterado_em)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (ano, mes, indicador, cenario, visao, atual["valor"], valor, agora),
        )
    conn.execute(
        """
        INSERT INTO fato_indicador (ano, mes, indicador, cenario, visao, valor, unidade, processado_em)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(ano, mes, indicador, cenario, visao)
        DO UPDATE SET valor=excluded.valor, unidade=excluded.unidade, processado_em=excluded.processado_em
        """,
        (ano, mes, indicador, cenario, visao, valor, unidade, agora),
    )
    return mudou


def gravar_periodo(
    conn: sqlite3.Connection,
    ano: int,
    mes: int,
    registros: Iterable[Tuple[str, str, str, float, str]],
    arquivos: List[str],
    avisos: Optional[List[str]] = None,
) -> Dict[str, int]:
    """Grava (UPSERT) todos os registros do período numa transação única.

    registros: (indicador, cenario, visao, valor, unidade)
    Retorna {'registros': n, 'alterados': quantos já existiam e mudaram}.
    """
    registros = list(registros)
    agora = _now()
    alterados = 0
    with transaction(conn):
        for indicador, cenario, visao, valor, unidade in registros:
            alterados += _upsert(conn, ano, mes, indicador, cenario, visao, valor, unidade, agora)
        conn.execute(
            "INSERT INTO processamento_log (ano, mes, arquivos, n_registros, n_alterados, avisos, processado_em)"
            " VALUES (?,?,?,?,?,?,?)",
            (ano, mes, " | ".join(arquivos), len(registros), alterados, " || ".join(avisos or []), agora),
        )
    return {"registros": len(registros), "alterados": alterados}


def periodos_disponiveis(conn: sqlite3.Connection) -> List[Tuple[int, int]]:
    rows = conn.execute("SELECT DISTINCT ano, mes FROM fato_indicador ORDER BY ano, mes").fetchall()
    return [(r["ano"], r["mes"]) for r in rows]


def carregar_painel(conn: sqlite3.Connection, ano: int, mes: int) -> Painel:
    """{indicador: {visao: {cenario: valor}}} de um período."""
    out: Painel = {}
    for r in conn.execute(
        "SELECT indicador, cenario, visao, valor FROM fato_indicador WHERE ano=? AND mes=?", (ano, mes)
    ):
        out.setdefault(r["indicador"], {}).setdefault(r["visao"], {})[r["cenario"]] = r["valor"]
    return out


def carregar_todos(conn: sqlite3.Connection) -> Dict[Tuple[int, int], Painel]:
    """Histórico completo: {(ano, mes): {indicador: {visao: {cenario: valor}}}}."""
    out: Dict[Tuple[int, int], Painel] = {}
    for r in conn.execute(
        "SELECT ano, mes, indicador, cenario, visao, valor FROM fato_indicador ORDER BY ano, mes"
    ):
        out.setdefault((r["ano"], r["mes"]), {}).setdefault(r["indicador"], {}).setdefault(r["visao"], {})[
            r["cenario"]
        ] = r["valor"]
    return out


def serie_mensal(conn: sqlite3.Connection, indicador: str, visao: str = "month") -> List[sqlite3.Row]:
    """Série histórica de um indicador (uma linha por mês e cenário)."""
    return conn.execute(
        "SELECT ano, mes, cenario, valor FROM fato_indicador WHERE indicador=? AND visao=? ORDER BY ano, mes",
        (indicador, visao),
    ).fetchall()


def ultimo_log(conn: sqlite3.Connection, ano: int, mes: int) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM processamento_log WHERE ano=? AND mes=? ORDER BY id DESC LIMIT 1", (ano, mes)
    ).fetchone()


def contar_auditoria(conn: sqlite3.Connection, ano: int, mes: int) -> int:
    """Quantos valores daquele mês já foram corrigidos em reprocessamentos."""
    return conn.execute("SELECT COUNT(*) FROM fato_auditoria WHERE ano=? AND mes=?", (ano, mes)).fetchone()[0]


def adicionar_comentario(conn, ano: int, mes: int, indicador: str, autor: str, texto: str) -> None:
    with transaction(conn):
        conn.execute(
            "INSERT INTO comentario (ano, mes, indicador, autor, texto, criado_em) VALUES (?,?,?,?,?,?)",
            (ano, mes, indicador, autor.strip(), texto.strip(), _now()),
        )


def listar_comentarios(conn, ano: int, mes: int) -> List[sqlite3.Row]:
    return conn.execute("SELECT * FROM comentario WHERE ano=? AND mes=? ORDER BY id", (ano, mes)).fetchall()


def resumo_processamentos(conn: sqlite3.Connection) -> List[Dict[str, object]]:
    """Uma linha por mês gravado: última gravação, quantas vezes foi processado,
    quantos valores mudaram na última vez e quais arquivos foram usados."""
    out = []
    for r in conn.execute(
        """
        SELECT l.ano, l.mes, l.processado_em, l.arquivos, l.n_registros, l.n_alterados,
               (SELECT COUNT(*) FROM processamento_log x WHERE x.ano = l.ano AND x.mes = l.mes) AS vezes
        FROM processamento_log l
        WHERE l.id = (SELECT MAX(id) FROM processamento_log y WHERE y.ano = l.ano AND y.mes = l.mes)
        ORDER BY l.ano, l.mes
        """
    ):
        out.append(dict(r))
    return out


def gravar_manual(
    conn: sqlite3.Connection, ano: int, mes: int, indicador: str, unidade: str,
    valores: Dict[str, Dict[str, float]],
) -> int:
    """Grava os valores digitados à mão de UM indicador (ex.: Investimento) num mês já processado.

    valores: {visao: {cenario: valor}}. Usa o mesmo UPSERT/auditoria dos valores
    automáticos, então corrigir um número guarda o anterior. Reprocessar as
    planilhas nunca apaga esses valores, porque o indicador manual não faz parte
    do que o pipeline grava. Retorna quantos valores já existiam e mudaram.
    """
    if (ano, mes) not in periodos_disponiveis(conn):
        raise ValueError("Processe o mês pelas planilhas antes de preencher o indicador manual.")
    agora = _now()
    alterados = 0
    with transaction(conn):
        for visao, por_cen in valores.items():
            for cenario, valor in por_cen.items():
                alterados += _upsert(conn, ano, mes, indicador, cenario, visao, float(valor), unidade, agora)
    return alterados


def ultima_gravacao(conn: sqlite3.Connection, ano: int, mes: int, indicador: str) -> Optional[str]:
    """Quando o indicador foi gravado pela última vez naquele mês (None = nunca)."""
    r = conn.execute(
        "SELECT MAX(processado_em) AS t FROM fato_indicador WHERE ano=? AND mes=? AND indicador=?",
        (ano, mes, indicador),
    ).fetchone()
    return r["t"] if r and r["t"] else None
