"""Histórico (sem duplicar, auditoria), Investimento manual, CSV, insights e PDF."""
import csv
import io
import os
import tempfile
import unittest

import tests  # noqa: F401
import modelo_ficticio as mf
from painel import banco, exportar_csv, exportar_pdf
from painel.config import INDICADORES, POR_CODIGO
from painel.insights import gerar_insights


def registros(painel):
    """Painel {indicador: {visao: {cenario: valor}}} -> linhas para o banco."""
    return [(c, cen, v, val, POR_CODIGO[c].unidade)
            for c, pv in painel.items() for v, d in pv.items() for cen, val in d.items()]


def automaticos(mes):
    return registros(mf.valores_esperados(mes))


class TestHistorico(unittest.TestCase):
    def setUp(self):
        self.conn = banco.connect(os.path.join(tempfile.mkdtemp(), "t.db"))
        for mes in (6, 7, 8):
            banco.gravar_periodo(self.conn, 2026, mes, automaticos(mes), ["a", "b", "c"])

    def tearDown(self):
        self.conn.close()

    def contar(self, tabela):
        return self.conn.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]

    def test_acumula_sem_duplicar(self):
        self.assertEqual(self.contar("fato_indicador"), 3 * 81)
        out = banco.gravar_periodo(self.conn, 2026, 8, automaticos(8), ["a", "b", "c"])   # reprocessa igual
        self.assertEqual(out["alterados"], 0)
        self.assertEqual(self.contar("fato_indicador"), 3 * 81)
        self.assertEqual(banco.periodos_disponiveis(self.conn), [(2026, 6), (2026, 7), (2026, 8)])

    def test_correcao_vai_para_auditoria(self):
        novos = [(c, cen, v, val + (100 if (c, cen, v) == ("ocf_kusd", "real", "month") else 0), u)
                 for c, cen, v, val, u in automaticos(8)]
        out = banco.gravar_periodo(self.conn, 2026, 8, novos, ["a", "b", "c"])
        self.assertEqual(out["alterados"], 1)
        self.assertEqual(self.contar("fato_auditoria"), 1)
        self.assertEqual(self.contar("fato_indicador"), 3 * 81)
        resumo = banco.resumo_processamentos(self.conn)
        self.assertEqual(len(resumo), 3)
        self.assertEqual(resumo[-1]["vezes"], 2)

    def test_investimento_manual(self):
        with self.assertRaises(ValueError):            # mês ainda não processado
            banco.gravar_manual(self.conn, 2026, 9, "investimento_kbrl", "KBRL", {"month": {"budget": 1.0}})
        inv = mf.investimento_do_fechamento(8)
        self.assertEqual(banco.gravar_manual(self.conn, 2026, 8, "investimento_kbrl", "KBRL", inv), 0)
        banco.gravar_periodo(self.conn, 2026, 8, automaticos(8), ["a2", "b2", "c2"])     # reprocessa as planilhas
        self.assertEqual(banco.carregar_painel(self.conn, 2026, 8)["investimento_kbrl"],
                         {v: {c: float(x) for c, x in d.items()} for v, d in inv.items()},
                         "reprocessar apagou o investimento manual")
        inv["month"]["real"] += 1
        self.assertEqual(banco.gravar_manual(self.conn, 2026, 8, "investimento_kbrl", "KBRL", inv), 1)
        self.assertIsNotNone(banco.ultima_gravacao(self.conn, 2026, 8, "investimento_kbrl"))


class TestExportacoesEInsights(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        conn = banco.connect(os.path.join(tempfile.mkdtemp(), "t.db"))
        for mes in range(1, 9):
            banco.gravar_periodo(conn, 2026, mes, automaticos(mes), ["a", "b", "c"])
            banco.gravar_manual(conn, 2026, mes, "investimento_kbrl", "KBRL", mf.investimento_do_fechamento(mes))
        cls.hist = banco.carregar_todos(conn)
        conn.close()

    def test_csv_para_excel_ptbr(self):
        dados = exportar_csv.csv_painel(2026, 8, self.hist[(2026, 8)])
        self.assertTrue(dados.startswith(b"\xef\xbb\xbf"), "falta BOM UTF-8")
        self.assertIn(b"\r\n", dados)
        linhas = list(csv.reader(io.StringIO(dados.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(linhas[0], exportar_csv.CABECALHO)
        self.assertEqual(len(linhas), 1 + len(INDICADORES) * 3)
        self.assertTrue(all(len(l) == len(exportar_csv.CABECALHO) for l in linhas))
        self.assertTrue(all("." not in c for l in linhas[1:] for c in l[5:]), "ponto decimal/milhar no CSV")

    def test_csv_historico_respeita_filtros(self):
        h = exportar_csv.csv_historico(self.hist, anos=[2026], indicadores=["ocf_kusd", "nsr"], visoes=["ytd"])
        linhas = list(csv.reader(io.StringIO(h.decode("utf-8-sig")), delimiter=";"))[1:]
        self.assertEqual(len(linhas), 8 * 2)
        self.assertEqual({l[4] for l in linhas}, {"YTD"})
        self.assertEqual([int(l[1]) for l in linhas], sorted(int(l[1]) for l in linhas))   # ordem cronológica

    def test_insights_deterministicos_e_sem_causa(self):
        s1 = gerar_insights(2026, 8, self.hist[(2026, 8)], self.hist)
        s2 = gerar_insights(2026, 8, self.hist[(2026, 8)], self.hist)
        self.assertEqual({k: [(i.texto, i.nivel) for i in v] for k, v in s1.items()},
                         {k: [(i.texto, i.nivel) for i in v] for k, v in s2.items()})
        texto = " ".join(i.texto for v in s1.values() for i in v).lower()
        for proibida in ("devido a", "por causa", "motivado", "em razão"):
            self.assertNotIn(proibida, texto)
        self.assertIn("Evolução frente a períodos anteriores", s1)
        so_um = gerar_insights(2026, 1, self.hist[(2026, 1)], {(2026, 1): self.hist[(2026, 1)]})
        self.assertIn("apenas 1 mês", so_um["Tendências"][0].texto)

    def test_pdf(self):
        sem_investimento = {k: v for k, v in self.hist[(2026, 8)].items() if k != "investimento_kbrl"}
        for painel in (self.hist[(2026, 8)], sem_investimento):
            pdf = exportar_pdf.painel_pdf(2026, 8, painel)
            self.assertTrue(pdf.startswith(b"%PDF"))
            self.assertGreater(len(pdf), 20000)


if __name__ == "__main__":
    unittest.main()
