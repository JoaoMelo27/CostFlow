"""
Regras de negócio do Painel Financeiro (tudo em Python, nada na interface).

Módulos:
    config         indicadores, regras de Δ% e de cor (faróis) num lugar só
    formatacao     números no padrão brasileiro
    leitores/      um leitor por planilha-fonte (cash cost, G&A, OCF)
    pipeline       localiza arquivos, detecta o período, calcula e valida
    banco          SQLite: histórico sem duplicar, auditoria, comentários
    insights       textos automáticos a partir dos números (sem inventar causas)
    telas          monta o que cada aba da interface mostra (cartões, tabelas, gráficos)
    exportar_csv   CSV que abre direto no Excel em português
    exportar_pdf   painel em PDF (A4 paisagem) para impressão
"""
