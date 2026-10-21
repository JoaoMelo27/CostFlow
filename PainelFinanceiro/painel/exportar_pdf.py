"""
Painel em PDF para impressão: uma página A4 paisagem com os 10 cartões, no mesmo desenho da tela.

Gerado com reportlab (Python puro: funciona em qualquer computador sem navegador nem Office).
A fonte DejaVu Sans fica em painel/fontes para que Δ e ≤ saiam corretos em qualquer máquina.
Os números vêm da mesma função de Δ% e da mesma regra de cor dos cartões da tela.
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from typing import Dict

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from . import formatacao as fmt
from .config import (CARTOES_CUSTOS, CARTOES_FINANCEIROS, DELTA_SOBRE_VALOR_ARREDONDADO, MESES_PT, POR_CODIGO,
                     VISAO_LABEL, VISOES, cor_do_delta, delta_indicador)

AQUI = os.path.dirname(os.path.abspath(__file__))
_FONTES = os.path.join(AQUI, "fontes")
_LOGO = os.path.join(AQUI, "..", "static", "img", "nexa_logo.png")   # o mesmo logo usado na tela

LARANJA, LARANJA_ESCURO, LARANJA_CLARO, FAIXA = "#FE4F00", "#A33300", "#FFEEE4", "#D94300"
CINZA, BORDA, TEXTO = "#666666", "#E3DBD5", "#2B2B2B"
COR_PONTO = {"verde": "#2E7D32", "vermelho": "#C62828", "amarelo": "#C98A00", "preto": "#2B2B2B", "cinza": "#98A4B3"}

ESQ = CARTOES_CUSTOS          # mesma ordem dos cartões da tela
DIR = CARTOES_FINANCEIROS

# legenda de cada regra de cor: lista de (cor do ponto, texto)
LEGENDA = {
    "custo": [("vermelho", "Δ > 0%"), ("verde", "Δ ≤ 0%")],
    "invest": [("vermelho", "Δ < -5% ou > +5%"), ("verde", "entre -5% e +5%")],
    "beneficio": [("verde", "Δ > 0%"), ("vermelho", "Δ ≤ 0%")],
    "cashcost": [("vermelho", "Meta 100"), ("amarelo", "Meta 300"), ("verde", "Meta 500"), ("preto", "Meta 0")],
}

_registradas = False


def _fontes():
    global _registradas
    if not _registradas:
        pdfmetrics.registerFont(TTFont("Painel", os.path.join(_FONTES, "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("Painel-Bold", os.path.join(_FONTES, "DejaVuSans-Bold.ttf")))
        _registradas = True


def _cor(c, hexa):
    c.setFillColor(hexa)
    c.setStrokeColor(hexa)


def _card(c, ind, painel, x, y_topo, w, h, fs, fv):
    """Desenha um cartão com o canto superior esquerdo em (x, y_topo)."""
    y = y_topo - h
    c.setFillColor("#FFFFFF"); c.setStrokeColor(BORDA); c.setLineWidth(0.6)
    c.roundRect(x, y, w, h, 3, fill=1, stroke=1)
    c.setFillColor(LARANJA); c.rect(x + 0.3, y_topo - 2.4, w - 0.6, 2.4, fill=1, stroke=0)

    pad = 7
    ty = y_topo - 16
    c.setFillColor(LARANJA_ESCURO); c.setFont("Painel-Bold", fs)
    c.drawString(x + pad, ty, ind.nome)

    # legenda (pontos + texto); indicador manual sem dado mostra o aviso
    ly = ty - 12
    sem_dado = ind.manual and not any(painel.get(ind.codigo, {}).get(v) for v in VISOES)
    c.setFont("Painel", 6.6)
    if sem_dado:
        c.setFillColor("#C98A00"); c.drawString(x + pad, ly, "Pendente: preencher manualmente no painel")
    else:
        farol = ind.cor == "cashcost"          # legenda dos faróis: negrito e bolinhas maiores, como na empresa
        fonte_leg, raio = ("Painel-Bold", 2.7) if farol else ("Painel", 2.0)
        itens = LEGENDA[ind.cor]
        c.setFont(fonte_leg, 6.6)
        if farol:
            # o cartão do PDF é estreito: os 4 faróis ficam em 2 linhas de 2, na mesma ordem de leitura (100, 300 / 500, 0)
            colw = (w - 2 * pad) / 2
            for i, (cor, txt) in enumerate(itens):
                r_, k_ = divmod(i, 2)
                px, py = x + pad + k_ * colw, ly - r_ * 9
                c.setFillColor(COR_PONTO[cor]); c.circle(px + raio, py + 2.2, raio, fill=1, stroke=0)
                c.setFillColor(TEXTO); c.drawString(px + raio * 2 + 3, py, txt)
        else:
            lx = x + pad
            for cor, txt in itens:
                c.setFillColor(COR_PONTO[cor]); c.circle(lx + raio, ly + 2.2, raio, fill=1, stroke=0)
                c.setFillColor(CINZA); c.drawString(lx + raio * 2 + 3, ly, txt)
                lx += raio * 2 + 3 + pdfmetrics.stringWidth(txt, fonte_leg, 6.6) + 8

    # três blocos (Month / YTD / FY)
    ref_lbl = "ΔBud" if ind.delta_ref == "budget" else "ΔRF"
    larguras = [0.24, 0.24, 0.26, 0.26]
    inner = w - 2 * pad
    colx = [x + pad]
    for f in larguras:
        colx.append(colx[-1] + inner * f)
    th, td = 13.5, 21
    gap_label = max(8, min(24, (h - 49 - 8 - 3 * (4 + th + td + 6.8)) / 2))   # distribui a altura que sobra
    yy = ly - 21
    for visao in VISOES:
        d = painel.get(ind.codigo, {}).get(visao, {})
        delta = delta_indicador(ind, d.get("real"), d.get(ind.delta_ref))
        c.setFillColor(CINZA); c.setFont("Painel-Bold", 6.8)
        c.drawString(x + pad, yy, VISAO_LABEL[visao].upper())
        yy -= 4
        # cabeçalho
        c.setFillColor(LARANJA_CLARO); c.setStrokeColor(BORDA); c.setLineWidth(0.4)
        c.rect(x + pad, yy - th, inner, th, fill=1, stroke=1)
        c.setFillColor(LARANJA_ESCURO); c.setFont("Painel-Bold", 7)
        for i, rot in enumerate(("Budget", "RF", "Real", ref_lbl)):
            c.drawCentredString((colx[i] + colx[i + 1]) / 2, yy - th + 4.3, rot)
        yy -= th
        # valores
        c.setFillColor("#FFFFFF"); c.rect(x + pad, yy - td, inner, td, fill=1, stroke=1)
        c.setFillColor(LARANJA_CLARO); c.rect(colx[2], yy - td, colx[3] - colx[2], td, fill=1, stroke=1)
        for i in range(1, 4):
            c.line(colx[i], yy, colx[i], yy - td)
        base = yy - td + 7
        vals = [fmt.valor_indicador(d.get(k), ind.unidade, ind.decimais) for k in ("budget", "rf", "real")]
        for i, v in enumerate(vals):
            c.setFillColor(LARANJA_ESCURO if i == 2 else TEXTO)
            c.setFont("Painel-Bold" if i == 2 else "Painel", fv)
            c.drawCentredString((colx[i] + colx[i + 1]) / 2, base, v)
        txt = fmt.pct(delta)
        c.setFillColor(TEXTO); c.setFont("Painel", fv)
        cx = (colx[3] + colx[4]) / 2
        tw = pdfmetrics.stringWidth(txt, "Painel", fv)
        c.drawString(cx - (tw + 8) / 2, base, txt)
        c.setFillColor(COR_PONTO[cor_do_delta(ind.cor, delta)])
        c.circle(cx - (tw + 8) / 2 + tw + 5, base + 3, 2.3, fill=1, stroke=0)
        yy -= td + gap_label


def painel_pdf(ano: int, mes: int, painel: Dict[str, Dict[str, Dict[str, float]]]) -> bytes:
    """PDF (bytes) do painel de um período, A4 paisagem, pronto para imprimir."""
    _fontes()
    buf = io.BytesIO()
    pw, ph = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(pw, ph))
    c.setTitle(f"Painel Financeiro — {MESES_PT[mes - 1]}/{ano} — Unidade Vazante")
    c.setAuthor("Nexa — Performance & Facilities")

    m = 24
    # cabeçalho
    topo = ph - m
    c.setFillColor(LARANJA_ESCURO); c.setFont("Painel-Bold", 17)
    titulo = "PAINEL FINANCEIRO"
    c.drawString(m, topo - 15, titulo)
    tw = pdfmetrics.stringWidth(titulo, "Painel-Bold", 17)
    c.setFillColor(LARANJA); c.drawString(m + tw + 6, topo - 15, "|")
    c.setFillColor(LARANJA_ESCURO); c.drawString(m + tw + 18, topo - 15, f"{MESES_PT[mes - 1].upper()}/{ano}")
    tw2 = pdfmetrics.stringWidth(f"{MESES_PT[mes - 1].upper()}/{ano}", "Painel-Bold", 17)
    c.setFillColor(CINZA); c.setFont("Painel", 9)
    c.drawString(m + tw + 18 + tw2 + 10, topo - 14.5, "Unidade Vazante")
    if os.path.exists(_LOGO):
        from reportlab.lib.utils import ImageReader
        img = ImageReader(_LOGO)
        iw, ih = img.getSize()
        lh = 26
        c.drawImage(img, pw - m - lh * iw / ih, topo - lh + 2, width=lh * iw / ih, height=lh, mask="auto")
    c.setStrokeColor(LARANJA); c.setLineWidth(2)
    c.line(m, topo - 27, pw - m, topo - 27)

    # grupos
    gap = 12
    util = pw - 2 * m - gap
    w_esq, w_dir = util * 0.6, util * 0.4
    x_esq, x_dir = m, m + w_esq + gap
    y_grupo = topo - 36
    for x, w, rot in ((x_esq, w_esq, "KPIs Custos"), (x_dir, w_dir, "KPI's Financeiros")):
        c.setFillColor(FAIXA); c.roundRect(x, y_grupo - 15, w, 15, 2.5, fill=1, stroke=0)
        c.setFillColor("#FFFFFF"); c.setFont("Painel-Bold", 8); c.drawString(x + 8, y_grupo - 10.5, rot)

    # tamanhos de fonte uniformes: o maior que cabe no pior caso (título mais longo / número mais largo)
    pad = 7
    cw_min = min((w_esq - 16) / 3, (w_dir - 8) / 2)
    fs = 10.0
    while max(pdfmetrics.stringWidth(POR_CODIGO[k].nome, "Painel-Bold", fs) for k in ESQ + DIR) > cw_min - 2 * pad and fs > 6.5:
        fs -= 0.1
    fv = 8.6
    inner = cw_min - 2 * pad
    while fv > 6.0:
        pior = 0.0
        for k in ESQ + DIR:
            ind = POR_CODIGO[k]
            for visao in VISOES:
                d = painel.get(k, {}).get(visao, {})
                for ch in ("budget", "rf"):
                    pior = max(pior, pdfmetrics.stringWidth(fmt.valor_indicador(d.get(ch), ind.unidade, ind.decimais), "Painel", fv) / 0.24)
                pior = max(pior, pdfmetrics.stringWidth(fmt.valor_indicador(d.get("real"), ind.unidade, ind.decimais), "Painel-Bold", fv) / 0.26)
                dl = fmt.pct(delta_indicador(ind, d.get("real"), d.get(ind.delta_ref)))
                pior = max(pior, (pdfmetrics.stringWidth(dl, "Painel", fv) + 9) / 0.26)
        if pior + 6 <= inner:
            break
        fv -= 0.1

    rodape = 30
    y0 = y_grupo - 15 - 8
    altura_util = y0 - m - rodape
    gcard = 8
    h = (altura_util - gcard) / 2
    for blocos, x, w, cols in ((ESQ, x_esq, w_esq, 3), (DIR, x_dir, w_dir, 2)):
        cw = (w - gcard * (cols - 1)) / cols
        for i, cod in enumerate(blocos):
            r, k = divmod(i, cols)
            _card(c, POR_CODIGO[cod], painel, x + k * (cw + gcard), y0 - r * (h + gcard), cw, h, fs, fv)

    # rodapé
    pendente = not any(painel.get("investimento_kbrl", {}).get(v) for v in VISOES)
    c.setFillColor(CINZA); c.setFont("Painel", 6.3)
    notas = [
        ("Δ% calculado sobre os valores arredondados exibidos, como no painel de referência."
         if DELTA_SOBRE_VALOR_ARREDONDADO else "Δ% calculado sobre os valores exatos.")
        + " Δ contra Budget nos custos e cash cost; contra RF nos financeiros e no investimento."
    ]
    if pendente:
        notas.append("Investimento (Capex/Opex/Oro): ainda não preenchido para este mês.")
    for i, n in enumerate(notas):
        c.drawString(m, m + 14 - i * 8.5, n)
    c.drawRightString(pw - m, m + 5, f"Gerado em {datetime.now():%d/%m/%Y %H:%M}")
    c.showPage()
    c.save()
    return buf.getvalue()
