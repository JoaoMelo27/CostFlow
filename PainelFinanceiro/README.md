# Painel Financeiro

Automação do fechamento mensal de um Painel Financeiro de mineração. O sistema lê três planilhas Excel,
calcula 10 indicadores (Month / YTD / FY × Budget / RF / Real), guarda o histórico mês a mês e mostra o painel
com filtro de ano e mês, insights automáticos, histórico e exportação em PDF e CSV.

A rotina manual "abrir Excel → localizar → consolidar → calcular → montar painel" vira
**"colocar os arquivos na pasta → clicar em Atualizar → conferir → confirmar"**.

> **Todos os números deste repositório são fictícios.** As planilhas de exemplo são geradas por
> `exemplos/gerar_exemplos.py` com o mesmo layout das planilhas reais, mas com valores inventados.

## Ferramentas

| Parte | Ferramenta |
|---|---|
| Regras de negócio, leitura das planilhas, cálculos | Python |
| Servidor web e API | Flask |
| Banco de dados | SQLite (SQL puro, sem ORM) |
| Interface | HTML, CSS e JavaScript puros (sem framework) |
| Bibliotecas de apoio | pyxlsb e openpyxl (ler Excel), reportlab (gerar o PDF) |

## Rodar no GitHub Codespaces (recomendado para o grupo)

1. No GitHub, abra o repositório **CostFlow** → botão verde **Code** → aba **Codespaces** → **Create codespace on main**.
2. Espere a criação terminar (a primeira vez leva uns 2 minutos). Ela já instala tudo e gera os dados fictícios.
3. O painel sobe sozinho e abre numa aba do navegador. Se não abrir, vá na aba **Ports** do VS Code e clique no
   globo da porta **8000**.

Se precisar subir o painel na mão: abra um terminal e rode

```bash
cd PainelFinanceiro
python app.py
```

## Rodar no próprio computador

Precisa do Python 3.10 ou mais novo.

```bash
cd PainelFinanceiro
python -m venv .venv
# Mac/Linux:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

pip install -r requirements.txt
python exemplos/gerar_exemplos.py   # só na primeira vez: cria os dados fictícios
python app.py                        # abre http://localhost:8000
```

No Mac, use `python3` no lugar de `python` se o comando `python` não existir.

## Roteiro para a apresentação

O gerador deixa **janeiro a agosto/2026** no histórico e as planilhas de **setembro/2026** na pasta `entrada`.
Assim dá para mostrar o fechamento acontecendo ao vivo:

1. **Painel**: os 10 cartões de agosto, com Δ% e os faróis Meta 500 / 300 / 100 / 0 nos Cash Costs.
2. **Atualizar** → botão **Atualizar**: o sistema acha os 3 arquivos, detecta setembro e mostra validações e prévia.
   Nada é gravado ainda.
3. **Confirmar e salvar no histórico**: setembro entra no histórico e o filtro do topo muda para ele.
4. Na mesma aba, preencher o **Investimento** (os 3 arquivos não trazem esse dado; ele é digitado à mão).
5. **Overview / Insights**: textos automáticos, gráficos e quadro de variações. **Histórico**: tabela, gráfico e CSV.
6. Clicar em **Atualizar** de novo com os mesmos arquivos mostra que reprocessar **não duplica** o mês.

Para voltar ao estado inicial: apague `dados/painel.db` e rode `python exemplos/gerar_exemplos.py` de novo.

## Como o sistema funciona

```
entrada/ (3 planilhas)
   │  painel/leitores/      um leitor por aba (cash_cost, ga, ocf), acha tudo por rótulo e data, nunca por posição fixa
   ▼
painel/pipeline.py          localiza os arquivos, detecta o mês, calcula e VALIDA (sem gravar)
   │  (pessoa confere e confirma)
   ▼
painel/banco.py             SQLite: grava o mês inteiro numa transação, sem duplicar, com auditoria
   │
   ▼
painel/telas.py             monta o conteúdo de cada aba (Δ%, cores e formatação já prontos)
   │
app.py (Flask, /api/...)  ──►  templates/index.html + static/js/app.js + static/js/graficos.js
```

Toda regra fica em Python. O JavaScript só desenha o que recebe, para que a tela, o PDF, o CSV e os insights
mostrem sempre o mesmo número.

### Estrutura de pastas

```
PainelFinanceiro/
├── app.py                 servidor Flask: página + API JSON + downloads
├── requirements.txt
├── painel/                regras de negócio (Python)
│   ├── config.py          indicadores, regras de Δ% e de cor, faróis (num lugar só)
│   ├── formatacao.py      números no padrão brasileiro
│   ├── leitores/          planilha.py (comum), cash_cost.py, ga.py, ocf.py
│   ├── pipeline.py        localizar → detectar período → processar → salvar
│   ├── banco.py           SQLite: UPSERT, auditoria, comentários, investimento manual
│   ├── insights.py        textos automáticos, sem inventar causa
│   ├── telas.py           o que cada aba mostra
│   ├── exportar_csv.py    CSV que abre direto no Excel em português
│   ├── exportar_pdf.py    painel em A4 paisagem
│   └── fontes/            fonte usada no PDF
├── templates/index.html   página única com as 5 abas
├── static/                css/painel.css, js/app.js, js/graficos.js, img/
├── exemplos/              gerador de planilhas e histórico fictícios
├── entrada/               onde ficam as 3 planilhas do mês (não vai para o Git)
├── dados/                 banco SQLite (não vai para o Git)
└── tests/                 testes automáticos
```

### De onde vem cada indicador

| Indicador | Arquivo › aba › linha |
|---|---|
| Custo Total MBRL | CUSTO TOTAL › Cash Cost 2026 Completo › "Custo Total (R$) \| sem Efeito Corp com Nexa Energy" |
| Custo OPEX MBRL | Gestão de Custos OPEX › (mesma aba e linha) |
| Cash Cost Total USD/t | CUSTO TOTAL › Cash Cost 2026 Completo › "Cash Cost (US$/t Prod. Alimentada)" |
| Cash Cost OPEX USD/t | Gestão de Custos OPEX › (mesma aba e linha) |
| Cash Cost G&A R$/t | Gestão de Custos OPEX › Meta G&A sem nexa e sem corp › "R$/Ton" |
| Receita Líquida KUSD | OCF › BD › "(=) Net Revenues" |
| OCF KUSD | OCF › BD › "(=) OCF" |
| NSR | OCF › BD › "NSR Financial" |
| Margem | calculada: OCF ÷ Receita Líquida |
| Investimento (Capex/Opex/Oro) KBRL | digitado à mão na aba Atualizar (não está nos 3 arquivos) |

### Regras de cálculo

- **Month**: valor da coluna do mês. **FY**: coluna do total anual.
- **YTD** de valores (R$, KUSD): soma de janeiro até o mês. **YTD de razões** (US$/t, R$/t): média simples dos meses.
- **Cenários**: a coluna *RF* é o forecast anterior ("RF ANT" / "RF -1") e a coluna *Real* é o forecast vigente
  ("RF"), que nos meses fechados já é o realizado.
- **Δ%** = Real ÷ referência − 1, calculado sobre os valores arredondados que o cartão mostra. A referência é o
  Budget nos custos e Cash Costs e o RF nos financeiros e no Investimento.
- **Faróis dos Cash Costs** (Real contra Budget na mesma visão): Meta 500 verde (Δ ≤ −2%), Meta 300 amarelo
  (até 0%), Meta 100 vermelho (até +4%), Meta 0 preto (acima de +4%). Limites em `painel/config.py`.

### Garantias do histórico

- Reprocessar um mês **atualiza** aquele mês, não cria linhas novas (chave primária + UPSERT).
- Se algum valor mudar, o anterior fica na tabela `fato_auditoria`.
- Um mês é gravado inteiro ou não é gravado (transação única).
- Reprocessar as planilhas não apaga o Investimento digitado à mão.
- Se faltar arquivo ou alguma aba mudar de layout, o sistema para com uma mensagem dizendo o que não achou,
  em vez de gravar número errado.

## Testes

```bash
cd PainelFinanceiro
python -m unittest discover -s tests -v
```

Cobrem as regras (Δ%, cores, faróis, formatação), a leitura das planilhas contra um gabarito calculado direto
pelo modelo fictício, o histórico (sem duplicar, auditoria, investimento manual), CSV, insights, PDF e o fluxo
completo pela API do Flask.

## Configuração (opcional)

| Variável | Para quê | Padrão |
|---|---|---|
| `PAINEL_DB` | caminho do banco SQLite (ex.: numa pasta de rede) | `dados/painel.db` |
| `PAINEL_PASTA` | pasta das 3 planilhas do mês | `entrada/` |
| `PAINEL_SOMENTE_LEITURA` | `1` esconde a aba Atualizar (quem só consulta) | `0` |
| `PORTA` | porta do servidor | `8000` |

Com o banco numa pasta de rede, só uma pessoa deve rodar **Atualizar** por vez: o SQLite não lida bem com duas
gravações simultâneas em compartilhamento de rede. As demais podem usar `PAINEL_SOMENTE_LEITURA=1`.

---
Ferramenta de apoio à análise gerencial. A validação final dos números é dos responsáveis financeiros.
