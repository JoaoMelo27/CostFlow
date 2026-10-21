"""
Painel Financeiro - servidor web (Flask).

Como rodar:
    python app.py
e abrir http://localhost:8000 (no Codespaces a porta abre sozinha).

O servidor faz duas coisas:
  1. entrega a página (templates/index.html + static/), feita em HTML, CSS e JavaScript puros;
  2. responde a API em /api/..., que devolve em JSON o que cada aba mostra.
Toda conta e toda regra ficam no pacote `painel` (Python). O JavaScript só desenha.

Variáveis de ambiente (opcionais):
    PAINEL_DB               caminho do arquivo SQLite (padrão: ./dados/painel.db)
    PAINEL_PASTA            pasta onde ficam os 3 arquivos do mês (padrão: ./entrada)
    PAINEL_SOMENTE_LEITURA  "1" esconde a aba Atualizar (para quem só consulta)
    PORTA                   porta do servidor (padrão: 8000)
"""
from __future__ import annotations

import os
import secrets
import threading
import traceback
import webbrowser

from flask import Flask, Response, abort, g, jsonify, render_template, request

from painel import banco, exportar_csv, exportar_pdf, pipeline, telas
from painel.config import POR_CODIGO, VISOES

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("PAINEL_DB", os.path.join(BASE, "dados", "painel.db"))
PASTA_PADRAO = os.environ.get("PAINEL_PASTA", os.path.join(BASE, "entrada"))
SOMENTE_LEITURA = os.environ.get("PAINEL_SOMENTE_LEITURA", "0") == "1"

app = Flask(__name__)
app.json.ensure_ascii = False      # acentos legíveis no JSON
app.json.sort_keys = False         # mantém a ordem das colunas das tabelas

# Prévias calculadas pelo botão Atualizar e ainda não confirmadas.
# Ficam na memória do servidor até a pessoa clicar em "Confirmar" (ou serem descartadas).
_previas: dict = {}
_trava = threading.Lock()


# --------------------------------------------------------------------------- utilidades
def conexao():
    """Uma conexão SQLite por requisição (fechada automaticamente no fim)."""
    if "conn" not in g:
        g.conn = banco.connect(DB_PATH)
    return g.conn


@app.teardown_appcontext
def _fechar_conexao(_erro):
    conn = g.pop("conn", None)
    if conn is not None:
        conn.close()


def _periodo_da_url():
    """Lê ?ano=&mes= e confere se o período existe no histórico."""
    try:
        ano, mes = int(request.args["ano"]), int(request.args["mes"])
    except (KeyError, ValueError):
        abort(400, "Informe ano e mês.")
    if (ano, mes) not in banco.periodos_disponiveis(conexao()):
        abort(404, "Período não encontrado no histórico.")
    return ano, mes


def _bloquear_se_somente_leitura():
    if SOMENTE_LEITURA:
        abort(403, "Este computador está em modo somente consulta.")


def _baixar(conteudo: bytes, nome: str, tipo: str) -> Response:
    return Response(conteudo, mimetype=tipo, headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
def _erro_json(e):
    return jsonify({"erro": e.description}), e.code


# --------------------------------------------------------------------------- página
@app.get("/")
def index():
    return render_template("index.html")


# --------------------------------------------------------------------------- consulta
@app.get("/api/estado")
def api_estado():
    return jsonify({**telas.estado(conexao()), "somente_leitura": SOMENTE_LEITURA, "pasta_padrao": PASTA_PADRAO})


@app.get("/api/painel")
def api_painel():
    ano, mes = _periodo_da_url()
    return jsonify(telas.tela_painel(banco.carregar_painel(conexao(), ano, mes), ano, mes))


@app.get("/api/insights")
def api_insights():
    ano, mes = _periodo_da_url()
    visao = request.args.get("visao", "month")
    if visao not in VISOES:
        abort(400, "Visão inválida.")
    return jsonify(telas.tela_insights(conexao(), ano, mes, visao))


@app.get("/api/historico")
def api_historico():
    anos = [int(a) for a in request.args.get("anos", "").split(",") if a.strip().isdigit()]
    cod = request.args.get("indicador", "todos")
    visao = request.args.get("visao", "month")
    if cod != "todos" and cod not in POR_CODIGO or visao not in VISOES:
        abort(400, "Filtro inválido.")
    recentes = request.args.get("ordem") == "recentes"
    return jsonify(telas.tela_historico(conexao(), anos, cod, visao, recentes))


@app.get("/api/sobre")
def api_sobre():
    ano = request.args.get("ano", type=int)
    mes = request.args.get("mes", type=int)
    return jsonify(telas.tela_sobre(conexao(), ano, mes, DB_PATH, SOMENTE_LEITURA))


@app.post("/api/comentarios")
def api_comentar():
    dados = request.get_json(force=True)
    ano, mes = int(dados["ano"]), int(dados["mes"])
    autor, texto = (dados.get("autor") or "").strip(), (dados.get("texto") or "").strip()
    alvo = dados.get("indicador", "geral")
    if not autor or not texto:
        return jsonify({"erro": "Preencha autor e comentário."}), 400
    if alvo != "geral" and alvo not in POR_CODIGO:
        abort(400, "Indicador inválido.")
    banco.adicionar_comentario(conexao(), ano, mes, alvo, autor, texto)
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- atualização mensal
@app.post("/api/atualizar")
def api_atualizar():
    """Lê os arquivos da pasta, calcula e valida. NÃO grava: devolve uma prévia para conferência."""
    _bloquear_se_somente_leitura()
    dados = request.get_json(force=True)
    pasta = (dados.get("pasta") or PASTA_PADRAO).strip()
    nada_gravado = "Nada foi gravado. O histórico continua como estava."
    try:
        arquivos = pipeline.localizar_arquivos(pasta)
        if dados.get("manual"):
            ano, mes = int(dados["ano"]), int(dados["mes"])
        else:
            ano, mes = pipeline.detectar_periodo(arquivos)
        resultado = pipeline.processar(arquivos, ano, mes)
    except pipeline.ArquivoProtegidoError as e:
        return jsonify({"erro": f"Arquivo protegido: {e}"}), 422
    except pipeline.ArquivoComProblemaError as e:
        return jsonify({"erro": f"Problema na leitura de um arquivo. {e}", "nota": nada_gravado}), 422
    except FileNotFoundError as e:
        return jsonify({"erro": str(e), "nota": nada_gravado}), 422
    except ValueError as e:
        return jsonify({"erro": str(e)}), 422
    except Exception as e:      # erro inesperado: mostra, não esconde
        return jsonify({"erro": f"Erro inesperado: {e}", "detalhe": traceback.format_exc()}), 500

    token = secrets.token_hex(8)
    with _trava:
        _previas.clear()                 # só a prévia mais recente vale (como na tela original)
        _previas[token] = resultado
    ja_existe = (ano, mes) in banco.periodos_disponiveis(conexao())
    return jsonify({"token": token, **telas.tela_previa(resultado, ja_existe)})


@app.post("/api/confirmar")
def api_confirmar():
    """Grava no histórico a prévia que a pessoa conferiu."""
    _bloquear_se_somente_leitura()
    token = request.get_json(force=True).get("token")
    with _trava:
        resultado = _previas.pop(token, None)
    if resultado is None:
        return jsonify({"erro": "A prévia expirou. Clique em Atualizar de novo."}), 409
    try:
        out = pipeline.salvar(conexao(), resultado)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 422
    msg = (f"{telas.periodo_txt(resultado.ano, resultado.mes)} gravado: {out['registros']} valores "
           f"({out['alterados']} já existiam e mudaram). Veja na aba Painel.")
    return jsonify({"mensagem": msg, "ano": resultado.ano, "mes": resultado.mes})


@app.get("/api/investimento")
def api_investimento():
    ano, mes = _periodo_da_url()
    return jsonify(telas.tela_investimento(conexao(), ano, mes))


@app.post("/api/investimento")
def api_salvar_investimento():
    """Grava os 9 valores digitados do Investimento (Capex/Opex/Oro)."""
    _bloquear_se_somente_leitura()
    dados = request.get_json(force=True)
    ano, mes = int(dados["ano"]), int(dados["mes"])
    lidos, problemas, avisos = telas.ler_investimento(dados.get("valores", {}))
    if problemas:
        return jsonify({"erro": "Preencha todos os 9 campos com números. Verifique: " + "; ".join(problemas) + "."}), 400
    ind = POR_CODIGO["investimento_kbrl"]
    try:
        mudou = banco.gravar_manual(conexao(), ano, mes, ind.codigo, ind.unidade, lidos)
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    msg = (f"Investimento de {telas.periodo_txt(ano, mes)} salvo ({mudou} valor(es) corrigido(s) "
           "foram registrados na auditoria).") + (" Atenção: " + " ".join(avisos) if avisos else "")
    return jsonify({"mensagem": msg})


# --------------------------------------------------------------------------- exportações
@app.get("/exportar/painel.pdf")
def baixar_pdf():
    ano, mes = _periodo_da_url()
    pdf = exportar_pdf.painel_pdf(ano, mes, banco.carregar_painel(conexao(), ano, mes))
    return _baixar(pdf, f"painel_financeiro_{ano}_{mes:02d}.pdf", "application/pdf")


@app.get("/exportar/painel.csv")
def baixar_csv_painel():
    ano, mes = _periodo_da_url()
    csv = exportar_csv.csv_painel(ano, mes, banco.carregar_painel(conexao(), ano, mes))
    return _baixar(csv, f"painel_financeiro_{ano}_{mes:02d}.csv", "text/csv")


@app.get("/exportar/historico.csv")
def baixar_csv_historico():
    anos = [int(a) for a in request.args.get("anos", "").split(",") if a.strip().isdigit()]
    cod = request.args.get("indicador", "todos")
    visao = request.args.get("visao", "month")
    cods = [c for c in POR_CODIGO] if cod == "todos" else [cod]
    csv = exportar_csv.csv_historico(banco.carregar_todos(conexao()), anos, cods, [visao])
    return _baixar(csv, "historico_painel_financeiro.csv", "text/csv")


# --------------------------------------------------------------------------- iniciar
if __name__ == "__main__":
    porta = int(os.environ.get("PORTA", "8000"))
    endereco = f"http://localhost:{porta}"
    print(f"\n  Painel Financeiro rodando em {endereco}\n  (Ctrl+C para encerrar)\n")
    # No computador da pessoa, abre o navegador sozinho; no Codespaces quem abre é o próprio VS Code.
    if not os.environ.get("CODESPACES") and os.environ.get("PAINEL_SEM_NAVEGADOR") != "1":
        threading.Timer(1.0, lambda: webbrowser.open(endereco)).start()
    app.run(host="0.0.0.0", port=porta, debug=False)
