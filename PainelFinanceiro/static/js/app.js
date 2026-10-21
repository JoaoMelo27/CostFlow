/* =====================================================================
   Painel Financeiro — interface (JavaScript puro)

   Como funciona:
     - O topo tem o filtro de Ano e Mês, que vale para todas as abas.
     - Cada aba pede ao servidor (API em /api/...) o conteúdo já calculado
       e só monta o HTML. Nenhuma conta é feita aqui: Δ%, cores, faróis e
       formatação vêm prontos do Python, para a tela bater com o PDF e o CSV.
   ===================================================================== */

// ------------------------------------------------------------------ estado da tela
const estado = {
  ano: null,
  mes: null,
  aba: "painel",
  info: null,                    // resposta de /api/estado (períodos gravados etc.)
  visaoInsights: "month",
  historico: { anos: null, indicador: "todos", visao: "month", ordem: "cronologica", processamentosAberto: false },
  tokenPrevia: null,             // prévia do botão Atualizar ainda não confirmada
  mensagemAtualizar: null,       // "Setembro/2026 gravado: ..." depois de confirmar
  mensagemInvestimento: null,
};

// Gráficos desenhados na aba atual (redesenhados quando a janela muda de tamanho).
let desenhos = [];

// ------------------------------------------------------------------ utilidades
const $ = (id) => document.getElementById(id);

/** Escapa texto para colocar dentro de HTML com segurança. */
function esc(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/** Chama a API. Em caso de erro, lança um Error com a mensagem do servidor. */
async function api(url, corpo = null) {
  const opcoes = corpo === null ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo),
  };
  const resposta = await fetch(url, opcoes);
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) {
    const erro = new Error(dados.erro || `Erro ${resposta.status}`);
    erro.dados = dados;
    throw erro;
  }
  return dados;
}

function periodoQuery() {
  return `ano=${estado.ano}&mes=${estado.mes}`;
}

function temDados() {
  return estado.info && estado.info.periodos.length > 0;
}

function semDados(container) {
  container.innerHTML = "<p>Sem dados ainda.</p>";
}

function alerta(tipo, html) {
  return `<div class="alerta ${tipo}">${html}</div>`;
}

function carregando(sim) {
  $("carregando").hidden = !sim;
}

// ------------------------------------------------------------------ filtro de período (topo)
/** Lê os períodos gravados e monta os seletores de Ano e Mês. */
async function carregarEstado(periodoPreferido = null) {
  estado.info = await api("/api/estado");
  const info = estado.info;
  $("botao-aba-atualizar").hidden = info.somente_leitura;

  const vazio = info.periodos.length === 0;
  $("historico-vazio").hidden = !vazio;
  document.querySelectorAll("#filtros .seletor").forEach((s) => { s.hidden = vazio; });
  if (vazio) { estado.ano = estado.mes = null; return; }

  // período escolhido: o pedido (ex.: recém-gravado), o atual se ainda existir, ou o mais recente
  const existe = (a, m) => info.periodos.some(([pa, pm]) => pa === a && pm === m);
  if (periodoPreferido && existe(...periodoPreferido)) {
    [estado.ano, estado.mes] = periodoPreferido;
  } else if (!(estado.ano && existe(estado.ano, estado.mes))) {
    estado.ano = info.anos[0];
    estado.mes = info.meses_por_ano[String(estado.ano)][0];
  }
  montarSeletores();
}

function montarSeletores() {
  const info = estado.info;
  $("filtro-ano").innerHTML = info.anos
    .map((a) => `<option value="${a}" ${a === estado.ano ? "selected" : ""}>Ano ${a}</option>`).join("");
  $("filtro-mes").innerHTML = info.meses_por_ano[String(estado.ano)]
    .map((m) => `<option value="${m}" ${m === estado.mes ? "selected" : ""}>${info.nomes_meses[m - 1]}</option>`).join("");
}

$("filtro-ano").addEventListener("change", (ev) => {
  estado.ano = Number(ev.target.value);
  const meses = estado.info.meses_por_ano[String(estado.ano)];
  if (!meses.includes(estado.mes)) estado.mes = meses[0];
  montarSeletores();
  mostrarAba();
});

$("filtro-mes").addEventListener("change", (ev) => {
  estado.mes = Number(ev.target.value);
  mostrarAba();
});

// ------------------------------------------------------------------ abas
document.querySelectorAll("#abas button").forEach((botao) => {
  botao.addEventListener("click", () => {
    estado.aba = botao.dataset.aba;
    document.querySelectorAll("#abas button").forEach((b) => b.classList.toggle("ativa", b === botao));
    mostrarAba();
  });
});

async function mostrarAba() {
  document.querySelectorAll("section.aba").forEach((s) => { s.hidden = s.id !== `aba-${estado.aba}`; });
  desenhos = [];
  const telas = {
    painel: telaPainel, insights: telaInsights, atualizar: telaAtualizar, historico: telaHistorico, sobre: telaSobre,
  };
  try {
    await telas[estado.aba]();
  } catch (erro) {
    $(`aba-${estado.aba}`).insertAdjacentHTML("afterbegin", alerta("erro", esc(erro.message)));
  }
}

window.addEventListener("resize", () => {
  clearTimeout(window._redesenho);
  window._redesenho = setTimeout(() => desenhos.forEach((desenhar) => desenhar()), 150);
});

/** Desenha um gráfico agora e guarda para redesenhar se a janela mudar de tamanho. */
function desenhar(funcao) {
  funcao();
  desenhos.push(funcao);
}

// =================================================================== aba Painel
function htmlLegenda(cartao) {
  if (cartao.pendente) {
    return "<span class='pendente'>Pendente: preencher manualmente na aba Atualizar</span>";
  }
  if (cartao.farol) {
    return "<span class='farol'>" + cartao.legenda.map((i) =>
      `<span class='fi' title='${esc(i.dica)}'><i class='pt pt-${i.cor}'></i>${esc(i.texto)}</span>`).join("") + "</span>";
  }
  return cartao.legenda.map((i) => `<i class='pt pt-${i.cor}'></i>${esc(i.texto)}`).join(" ");
}

function htmlCartao(cartao) {
  const visoes = cartao.visoes.map((v) => `
      <div class='vis'>${esc(v.nome)}</div>
      <table>
        <colgroup><col style='width:24%'><col style='width:24%'><col style='width:26%'><col style='width:26%'></colgroup>
        <tr><th>Budget</th><th>RF</th><th>Real</th><th>${esc(cartao.rotulo_delta)}</th></tr>
        <tr><td>${esc(v.budget)}</td><td>${esc(v.rf)}</td><td class='real'>${esc(v.real)}</td>
            <td>${esc(v.delta)}<i class='pt pt-${v.cor}'></i></td></tr>
      </table>`).join("");
  return `<div class='card'><h4>${esc(cartao.nome)}</h4><div class='leg'>${htmlLegenda(cartao)}</div>${visoes}</div>`;
}

async function telaPainel() {
  const aba = $("aba-painel");
  if (!temDados()) return semDados(aba);
  const p = await api(`/api/painel?${periodoQuery()}`);
  aba.innerHTML = `
    <div class='cabecalho'>
      <div class='titulo'>PAINEL FINANCEIRO <b>|</b> ${esc(p.titulo)}<span class='sub'>Unidade Vazante</span></div>
      <img src='/static/img/nexa_logo.png' height='34' alt='Logo'>
    </div>
    <div class='grade'>
      <div><div class='grupo'>KPIs Custos</div><div class='cards c3'>${p.custos.map(htmlCartao).join("")}</div></div>
      <div><div class='grupo'>KPI's Financeiros</div><div class='cards c2'>${p.financeiros.map(htmlCartao).join("")}</div></div>
    </div>
    <div class='acoes-painel'>
      <a class='botao' href='/exportar/painel.pdf?${periodoQuery()}'>Exportar painel em PDF</a>
      <a class='botao' href='/exportar/painel.csv?${periodoQuery()}'>Exportar painel (CSV)</a>
    </div>
    <p class='legenda-texto' style='margin-top:1rem'>${esc(p.nota)}</p>`;
}

// =================================================================== aba Overview / Insights
async function telaInsights() {
  const aba = $("aba-insights");
  if (!temDados()) return semDados(aba);
  const d = await api(`/api/insights?${periodoQuery()}&visao=${estado.visaoInsights}`);

  const radios = ["month", "ytd", "fy"].map((v) => `
      <label><input type="radio" name="visao-insights" value="${v}" ${v === estado.visaoInsights ? "checked" : ""}>
      ${{ month: "Month", ytd: "YTD", fy: "FY" }[v]}</label>`).join("");

  const secoes = d.secoes.map((s) => `
      <details class='expansor' ${s.aberta ? "open" : ""}>
        <summary>${esc(s.titulo)}</summary>
        <div class='conteudo'>${s.itens.map((i) =>
          `<div class='ins ${i.nivel}'>${i.titulo ? `<span class='t'>${esc(i.titulo)}</span>` : ""}${esc(i.texto)}</div>`).join("")}
        </div>
      </details>`).join("");

  const evolucao = d.evolucao.map((e, i) => `
      <div>
        <div class='nota'><b>${esc(e.rotulo)}</b> — ${esc(e.unidade)}</div>
        <div id='grafico-evolucao-${i}'></div>
      </div>`).join("");

  const quadro = d.quadro.map((r) => `
      <tr><td class='l'>${esc(r.indicador)}</td><td class='real'>${esc(r.real)}</td>
        <td>${esc(r.budget)}</td><td>${esc(r.dif_budget)}</td><td class='v-${r.nivel_budget}'>${esc(r.pct_budget)}</td>
        <td>${esc(r.rf)}</td><td>${esc(r.dif_rf)}</td><td class='v-${r.nivel_rf}'>${esc(r.pct_rf)}</td></tr>`).join("");

  const comentarios = d.comentarios.map((c) => `
      <div class='comentario'><b>${esc(c.autor)}</b> · ${esc(c.sobre)} · <i>${esc(c.quando)}</i><br>${esc(c.texto)}</div>`).join("");

  aba.innerHTML = `
    <div class='topo-insights'>
      <h2>${esc(d.titulo)}</h2>
      <div><div class='rotulo'>Visão dos gráficos e do quadro</div><div class='radios'>${radios}</div></div>
    </div>

    <div class='colunas-insights'>
      <div>${secoes}</div>
      <div>
        <div class='sec'>Principais variações — Real contra a referência</div>
        <div class='nota'>Referência: Budget nos custos e cash cost; RF nos financeiros e no investimento.
          Verde = favorável · amarelo = desfavorável · vermelho = desfavorável a partir de ${esc(d.limiar_critico)}.
          Nos Cash Costs valem os faróis Meta 500/300/100/0 (preto = Meta 0).</div>
        <div id='grafico-variacoes'></div>
        <div class='sec' style='margin-top:1.5rem'>Custo realizado × orçamento</div>
        <div class='nota'>Budget, RF (forecast anterior) e Real (forecast vigente) em MBRL.</div>
        <div id='grafico-real-budget'></div>
      </div>
    </div>

    <div class='sec' style='margin-top:14px'>Evolução mensal (valor do mês)</div>
    <div class='tres-colunas'>${evolucao}</div>
    ${d.um_mes_so ? "<p class='legenda-texto'>Só há um mês no histórico; as linhas de evolução crescem a cada fechamento gravado.</p>" : ""}

    <div class='sec' style='margin-top:14px'>Quadro de variações — ${esc(d.visao)}</div>
    <div class='tabela-wrap'><table class='tab'>
      <tr><th class='l'>Indicador</th><th>Real</th><th>Budget</th><th>Real − Budget</th><th>Δ Bud</th>
          <th>RF</th><th>Real − RF</th><th>Δ RF</th></tr>
      ${quadro}
    </table></div>

    <hr>
    <h2>Comentários dos responsáveis</h2>
    <p class='legenda-texto'>Espaço para os responsáveis registrarem as causas das variações.</p>
    ${comentarios}
    <div class='formulario'>
      <label class='rotulo' for='comentario-autor'>Autor</label>
      <input class='campo' id='comentario-autor'>
      <label class='rotulo' for='comentario-sobre'>Sobre</label>
      <div class='seletor largo'><select id='comentario-sobre'>
        ${d.alvos_comentario.map((a) => `<option value='${esc(a.codigo)}'>${esc(a.nome)}</option>`).join("")}
      </select></div>
      <label class='rotulo' for='comentario-texto'>Comentário</label>
      <textarea class='campo' id='comentario-texto'></textarea>
      <div id='comentario-aviso'></div>
      <button class='botao' id='botao-comentar'>Registrar comentário</button>
    </div>`;

  desenhar(() => Graficos.variacoes($("grafico-variacoes"), d.variacoes));
  desenhar(() => Graficos.realXBudget($("grafico-real-budget"), d.real_x_budget));
  d.evolucao.forEach((e, i) => desenhar(() => Graficos.evolucao($(`grafico-evolucao-${i}`), e.grafico)));

  aba.querySelectorAll("input[name='visao-insights']").forEach((r) =>
    r.addEventListener("change", () => { estado.visaoInsights = r.value; telaInsights(); }));

  $("botao-comentar").addEventListener("click", async () => {
    try {
      await api("/api/comentarios", {
        ano: estado.ano, mes: estado.mes, autor: $("comentario-autor").value,
        indicador: $("comentario-sobre").value, texto: $("comentario-texto").value,
      });
      telaInsights();
    } catch (erro) {
      $("comentario-aviso").innerHTML = alerta("aviso", esc(erro.message));
    }
  });
}

// =================================================================== aba Atualizar
function preencherMesesManuais() {
  const nomes = estado.info ? estado.info.nomes_meses : [];
  $("manual-mes").innerHTML = nomes.map((n, i) => `<option value="${i + 1}">${esc(n)}</option>`).join("");
}

async function telaAtualizar() {
  if (!$("pasta").value) $("pasta").value = estado.info.pasta_padrao;
  if (!$("manual-mes").options.length) preencherMesesManuais();
  if (estado.mensagemAtualizar) {
    $("resultado-atualizar").innerHTML = alerta("sucesso", esc(estado.mensagemAtualizar));
    estado.mensagemAtualizar = null;
  }
  await telaInvestimento();
}

$("periodo-manual").addEventListener("change", (ev) => { $("periodo-manual-campos").hidden = !ev.target.checked; });

$("botao-atualizar").addEventListener("click", async () => {
  const saida = $("resultado-atualizar");
  saida.innerHTML = "";
  estado.tokenPrevia = null;
  carregando(true);
  try {
    const manual = $("periodo-manual").checked;
    const p = await api("/api/atualizar", {
      pasta: $("pasta").value, manual, ano: Number($("manual-ano").value), mes: Number($("manual-mes").value),
    });
    estado.tokenPrevia = p.token;
    mostrarPrevia(p);
  } catch (erro) {
    const d = erro.dados || {};
    saida.innerHTML = alerta("erro", esc(erro.message) + (d.detalhe ? `<pre>${esc(d.detalhe)}</pre>` : ""))
      + (d.nota ? `<p class='legenda-texto'>${esc(d.nota)}</p>` : "");
  } finally {
    carregando(false);
  }
});

function mostrarPrevia(p) {
  const icone = { ok: "✅", aviso: "⚠️", erro: "❌" };
  const colunas = ["Indicador", "Unidade", "Visão", "Budget", "RF", "Real", "Variação", "Comparada com"];
  $("resultado-atualizar").innerHTML = `
    ${alerta("sucesso", `Período lido: <b>${esc(p.periodo)}</b> · arquivos: ${p.arquivos.map(esc).join(" · ")}`)}
    ${p.ja_existe ? alerta("aviso", "Este mês já existe no histórico. Confirmar vai atualizar os valores dele; "
      + "qualquer valor que mudar fica registrado na auditoria. Os outros meses não são afetados.") : ""}
    <p><b>Validações</b></p>
    <ul class='validacoes'>${p.validacoes.map((v) => `<li>${icone[v.nivel]} ${esc(v.mensagem)}</li>`).join("")}</ul>
    <p><b>Prévia dos valores calculados</b></p>
    <div class='grade-dados limitada'><table>
      <tr>${colunas.map((c) => `<th>${c}</th>`).join("")}</tr>
      ${p.previa.map((l) => `<tr>${colunas.map((c) => `<td>${esc(l[c])}</td>`).join("")}</tr>`).join("")}
    </table></div>
    <button class='botao primario' id='botao-confirmar' ${p.tem_erro ? "disabled" : ""}>Confirmar e salvar no histórico</button>`;

  $("botao-confirmar").addEventListener("click", async () => {
    try {
      const r = await api("/api/confirmar", { token: estado.tokenPrevia });
      estado.tokenPrevia = null;
      estado.mensagemAtualizar = r.mensagem;
      $("resultado-atualizar").innerHTML = "";
      await carregarEstado([r.ano, r.mes]);       // o filtro do topo passa para o mês gravado
      await telaAtualizar();
    } catch (erro) {
      $("resultado-atualizar").insertAdjacentHTML("beforeend", alerta("erro", esc(erro.message)));
    }
  });
}

async function telaInvestimento() {
  const caixa = $("investimento");
  if (!temDados()) {
    caixa.innerHTML = alerta("info", "Processe o primeiro mês pelas planilhas; depois o Investimento pode ser preenchido aqui.");
    return;
  }
  const d = await api(`/api/investimento?${periodoQuery()}`);
  const linhas = d.linhas.map((l) => `
      <div class='inv-rotulo'><b>${esc(l.nome)}</b></div>
      ${l.campos.map((c) => `<input class='campo' data-visao='${l.visao}' data-cenario='${c.cenario}'
                               aria-label='${esc(l.nome)} · ${esc(c.nome)}' value='${esc(c.valor)}'>`).join("")}`).join("");
  caixa.innerHTML = `
    <p>Período: <b>${esc(d.periodo)}</b> (o mesmo escolhido no topo da tela). Digite os 9 valores em KBRL, do jeito
      que estão no relatório de investimentos (ex.: 21.500). Reprocessar as planilhas <b>não apaga</b> estes valores.</p>
    <p class='legenda-texto'>${d.ultima_gravacao ? `Última gravação: ${esc(d.ultima_gravacao)}`
      : "Ainda não preenchido para este mês: o cartão do painel fica como pendente."}</p>
    ${estado.mensagemInvestimento ? alerta("sucesso", esc(estado.mensagemInvestimento)) : ""}
    <div class='formulario'>
      <div class='grade-investimento'>
        <div></div><div><b>Budget</b></div><div><b>RF</b></div><div><b>Real</b></div>
        ${linhas}
      </div>
      <button class='botao primario' id='botao-investimento'>Salvar Investimento</button>
    </div>
    <div id='investimento-erro'></div>`;
  estado.mensagemInvestimento = null;

  $("botao-investimento").addEventListener("click", async () => {
    const valores = {};
    caixa.querySelectorAll("input[data-visao]").forEach((campo) => {
      (valores[campo.dataset.visao] ??= {})[campo.dataset.cenario] = campo.value;
    });
    try {
      const r = await api("/api/investimento", { ano: estado.ano, mes: estado.mes, valores });
      estado.mensagemInvestimento = r.mensagem;
      await telaInvestimento();
    } catch (erro) {
      $("investimento-erro").innerHTML = alerta("erro", esc(erro.message));
    }
  });
}

// =================================================================== aba Histórico
async function telaHistorico() {
  const aba = $("aba-historico");
  if (!temDados()) return semDados(aba);
  const f = estado.historico;
  if (f.anos === null) f.anos = [...estado.info.anos];     // por padrão, todos os anos
  const query = `anos=${f.anos.join(",")}&indicador=${f.indicador}&visao=${f.visao}`;
  const d = await api(`/api/historico?${query}&ordem=${f.ordem === "recentes" ? "recentes" : "cronologica"}`);

  const fichas = d.anos.map((a) =>
    `<button class='ficha ${f.anos.includes(a) ? "marcada" : ""}' data-ano='${a}'>${a}</button>`).join("");
  const opcoes = (lista, atual) => lista.map((o) =>
    `<option value='${o.codigo}' ${o.codigo === atual ? "selected" : ""}>${esc(o.nome)}</option>`).join("");

  let corpo;
  if (!f.anos.length) {
    corpo = alerta("info", "Escolha ao menos um ano.");
  } else {
    corpo = (d.grafico ? `<div class='sec'>${esc(d.grafico.titulo)}</div><div id='grafico-historico'></div>` : "")
      + tabelaHistorico(d)
      + `<p style='margin-top:1rem'><a class='botao' href='/exportar/historico.csv?${query}'>Exportar histórico filtrado (CSV)</a></p>
         <p class='legenda-texto'>O CSV segue os filtros acima (anos, indicador e visão), em ordem cronológica,
           com separador ';' e acentos para abrir direto no Excel em português.</p>`;
  }

  const processamentos = d.processamentos.length ? `
      <div class='tabela-wrap'><table class='tab'>
        <tr><th class='l'>Período</th><th class='l'>Última gravação</th><th>Vezes processado</th>
            <th>Valores alterados na última</th><th class='l'>Arquivos usados</th></tr>
        ${d.processamentos.map((r) => `<tr><td class='l'>${esc(r.periodo)}</td><td class='l'>${esc(r.quando)}</td>
            <td>${r.vezes}</td><td>${r.alterados}</td><td class='l u'>${esc(r.arquivos)}</td></tr>`).join("")}
      </table></div>` : "<p>Sem registros.</p>";

  aba.innerHTML = `
    <div class='nota'>${esc(d.resumo)}</div>
    <div class='grade-filtros-historico'>
      <div><div class='rotulo'>Ano</div><div class='fichas'>${fichas}</div></div>
      <div><label class='rotulo' for='hist-indicador'>Indicador</label>
        <div class='seletor'><select id='hist-indicador'>${opcoes(d.indicadores, f.indicador)}</select></div></div>
      <div><label class='rotulo' for='hist-visao'>Visão</label>
        <div class='seletor'><select id='hist-visao'>${opcoes(d.visoes, f.visao)}</select></div></div>
      <div><div class='rotulo'>Ordem</div><div class='radios vertical'>
        <label><input type='radio' name='hist-ordem' value='cronologica' ${f.ordem !== "recentes" ? "checked" : ""}> Cronológica</label>
        <label><input type='radio' name='hist-ordem' value='recentes' ${f.ordem === "recentes" ? "checked" : ""}> Mais recente primeiro</label>
      </div></div>
    </div>
    ${corpo}
    <details class='expansor' style='margin-top:1rem' ${f.processamentosAberto ? "open" : ""} id='hist-processamentos'>
      <summary>Registro de processamentos</summary>
      <div class='conteudo'>${processamentos}</div>
    </details>`;

  if (d.grafico && f.anos.length) desenhar(() => Graficos.evolucao($("grafico-historico"), d.grafico, 260));

  aba.querySelectorAll(".ficha").forEach((b) => b.addEventListener("click", () => {
    const ano = Number(b.dataset.ano);
    f.anos = f.anos.includes(ano) ? f.anos.filter((a) => a !== ano) : [...f.anos, ano].sort();
    telaHistorico();
  }));
  $("hist-indicador").addEventListener("change", (ev) => { f.indicador = ev.target.value; telaHistorico(); });
  $("hist-visao").addEventListener("change", (ev) => { f.visao = ev.target.value; telaHistorico(); });
  aba.querySelectorAll("input[name='hist-ordem']").forEach((r) =>
    r.addEventListener("change", () => { f.ordem = r.value; telaHistorico(); }));
  $("hist-processamentos").addEventListener("toggle", (ev) => { f.processamentosAberto = ev.target.open; });
}

function tabelaHistorico(d) {
  if (!d.linhas.length) return "<div class='nota'>Nenhum dado para os filtros escolhidos.</div>";
  const valores = (l) => `<td>${esc(l.budget)}</td><td>${esc(l.rf)}</td><td class='real'>${esc(l.real)}</td>
      <td class='v-${l.nivel}'>${esc(l.variacao)}</td><td class='l u'>${esc(l.comparada)}</td>`;
  let cabecalho, linhas;
  if (d.unico) {
    cabecalho = "<th class='l'>Período</th>";
    linhas = d.linhas.map((l) => `<tr><td class='l'>${esc(l.periodo)}</td>${valores(l)}</tr>`);
  } else {
    cabecalho = "<th class='l'>Indicador</th><th class='l'>Unid.</th>";
    linhas = d.linhas.map((l) => l.grupo
      ? `<tr class='grupo-linha'><td colspan='7'>${esc(l.grupo)}</td></tr>`
      : `<tr><td class='l'>${esc(l.indicador)}</td><td class='l u'>${esc(l.unidade)}</td>${valores(l)}</tr>`);
  }
  return `<div class='tabela-wrap alta'><table class='tab'>
      <tr>${cabecalho}<th>Budget</th><th>RF</th><th>Real</th><th>Variação</th><th class='l'>Comparada com</th></tr>
      ${linhas.join("")}</table></div>`;
}

// =================================================================== aba Sobre
async function telaSobre() {
  const aba = $("aba-sobre");
  const d = await api(`/api/sobre${temDados() ? "?" + periodoQuery() : ""}`);
  const colunas = ["Indicador", "Unidade", "Δ contra", "Regra de cor", "Fonte"];
  let ultimo = "";
  if (d.ultimo) {
    const u = d.ultimo;
    if (u.quando) {
      ultimo = `<p><b>Última gravação de ${esc(u.periodo)}:</b> ${esc(u.quando)} · ${u.registros} valores · ${u.alterados} alterados</p>
        <p class='legenda-texto'>Arquivos usados: ${esc(u.arquivos)}</p>
        ${u.avisos ? `<p class='legenda-texto'>Avisos: ${esc(u.avisos)}</p>` : ""}`;
    }
    ultimo += `<p class='legenda-texto'>Registros de auditoria (valores corrigidos em reprocessamentos) deste mês: ${u.auditoria}</p>`;
  }
  aba.innerHTML = `
    <h2>Rastreabilidade</h2>
    <p>De onde vem cada indicador e qual é a base do Δ e da cor:</p>
    <div class='grade-dados'><table>
      <tr>${colunas.map((c) => `<th>${c}</th>`).join("")}</tr>
      ${d.rastreabilidade.map((l) => `<tr>${colunas.map((c) => `<td>${esc(l[c])}</td>`).join("")}</tr>`).join("")}
    </table></div>
    <p class='legenda-texto'>${esc(d.base)}</p>
    <p><b>Convenção de cenários nos arquivos-fonte.</b> A coluna <i>RF</i> do painel corresponde ao forecast anterior
      ("RF ANT" no OCF, "RF -1" nas abas de custo) e a coluna <i>Real</i> corresponde ao forecast vigente ("RF"),
      que nos meses fechados já reflete o realizado.</p>
    ${ultimo}
    <p class='legenda-texto'>Ferramenta de apoio à análise gerencial. A validação final dos números é dos responsáveis financeiros.</p>`;
}

// =================================================================== início
(async function iniciar() {
  try {
    await carregarEstado();
    await mostrarAba();
  } catch (erro) {
    document.querySelector(".pagina").insertAdjacentHTML("afterbegin",
      alerta("erro", "Não consegui falar com o servidor do painel. Ele está rodando? " + esc(erro.message)));
  }
})();
