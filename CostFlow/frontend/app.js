/* CostFlow — versão HTML/CSS/JS puro (sem dependências) */

// ── Dados ───────────────────────────────────────────────────────────────────
const monthly = [
  ["Jan", 320000, 298000, 310000], ["Fev", 340000, 325000, 332000], ["Mar", 355000, 341000, 349000],
  ["Abr", 370000, 388000, 380000], ["Mai", 360000, 372000, 368000], ["Jun", 375000, 362000, 370000],
  ["Jul", 390000, 332000, 362000], ["Ago", 362000, 344000, 352000], ["Set", 378000, 325500, 348000],
].map(([mes, budget, actual, forecast]) => ({ mes, budget, actual, forecast }));

const imports = [
  ["custos_setembro_v2.xlsx", "Analista João", "12/10/2024", "success"],
  ["forecast_q4_vfinal.csv", "Admin Nexa", "10/10/2024", "warning"],
  ["budget_anual_2024.xlsx", "Admin Nexa", "01/10/2024", "success"],
  ["custos_agosto_v3.xlsx", "Analista Maria", "05/09/2024", "success"],
  ["forecast_q3_rev2.xlsx", "Analista João", "22/08/2024", "error"],
];
const rows = [
  ["Manutenção Industrial", 150000, 147000, 142300], ["Logística e Fretes", 85000, 88000, 92100],
  ["TI e Software", 42000, 41500, 41850], ["RH e Benefícios", 195000, 198000, 201400],
  ["Infraestrutura", 63000, 61000, 58900], ["Comercial", 74000, 75000, 76250],
].map(([categoria, budget, forecast, actual]) => ({ categoria, periodo: "Set/2024", budget, forecast, actual }));
const users = [
  ["Admin Nexa", "admin@nexa.com.br", "Administrador", "—", 1, "Hoje, 14:32"],
  ["João Silva", "joao.silva@nexa.com.br", "Analista", "Controladoria", 1, "Hoje, 11:15"],
  ["Maria Santos", "maria.santos@nexa.com.br", "Analista", "Operações", 1, "Ontem, 17:40"],
  ["Carlos Mendes", "carlos.mendes@nexa.com.br", "Visualizador", "Diretoria", 1, "28/09/2024"],
  ["Ana Ferreira", "ana.ferreira@nexa.com.br", "Visualizador", "Comercial", 0, "15/08/2024"],
];
const reports = [
  ["Consolidação Mensal — Set/2024", "Resumo completo de Budget, Forecast e Actual por categoria", "12/10/2024", "PDF"],
  ["Comparativo Anual 2024", "Evolução acumulada vs. Budget ao longo dos 9 meses", "10/10/2024", "XLSX"],
  ["Desvios por Área — Q3 2024", "Análise de desvios do 3º trimestre por centro de custo", "02/10/2024", "PDF"],
  ["Forecast Q4 2024", "Projeção de custos para o 4º trimestre", "01/10/2024", "PDF"],
];
const MONTHS = monthly.map(m => m.mes + "/2024");
const nav = [["dashboard", "Dashboard", "layout-dashboard"], ["importar", "Importar Planilha", "cloud-upload"],
  ["consultar", "Consultar Dados", "search"], ["relatorios", "Relatórios", "chart-column"], ["usuarios", "Usuários", "users"]];
const titles = { dashboard: "Consolidação de Custos", importar: "Importar Planilha", consultar: "Consultar Dados", relatorios: "Relatórios", usuarios: "Gerenciar Usuários" };

// ── Helpers ─────────────────────────────────────────────────────────────────
const fmt = v => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 0 });
const fmtFull = v => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const k = v => `${v > 0 ? "+" : ""}${(v / 1000).toFixed(0)}k`;
const $ = s => document.querySelector(s);
const legend = items => `<div class="legend">${items.map(([c, l]) => `<span><i style="background:${c}"></i>${l}</span>`).join("")}</div>`;
const statusMap = { success: ["ok", "SUCESSO", "file-check"], warning: ["warn", "AVISO", "circle-alert"], error: ["err", "ERRO", "x"] };

// ── Gráficos SVG ────────────────────────────────────────────────────────────
function frame(W, H, m, lo, hi, step, cats) {
  const iw = W - m.l - m.r, ih = H - m.t - m.b, y = v => m.t + ih * (1 - (v - lo) / (hi - lo));
  let s = "";
  for (let v = lo; v <= hi; v += step)
    s += `<line x1="${m.l}" x2="${W - m.r}" y1="${y(v)}" y2="${y(v)}" stroke="#f3f4f6" stroke-dasharray="3 3"/><text x="${m.l - 6}" y="${y(v) + 3}" text-anchor="end" font-size="10" fill="#9ca3af">${(v / 1000).toFixed(0)}k</text>`;
  const bw = iw / cats.length;
  cats.forEach((c, i) => s += `<text x="${m.l + bw * (i + .5)}" y="${H - 8}" text-anchor="middle" font-size="11" fill="#9ca3af">${c}</text>`);
  return { s, y, bw, x: i => m.l + bw * i };
}

function deviationChart() {
  const d = monthly.map(m => [m.actual - m.budget, m.actual - m.forecast]);
  const W = 700, H = 210, m = { l: 40, r: 8, t: 10, b: 26 };
  const f = frame(W, H, m, -60000, 20000, 20000, monthly.map(m => m.mes));
  let s = f.s + `<line x1="${m.l}" x2="${W - m.r}" y1="${f.y(0)}" y2="${f.y(0)}" stroke="#e5e7eb" stroke-width="1.5"/>`;
  d.forEach((pair, i) => pair.forEach((v, j) => {
    const w = f.bw * .36, x = f.x(i) + f.bw * .14 + j * (w + 3), y0 = f.y(0), y1 = f.y(v);
    const c = j ? (v < 0 ? "#4ade80" : "#f87171") : (v < 0 ? "#16a34a" : "#dc2626");
    s += `<rect x="${x}" y="${Math.min(y0, y1)}" width="${w}" height="${Math.abs(y1 - y0)}" rx="3" fill="${c}" opacity="${j ? .7 : .85}"><title>${monthly[i].mes} — ${j ? "vs Forecast" : "vs Budget"}: ${k(v)}</title></rect>`;
  }));
  return `<svg class="chart" viewBox="0 0 ${W} ${H}">${s}</svg>`;
}

function bridgeData() {
  let run = monthly.reduce((a, m) => a + m.budget, 0);
  const out = [{ name: "Budget", base: 0, fb: run, af: 0, end: run, type: "start" }];
  monthly.forEach(m => {
    const dfb = m.forecast - m.budget, daf = m.actual - m.forecast, delta = m.actual - m.budget, after = run + delta;
    out.push({ name: m.mes, base: Math.min(run, after), fb: Math.abs(dfb), af: Math.abs(daf), dfb, daf, delta, end: after, type: delta < 0 ? "saving" : "over" });
    run = after;
  });
  out.push({ name: "Actual", base: 0, fb: run, af: 0, end: run, type: "end" });
  return out;
}

function bridgeChart() {
  const b = bridgeData(), ends = b.filter(e => e.type !== "start" && e.type !== "end").map(e => e.end).concat(b[0].end);
  const lo = Math.floor((Math.min(...ends) - 50000) / 50000) * 50000, hi = Math.ceil((Math.max(...ends) + 30000) / 50000) * 50000;
  const W = 700, H = 290, m = { l: 44, r: 8, t: 26, b: 26 };
  const f = frame(W, H, m, lo, hi, 50000, b.map(e => e.name));
  const col = { start: ["#3C3C3B"], end: ["#F36C21"], saving: ["#4ade80", "#16a34a"], over: ["#fca5a5", "#dc2626"] };
  let s = f.s;
  b.forEach((e, i) => {
    const w = Math.min(f.bw * .8, 56), x = f.x(i) + (f.bw - w) / 2, c = col[e.type], tot = e.type === "start" || e.type === "end";
    const seg = (from, to, fill, label, tip) => {
      const y1 = f.y(Math.min(to, hi)), y0 = f.y(Math.max(from, lo)), h = y0 - y1;
      if (h <= 0) return "";
      const lbl = h >= 14 ? `<text x="${x + w / 2}" y="${y1 + h / 2 + 4}" text-anchor="middle" font-size="10" font-weight="700" fill="${tot ? "#fff" : e.type === "saving" ? "#14532d" : "#7f1d1d"}">${label}</text>` : "";
      return `<rect x="${x}" y="${y1}" width="${w}" height="${h}" fill="${fill}"><title>${tip}</title></rect>${lbl}`;
    };
    const tipT = `${e.name}: ${fmt(e.end)}`, tipB = `${e.name}\nΔ Forecast vs Budget: ${k(e.dfb || 0)}\nΔ Actual vs Forecast: ${k(e.daf || 0)}\nTotal Δ: ${fmt(e.delta || 0)}\nAcumulado: ${fmt(e.end)}`;
    if (tot) s += seg(0, e.fb, c[0], `${(e.fb / 1000).toFixed(0)}k`, tipT);
    else {
      s += seg(e.base, e.base + e.fb, c[0], k(e.dfb), tipB) + seg(e.base + e.fb, e.base + e.fb + e.af, c[1], k(e.daf), tipB);
      s += `<text x="${x + w / 2}" y="${f.y(e.base + e.fb + e.af) - 5}" text-anchor="middle" font-size="10" font-weight="800" fill="${e.type === "saving" ? "#15803d" : "#b91c1c"}">${k(e.delta)}</text>`;
    }
    if (i < b.length - 1) s += `<line x1="${x + w}" x2="${f.x(i + 1) + (f.bw - w) / 2}" y1="${f.y(e.end)}" y2="${f.y(e.end)}" stroke="#94a3b8" stroke-dasharray="4 3"/>`;
  });
  return `<svg class="chart" viewBox="0 0 ${W} ${H}">${s}</svg>`;
}

// ── Componentes ─────────────────────────────────────────────────────────────
const kpi = (label, val, sub, accent, valColor = "", subColor = "var(--g400)") =>
  `<div class="card kpi" style="border-left-color:${accent}"><p>${label}</p><h3 style="color:${valColor || "var(--dark)"}">${val}</h3><small style="color:${subColor}">${sub}</small></div>`;

const devCell = (a, ref) => {
  const p = (a - ref) / ref * 100;
  return `<td><span class="dev ${p < 0 ? "neg" : "pos"}">${icon(p < 0 ? "arrow-down-right" : "arrow-up-right", 14)}${p > 0 ? "+" : ""}${p.toFixed(2)}%</span></td>`;
};
const costRows = (list, edit) => list.map(r => `<tr><td class="name">${r.categoria}</td><td>${r.periodo}</td><td>${fmtFull(r.budget)}</td><td>${fmtFull(r.forecast)}</td><td class="act">${fmtFull(r.actual)}</td>${devCell(r.actual, r.budget)}${devCell(r.actual, r.forecast)}${edit ? `<td class="r"><button class="ib">${icon("square-pen")}</button></td>` : ""}</tr>`).join("");
const head = cols => `<thead><tr>${cols.map((c, i) => `<th${i === cols.length - 1 && c === "Ações" ? ' class="r"' : ""}>${c}</th>`).join("")}</tr></thead>`;
const costCols = ["Categoria / Área", "Período", "Budget", "Forecast", "Actual", "Desv. vs Budget", "Desv. vs Forecast"];
const options = list => list.map(o => `<option>${o}</option>`).join("");

function tile(title, dev, pct, word, l1, v1, l2, v2, prog, progLabel) {
  return `<div class="tile"><div class="row"><div><p class="lbl">${title}</p><p class="big">${fmt(dev)}</p><p class="sub">${pct.toFixed(2)}% ${word}</p></div>
    <div class="side"><div><span>${l1}</span><b>${fmt(v1)}</b></div><div><span>${l2}</span><b style="color:var(--orange)">${fmt(v2)}</b></div></div></div>
    <div class="pb"><div class="row"><span>${progLabel}</span><b>${prog.toFixed(1)}%</b></div><div class="bar"><i style="width:${prog}%"></i></div></div></div>`;
}

// ── Páginas ─────────────────────────────────────────────────────────────────
const TB = 4250000, TF = 4310000, TA = 3890500;
const pages = {
  dashboard: () => `<div class="page">
    <div class="grid g4">
      ${kpi("Budget Total (Anual)", "R$ 4.250.000", "Planejado em Jan/2024", "#3C3C3B")}
      ${kpi("Forecast (Projetado)", "R$ 4.310.000", "↑ 1.4% vs Budget", "#F5B800", "", "#ca8a04")}
      ${kpi("Actual (Realizado)", "R$ 3.890.500", "Acumulado até Setembro", "#F36C21", "#F36C21")}
      ${kpi("Saving (Economia)", "R$ 359.500", "Em relação ao Budget", "#d1d5db", "#16a34a", "#16a34a")}
    </div>
    <div class="card">
      <h4>Análise de Desvios — Realizado vs Referências</h4><p class="muted" style="margin-bottom:24px">Acumulado Jan–Set/2024 · valores negativos = economia</p>
      <div class="grid g2" style="margin-bottom:24px">
        ${tile("Realizado vs Budget", TA - TB, (TB - TA) / TB * 100, "abaixo do orçado", "Budget", TB, "Actual", TA, TA / TB * 100, "Execução orçamentária")}
        ${tile("Realizado vs Forecast", TA - TF, (TF - TA) / TF * 100, "abaixo do projetado", "Forecast", TF, "Actual", TA, TA / TF * 100, "Execução vs projeção")}
      </div>
      <p class="lbl" style="margin-bottom:12px">Desvio mensal por referência (Actual − referência)</p>
      ${deviationChart()}
      ${legend([["#16a34a", "vs Budget (economia)"], ["#dc2626", "vs Budget (estouro)"], ["#4ade80", "vs Forecast (economia)"], ["#f87171", "vs Forecast (estouro)"]])}
    </div>
    <div class="grid g5">
      <div class="card"><div class="row"><div><h4>Budget → Actual — Bridge Mensal</h4><p class="muted">Jan–Set/2024 · cada barra = desvio do mês vs Budget</p></div><button style="color:var(--g400)">${icon("ellipsis", 20)}</button></div>
        ${bridgeChart()}
        ${legend([["#3C3C3B", "Budget"], ["#F36C21", "Actual"], ["#4ade80", "Δ Forecast vs Budget"], ["#16a34a", "Δ Actual vs Forecast"], ["#fca5a5", "Δ Forecast vs Budget (estouro)"], ["#dc2626", "Δ Actual vs Forecast (estouro)"]])}</div>
      <div class="card"><div class="row" style="margin-bottom:20px"><h4>Últimas Importações</h4><button class="link">Ver todas</button></div>
        ${imports.map(([f, u, d, s]) => { const [c, t, ic] = statusMap[s]; return `<div class="imp"><span class="ico ${c}">${icon(ic)}</span><div class="t"><p>${f}</p><small>${u} · ${d}</small></div><span class="tag ${c}">${t}</span></div>`; }).join("")}</div>
    </div>
    <div class="card flush"><div class="thead"><h4>Detalhamento por Categoria</h4><div style="display:flex;gap:8px">
      <button class="btn ghost">${icon("funnel", 14)}Filtros</button><button class="btn dark">${icon("file-down", 14)}Exportar PDF</button></div></div>
      <table>${head([...costCols, "Ações"])}<tbody>${costRows(rows, true)}</tbody></table>
      <div class="tfoot"><span>Exibindo 6 de 48 registros</span><div class="pg">${[1, 2, 3, "..."].map(p => `<button class="${p === 1 ? "on" : ""}">${p}</button>`).join("")}</div></div></div>
  </div>`,

  importar: () => `<div class="page narrow">
    <div class="card" style="padding:32px"><h3 style="margin-bottom:4px">Importar Planilha de Custos</h3><p class="muted" style="font-size:14px;margin-bottom:24px">Formatos aceitos: .xlsx, .xls, .csv — máx. 20 MB</p><div id="importBox"></div></div>
    <div class="card"><h4 style="margin-bottom:16px">Estrutura esperada da planilha</h4><div style="overflow-x:auto"><table class="small">${head(["Coluna", "Tipo", "Obrigatório", "Descrição"])}<tbody>
      ${[["categoria", "Texto", "Sim", "Nome da área ou centro de custo"], ["periodo", "Data (MM/AAAA)", "Sim", "Período de referência dos valores"], ["tipo_valor", "Budget / Forecast / Actual", "Sim", "Natureza do valor financeiro"], ["valor", "Numérico (R$)", "Sim", "Valor monetário correspondente"], ["descricao", "Texto", "Não", "Descrição ou observações adicionais"]]
        .map(([c, t, o, d]) => `<tr><td><code>${c}</code></td><td>${t}</td><td><span class="tag ${o === "Sim" ? "or" : "gr"}">${o}</span></td><td>${d}</td></tr>`).join("")}</tbody></table></div></div></div>`,

  consultar: () => `<div class="page gap24">
    <div class="card grid" style="grid-template-columns:repeat(4,1fr);gap:16px;align-items:end">
      <div><label>Período</label><select id="fPer">${options(MONTHS)}</select></div>
      <div><label>Tipo de Valor</label><select id="fTipo"><option value="all">Todos</option><option>Budget</option><option>Forecast</option><option>Actual</option></select></div>
      <div><label>Área / Categoria</label><select id="fCat"><option value="">Todas as áreas</option>${options(rows.map(r => r.categoria))}</select></div>
      <button class="btn" id="apply" style="justify-content:center;padding:10px">Aplicar Filtros</button></div>
    <div class="card flush"><div class="thead"><div><h4 id="resTitle"></h4><p class="muted" id="resCount"></p></div><button class="btn dark">${icon("file-down", 14)}Exportar</button></div>
      <table>${head(costCols)}<tbody id="resBody"></tbody></table></div></div>`,

  relatorios: () => `<div class="page gap24"><div class="grid" style="grid-template-columns:1fr 1fr">
    ${reports.map(([t, d, dt, ty]) => `<div class="card rep"><div class="ri">${icon("chart-column", 24)}</div><div class="b"><p>${t}</p><small>${d}</small><div class="m"><small style="margin:0">${dt}</small><span class="tag or">${ty}</span></div></div><div class="s"><button>${icon("eye")}</button><button>${icon("file-down")}</button></div></div>`).join("")}</div>
    <div class="card"><h4 style="margin-bottom:16px">Gerar Novo Relatório</h4><div class="grid g3" style="margin-bottom:16px">
      <div><label>Tipo</label><select>${options(["Consolidação Mensal", "Comparativo Anual", "Análise de Desvios"])}</select></div>
      <div><label>Período</label><select>${options(MONTHS)}</select></div>
      <div><label>Formato</label><select>${options(["PDF", "Excel (.xlsx)", "CSV"])}</select></div></div>
      <button class="btn" style="padding:10px 20px">Gerar Relatório</button></div></div>`,

  usuarios: () => `<div class="page gap24"><div class="row" style="align-items:center"><div class="filters" id="uFilters">
      ${["Todos", "Administrador", "Analista", "Visualizador"].map((f, i) => `<button class="chip ${i ? "" : "on"}" data-f="${f}">${f}</button>`).join("")}</div>
      <button class="btn">${icon("plus")}Novo Usuário</button></div>
    <div class="card flush"><table>${head(["Usuário", "Perfil", "Área / Setor", "Status", "Último Acesso", "Ações"])}<tbody id="uBody"></tbody></table></div></div>`,
};

// ── Interações por página ───────────────────────────────────────────────────
const perfil = { Administrador: "or", Analista: "bl", Visualizador: "ok" };
const init = {
  importar() {
    const box = $("#importBox");
    const upload = () => {
      box.innerHTML = `<div class="drop"><div class="big-ic">${icon("upload", 32)}</div><div><b>Arraste a planilha aqui</b><br><small>ou clique para selecionar o arquivo</small></div><span class="btn">Selecionar arquivo</span></div>`;
      const d = box.firstChild;
      d.onclick = simulate;
      d.ondragover = e => { e.preventDefault(); d.classList.add("over"); };
      d.ondragleave = () => d.classList.remove("over");
      d.ondrop = e => { e.preventDefault(); simulate(); };
    };
    const simulate = () => {
      const f = "custos_outubro_v1.xlsx";
      box.innerHTML = `<div class="state"><span class="spin">${icon("refresh-cw", 40)}</span><div><b>${f}</b><p class="muted" style="font-size:14px">Validando estrutura e campos obrigatórios...</p></div></div>`;
      setTimeout(() => {
        box.innerHTML = `<div class="state done">${icon("circle-check", 40)}<div><b>${f}</b><p style="color:var(--green);font-weight:500;margin-top:4px">Arquivo validado com sucesso!</p><p class="muted">482 linhas · Período: Outubro/2024 · 6 categorias</p></div>
          <div style="display:flex;gap:12px"><button class="btn ghost" id="cancel" style="font-size:14px">Cancelar</button><button class="btn">Confirmar Importação</button></div></div>`;
        $("#cancel").onclick = upload;
      }, 2000);
    };
    upload();
  },
  consultar() {
    const render = () => {
      const per = $("#fPer").value, cat = $("#fCat").value, tipo = $("#fTipo").value;
      let list = rows.filter(r => !cat || r.categoria === cat);
      if (tipo !== "all") list = list.filter((_, i) => i % 2 === 0); // filtro ilustrativo, igual ao protótipo
      $("#resTitle").textContent = `Resultados — ${per}`;
      $("#resCount").textContent = `${list.length} registros encontrados`;
      $("#resBody").innerHTML = costRows(list.map(r => ({ ...r, periodo: per })), false);
    };
    $("#apply").onclick = render; $("#fPer").value = "Set/2024"; render();
  },
  usuarios() {
    const render = f => {
      $("#uBody").innerHTML = users.filter(u => f === "Todos" || u[2] === f).map(([n, e, p, a, on, last]) =>
        `<tr><td><div style="display:flex;align-items:center;gap:12px"><div class="avatar" style="width:32px;height:32px;font-size:12px">${n.split(" ").map(x => x[0]).join("").slice(0, 2)}</div><div><div class="name" style="font-weight:500;color:var(--g800)">${n}</div><small class="muted">${e}</small></div></div></td>
        <td><span class="tag ${perfil[p]}">${p}</span></td><td>${a}</td><td><span class="tag ${on ? "ok" : "gr"}">${on ? "Ativo" : "Inativo"}</span></td><td>${last}</td>
        <td class="r"><button class="ib">${icon("square-pen")}</button><button class="ib del">${icon("trash-2")}</button></td></tr>`).join("");
    };
    $("#uFilters").onclick = e => {
      const b = e.target.closest(".chip"); if (!b) return;
      document.querySelectorAll("#uFilters .chip").forEach(c => c.classList.toggle("on", c === b));
      render(b.dataset.f);
    };
    render("Todos");
  },
};

// ── Roteamento e inicialização ──────────────────────────────────────────────
function go(id) {
  $("#nav").innerHTML = nav.map(([i, l, ic]) => `<button data-id="${i}" class="${i === id ? "active" : ""}">${icon(ic, 18)}${l}</button>`).join("");
  $("#title").textContent = titles[id];
  $("#page").innerHTML = pages[id]();
  $("#page").scrollTop = 0;
  init[id]?.();
}

$("#logo").innerHTML = icon("trending-up", 20).replace('class="ic"', 'class="ic" style="color:#fff"');
$("#logout").innerHTML = icon("log-out");
$("#bell").insertAdjacentHTML("afterbegin", icon("bell", 20));
$("#search").insertAdjacentHTML("afterbegin", icon("calendar"));
$("#newImport").innerHTML = icon("plus") + "Nova Importação";
$("#closeModal").innerHTML = icon("x", 20);
$("#modalIc").innerHTML = icon("upload", 32);
$("#nav").onclick = e => { const b = e.target.closest("button"); if (b) go(b.dataset.id); };

const modal = $("#modal"), toggle = open => modal.classList.toggle("open", open);
$("#newImport").onclick = () => toggle(true);
["closeModal", "cancelModal", "confirmModal"].forEach(id => $("#" + id).onclick = () => toggle(false));
modal.onclick = e => { if (e.target === modal) toggle(false); };
document.addEventListener("keydown", e => e.key === "Escape" && toggle(false));

go("dashboard");
