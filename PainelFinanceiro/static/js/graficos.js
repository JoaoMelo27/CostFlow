/* =====================================================================
   Gráficos do painel, desenhados em SVG com JavaScript puro (sem biblioteca).

   Cada função recebe um elemento (container) e os dados JÁ CALCULADOS pelo
   servidor (Python). Aqui só se desenha: nenhuma regra de negócio.

     Graficos.variacoes(el, barras)      barras horizontais do Δ% de cada indicador
     Graficos.realXBudget(el, grupos)    Budget × RF × Real de Custo Total e Custo OPEX
     Graficos.evolucao(el, dados, alt)   linha mês a mês (Budget, RF e Real)
   ===================================================================== */
const Graficos = (() => {
  // Cores: fundo branco, laranja da marca no Real, laranja claro no RF e cinza no Budget.
  const COR_CENARIO = { Budget: "#8C99A8", RF: "#FFB38A", Real: "#FE4F00" };
  const COR_NIVEL = { verde: "#2E7D32", amarelo: "#D9A400", vermelho: "#C62828", preto: "#2B2B2B", cinza: "#98A4B3" };
  const NS = "http://www.w3.org/2000/svg";

  // ------------------------------------------------------------------ utilidades
  /** Número no padrão brasileiro: 1234.5 -> "1.234,5". */
  function numeroBR(valor, decimais) {
    return valor.toLocaleString("pt-BR", { minimumFractionDigits: decimais, maximumFractionDigits: decimais });
  }

  /** Marcas "redondas" de eixo entre min e max (1, 2, 5, 10, 20...). */
  function marcasEixo(min, max, quantidade) {
    if (min === max) { min -= 1; max += 1; }
    const passoBruto = (max - min) / quantidade;
    const potencia = Math.pow(10, Math.floor(Math.log10(passoBruto)));
    const fator = passoBruto / potencia;                       // entre 1 e 10
    const passo = (fator <= 1 ? 1 : fator <= 2 ? 2 : fator <= 5 ? 5 : 10) * potencia;
    const inicio = Math.floor(min / passo) * passo;
    const fim = Math.ceil(max / passo) * passo;
    const marcas = [];
    for (let v = inicio; v <= fim + passo / 2; v += passo) marcas.push(Math.round(v / passo) * passo);
    return marcas;
  }

  /** Cria um elemento SVG com atributos. */
  function el(tag, atributos = {}, pai = null) {
    const no = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(atributos)) no.setAttribute(k, v);
    if (pai) pai.appendChild(no);
    return no;
  }

  function texto(pai, x, y, conteudo, atributos = {}) {
    const t = el("text", { x, y, "font-size": 11, ...atributos }, pai);
    t.textContent = conteudo;
    return t;
  }

  /** Caixinha de dica que aparece ao passar o mouse. */
  function ligarDica(container, alvo, linhas) {
    let dica = container.querySelector(".dica");
    if (!dica) {
      dica = document.createElement("div");
      dica.className = "dica";
      dica.hidden = true;
      container.appendChild(dica);
    }
    alvo.style.cursor = "default";
    alvo.addEventListener("mousemove", (ev) => {
      dica.innerHTML = linhas.map(([rot, val]) => `<b>${escapar(rot)}</b> ${escapar(val)}`).join("<br>");
      const caixa = container.getBoundingClientRect();
      dica.style.left = `${ev.clientX - caixa.left + 12}px`;
      dica.style.top = `${ev.clientY - caixa.top + 12}px`;
      dica.hidden = false;
    });
    alvo.addEventListener("mouseleave", () => { dica.hidden = true; });
  }

  function escapar(s) {
    return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  }

  function novoSvg(container, largura, altura) {
    container.innerHTML = "";
    container.classList.add("grafico");
    return el("svg", { width: largura, height: altura, viewBox: `0 0 ${largura} ${altura}` }, container);
  }

  // ------------------------------------------------------------------ 1) variações (barras horizontais)
  function variacoes(container, barras) {
    if (!barras.length) { container.innerHTML = ""; return; }
    const largura = Math.max(container.clientWidth, 320);
    const larguraRotulos = 190;
    const linha = 26;
    const areaAltura = linha * barras.length;
    const altura = areaAltura + 62;
    const svg = novoSvg(container, largura, altura);

    const valores = barras.map((b) => b.valor);
    const marcas = marcasEixo(Math.min(0, ...valores), Math.max(0, ...valores), 10);
    const xMin = marcas[0], xMax = marcas[marcas.length - 1];
    const x0 = larguraRotulos, x1 = largura - 40;
    const escalaX = (v) => x0 + (v - xMin) / (xMax - xMin) * (x1 - x0);

    // grade vertical e rótulos do eixo
    for (const m of marcas) {
      el("line", { x1: escalaX(m), x2: escalaX(m), y1: 0, y2: areaAltura, class: "grade-linha" }, svg);
      texto(svg, escalaX(m), areaAltura + 16, numeroBR(m, 0), { "text-anchor": "middle" });
    }
    texto(svg, (x0 + x1) / 2, areaAltura + 40, "Variação do Real contra a referência (%)",
          { "text-anchor": "middle", class: "eixo-titulo" });

    barras.forEach((b, i) => {
      const yMeio = i * linha + linha / 2;
      texto(svg, x0 - 10, yMeio + 4, b.indicador, { "text-anchor": "end", fill: "#555" });
      const xa = escalaX(Math.min(0, b.valor)), xb = escalaX(Math.max(0, b.valor));
      const ret = el("rect", { x: xa, y: yMeio - 8, width: Math.max(xb - xa, 0.5), height: 16, fill: COR_NIVEL[b.nivel] }, svg);
      const positivo = b.valor >= 0;
      texto(svg, positivo ? xb + 4 : xa - 4, yMeio + 4, b.rotulo, { "text-anchor": positivo ? "start" : "end" });
      ligarDica(container, ret, [["Indicador", b.indicador], ["Real", b.real], ["Referência", b.referencia], ["Rótulo", b.rotulo]]);
    });
    el("line", { x1: escalaX(0), x2: escalaX(0), y1: 0, y2: areaAltura, stroke: "#8c99a8" }, svg);   // linha do zero
  }

  // ------------------------------------------------------------------ 2) Budget × RF × Real (barras agrupadas)
  function realXBudget(container, grupos) {
    if (!grupos.length) { container.innerHTML = ""; return; }
    const larguraGrupo = 150, espaco = 24, esquerda = 52, topo = 26, alturaArea = 230;
    const largura = esquerda + grupos.length * larguraGrupo + (grupos.length - 1) * espaco + 10;
    const altura = topo + alturaArea + 30;
    const svg = novoSvg(container, largura, altura);

    const maximo = Math.max(...grupos.flatMap((g) => g.barras.map((b) => b.valor)));
    const marcas = marcasEixo(0, maximo, 8);
    const yMax = marcas[marcas.length - 1];
    const escalaY = (v) => topo + alturaArea - v / yMax * alturaArea;

    // eixo Y (um só, à esquerda)
    for (const m of marcas) {
      texto(svg, esquerda - 8, escalaY(m) + 4, numeroBR(m, 0), { "text-anchor": "end" });
    }
    texto(svg, 0, 0, "MBRL", { class: "eixo-titulo", transform: `translate(14 ${topo + alturaArea / 2}) rotate(-90)`, "text-anchor": "middle" });

    grupos.forEach((g, gi) => {
      const xg = esquerda + gi * (larguraGrupo + espaco);
      texto(svg, xg + larguraGrupo / 2, 12, g.indicador, { "text-anchor": "middle" });
      for (const m of marcas) {
        el("line", { x1: xg, x2: xg + larguraGrupo, y1: escalaY(m), y2: escalaY(m), class: "grade-linha" }, svg);
      }
      const faixa = larguraGrupo / g.barras.length;
      g.barras.forEach((b, bi) => {
        const xc = xg + faixa * bi + faixa / 2;
        const ret = el("rect", { x: xc - 17, y: escalaY(b.valor), width: 34, height: escalaY(0) - escalaY(b.valor),
                                 fill: COR_CENARIO[b.cenario] }, svg);
        texto(svg, xc, escalaY(b.valor) - 6, b.rotulo, { "text-anchor": "middle" });
        texto(svg, xc, topo + alturaArea + 18, b.cenario, { "text-anchor": "middle" });
        ligarDica(container, ret, [["Indicador", g.indicador], ["Cenário", b.cenario], ["Rótulo", b.rotulo]]);
      });
    });
  }

  // ------------------------------------------------------------------ 3) evolução mensal (linhas)
  function evolucao(container, dados, altura = 240) {
    if (!dados) { container.innerHTML = ""; return; }
    const largura = Math.max(container.clientWidth, 260);
    const esquerda = 58, direita = 12, topo = 8;
    const giraRotulos = dados.periodos.length > 8;
    const baseEixo = giraRotulos ? 46 : 26;
    const alturaArea = altura - baseEixo - 26;
    const svg = novoSvg(container, largura, altura + 10);

    const todos = dados.series.flatMap((s) => s.valores.filter((v) => v !== null));
    const marcas = marcasEixo(Math.min(...todos), Math.max(...todos), 6);
    const yMin = marcas[0], yMax = marcas[marcas.length - 1];
    const escalaY = (v) => topo + alturaArea - (v - yMin) / (yMax - yMin) * alturaArea;
    const n = dados.periodos.length;
    const passoX = (largura - esquerda - direita) / Math.max(n, 1);
    const escalaX = (i) => esquerda + passoX * (i + 0.5);

    for (const m of marcas) {
      el("line", { x1: esquerda, x2: largura - direita, y1: escalaY(m), y2: escalaY(m), class: "grade-linha" }, svg);
      texto(svg, esquerda - 6, escalaY(m) + 4, numeroBR(m, dados.decimais_eixo), { "text-anchor": "end" });
    }
    texto(svg, 0, 0, dados.unidade, { class: "eixo-titulo", transform: `translate(12 ${topo + alturaArea / 2}) rotate(-90)`, "text-anchor": "middle" });
    dados.periodos.forEach((p, i) => {
      const y = topo + alturaArea + 16;
      if (giraRotulos) texto(svg, escalaX(i), y, p, { "text-anchor": "end", transform: `rotate(-45 ${escalaX(i)} ${y})` });
      else texto(svg, escalaX(i), y, p, { "text-anchor": "middle" });
    });

    for (const s of dados.series) {
      const cor = COR_CENARIO[s.cenario];
      const espessura = s.cenario === "Real" ? 3 : 1.6;
      let caminho = "", novoTrecho = true;
      s.valores.forEach((v, i) => {
        if (v === null) { novoTrecho = true; return; }
        caminho += `${novoTrecho ? "M" : "L"}${escalaX(i)},${escalaY(v)} `;
        novoTrecho = false;
      });
      el("path", { d: caminho, fill: "none", stroke: cor, "stroke-width": espessura, "stroke-linejoin": "round" }, svg);
      s.valores.forEach((v, i) => {
        if (v === null) return;
        const ponto = el("circle", { cx: escalaX(i), cy: escalaY(v), r: 3.8, fill: cor }, svg);
        ligarDica(container, ponto, [["Período", dados.periodos[i]], ["Cenário", s.cenario], ["Rótulo", s.rotulos[i]]]);
      });
    }

    // legenda embaixo: traço colorido + nome do cenário
    let xl = esquerda + 4;
    const yl = altura + 2;
    for (const s of dados.series) {
      el("line", { x1: xl, x2: xl + 14, y1: yl - 4, y2: yl - 4, stroke: COR_CENARIO[s.cenario], "stroke-width": 2.5 }, svg);
      texto(svg, xl + 19, yl, s.cenario);
      xl += 19 + s.cenario.length * 7 + 18;
    }
  }

  return { variacoes, realXBudget, evolucao, numeroBR };
})();
