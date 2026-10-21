"""
Prepara o painel com DADOS FICTÍCIOS, para rodar no Codespaces ou em qualquer máquina.

O que ele faz:
  1. Gera as planilhas fictícias de janeiro até setembro/2026 em exemplos/planilhas/AAAA-MM/
     (mesmo layout das planilhas reais).
  2. Processa janeiro a agosto pelo MESMO caminho do botão Atualizar (pipeline + banco) e
     preenche o Investimento desses meses, para o painel já abrir com histórico.
  3. Deixa as planilhas de setembro na pasta `entrada`, prontas para o grupo
     clicar em Atualizar ao vivo durante a apresentação.

Uso (a partir da pasta PainelFinanceiro):
    python exemplos/gerar_exemplos.py            # só carrega o histórico se o banco estiver vazio
    python exemplos/gerar_exemplos.py --forcar   # recarrega mesmo com dados (não duplica nada)
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)     # para importar o pacote `painel`
sys.path.insert(0, AQUI)     # para importar o modelo fictício

import modelo_ficticio as mf                                  # noqa: E402
from planilhas_ficticias import gerar_planilhas, nomes_arquivos  # noqa: E402

from painel import banco, pipeline                            # noqa: E402
from painel.config import POR_CODIGO                          # noqa: E402

PASTA_PLANILHAS = os.path.join(AQUI, "planilhas")
PASTA_ENTRADA = os.environ.get("PAINEL_PASTA", os.path.join(RAIZ, "entrada"))
DB_PATH = os.environ.get("PAINEL_DB", os.path.join(RAIZ, "dados", "painel.db"))


def _limpar_exemplos_da_entrada() -> None:
    """Remove da pasta `entrada` só as planilhas de exemplo antigas (nunca outros arquivos)."""
    if not os.path.isdir(PASTA_ENTRADA):
        return
    for nome in os.listdir(PASTA_ENTRADA):
        if "Exemplo" in nome and nome.lower().endswith(".xlsx"):
            os.remove(os.path.join(PASTA_ENTRADA, nome))


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera planilhas fictícias e carrega o histórico de exemplo.")
    parser.add_argument("--historico-ate", type=int, default=8, help="último mês carregado no histórico (padrão: 8)")
    parser.add_argument("--forcar", action="store_true", help="carrega o histórico mesmo se o banco já tiver dados")
    args = parser.parse_args()
    ultimo = args.historico_ate
    proximo = ultimo + 1 if ultimo < 12 else None

    base = mf.gerar_base()
    print("1) Gerando planilhas fictícias...")
    for mes in mf.lista_meses(proximo or ultimo):
        gerar_planilhas(os.path.join(PASTA_PLANILHAS, f"{mf.ANO}-{mes:02d}"), mes, base)
    print(f"   {proximo or ultimo} fechamentos em {os.path.relpath(PASTA_PLANILHAS, RAIZ)}/")

    conn = banco.connect(DB_PATH)
    if banco.periodos_disponiveis(conn) and not args.forcar:
        print("2) O banco já tem histórico: nada foi alterado (use --forcar para recarregar).")
    else:
        print("2) Carregando o histórico pelo mesmo caminho do botão Atualizar...")
        inv = POR_CODIGO["investimento_kbrl"]
        for mes in mf.lista_meses(ultimo):
            pasta = os.path.join(PASTA_PLANILHAS, f"{mf.ANO}-{mes:02d}")
            arquivos = pipeline.localizar_arquivos(pasta)
            ano_lido, mes_lido = pipeline.detectar_periodo(arquivos)
            resultado = pipeline.processar(arquivos, ano_lido, mes_lido)
            pipeline.salvar(conn, resultado)
            banco.gravar_manual(conn, ano_lido, mes_lido, inv.codigo, inv.unidade,
                                mf.investimento_do_fechamento(mes_lido, base))
            print(f"   {mes_lido:02d}/{ano_lido} gravado")
    conn.close()

    if proximo:
        print(f"3) Deixando as planilhas de {proximo:02d}/{mf.ANO} na pasta entrada (para clicar em Atualizar)...")
        os.makedirs(PASTA_ENTRADA, exist_ok=True)
        _limpar_exemplos_da_entrada()
        origem = os.path.join(PASTA_PLANILHAS, f"{mf.ANO}-{proximo:02d}")
        for nome in nomes_arquivos(proximo).values():
            shutil.copy2(os.path.join(origem, nome), os.path.join(PASTA_ENTRADA, nome))
    print("Pronto. Rode: python app.py")


if __name__ == "__main__":
    main()
