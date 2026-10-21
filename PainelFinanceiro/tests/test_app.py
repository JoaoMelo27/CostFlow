"""
Servidor Flask de ponta a ponta, sem navegador:
Atualizar -> conferir prévia -> Confirmar -> Painel / Insights / Histórico / Sobre / exportações.
"""
import importlib
import os
import shutil
import tempfile
import unittest

import tests  # noqa: F401
from planilhas_ficticias import gerar_planilhas


def novo_app(pasta_entrada, somente_leitura=False):
    """Carrega o app.py com um banco e uma pasta de entrada próprios do teste."""
    tmp = tempfile.mkdtemp()
    os.environ["PAINEL_DB"] = os.path.join(tmp, "painel.db")
    os.environ["PAINEL_PASTA"] = pasta_entrada
    os.environ["PAINEL_SOMENTE_LEITURA"] = "1" if somente_leitura else "0"
    import app
    app = importlib.reload(app)
    app.app.testing = True
    return app.app.test_client()


class TestFluxoCompleto(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entrada = tempfile.mkdtemp()
        cls.julho = tempfile.mkdtemp()
        gerar_planilhas(cls.entrada, 8)
        gerar_planilhas(cls.julho, 7)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.entrada, ignore_errors=True)
        shutil.rmtree(cls.julho, ignore_errors=True)

    def test_fluxo(self):
        c = novo_app(self.entrada)
        self.assertEqual(c.get("/").status_code, 200)
        self.assertEqual(c.get("/api/estado").get_json()["periodos"], [])

        # 1) Atualizar: lê e valida, mas não grava
        previa = c.post("/api/atualizar", json={}).get_json()
        self.assertEqual(previa["periodo"], "Agosto/2026")
        self.assertFalse(previa["tem_erro"])
        self.assertEqual(len(previa["previa"]), 27)
        self.assertEqual(c.get("/api/estado").get_json()["periodos"], [])

        # 2) Confirmar grava
        r = c.post("/api/confirmar", json={"token": previa["token"]}).get_json()
        self.assertIn("Agosto/2026 gravado: 81 valores", r["mensagem"])
        self.assertEqual(c.post("/api/confirmar", json={"token": previa["token"]}).status_code, 409)   # token usado

        # 3) Painel: 10 cartões, Investimento pendente
        p = c.get("/api/painel?ano=2026&mes=8").get_json()
        self.assertEqual(p["titulo"], "AGOSTO/2026")
        cartoes = p["custos"] + p["financeiros"]
        self.assertEqual(len(cartoes), 10)
        self.assertTrue(next(x for x in cartoes if x["codigo"] == "investimento_kbrl")["pendente"])
        self.assertEqual(sum(1 for x in cartoes if x["farol"]), 3)

        # 4) Investimento manual
        valores = {v: {cen: "1.000" for cen in ("budget", "rf", "real")} for v in ("month", "ytd", "fy")}
        valores["month"]["real"] = "abc"
        self.assertEqual(c.post("/api/investimento", json={"ano": 2026, "mes": 8, "valores": valores}).status_code, 400)
        valores["month"]["real"] = "1.000"
        self.assertIn("salvo", c.post("/api/investimento", json={"ano": 2026, "mes": 8, "valores": valores}).get_json()["mensagem"])
        p = c.get("/api/painel?ano=2026&mes=8").get_json()
        self.assertFalse(next(x for x in p["custos"] if x["codigo"] == "investimento_kbrl")["pendente"])

        # 5) Segundo mês, insights, comentários, histórico e sobre
        previa = c.post("/api/atualizar", json={"pasta": self.julho}).get_json()
        c.post("/api/confirmar", json={"token": previa["token"]})
        self.assertEqual(c.get("/api/estado").get_json()["periodos"], [[2026, 7], [2026, 8]])
        for visao in ("month", "ytd", "fy"):
            ins = c.get(f"/api/insights?ano=2026&mes=8&visao={visao}").get_json()
            self.assertTrue(ins["secoes"] and ins["variacoes"] and ins["quadro"])
        self.assertEqual(c.post("/api/comentarios", json={"ano": 2026, "mes": 8, "autor": "", "texto": "x"}).status_code, 400)
        c.post("/api/comentarios", json={"ano": 2026, "mes": 8, "autor": "Ana", "indicador": "ocf_kusd", "texto": "Teste"})
        self.assertEqual(c.get("/api/insights?ano=2026&mes=8&visao=month").get_json()["comentarios"][0]["sobre"], "OCF KUSD")
        h = c.get("/api/historico?anos=2026&indicador=ocf_kusd&visao=ytd").get_json()
        self.assertTrue(h["unico"] and h["grafico"] and len(h["linhas"]) == 2)
        h = c.get("/api/historico?anos=2026&indicador=todos&visao=month&ordem=recentes").get_json()
        self.assertEqual(h["linhas"][0]["grupo"], "Agosto/2026")
        self.assertEqual(len(c.get("/api/sobre?ano=2026&mes=8").get_json()["rastreabilidade"]), 10)

        # 6) Exportações
        self.assertTrue(c.get("/exportar/painel.pdf?ano=2026&mes=8").data.startswith(b"%PDF"))
        self.assertTrue(c.get("/exportar/painel.csv?ano=2026&mes=8").data.startswith(b"\xef\xbb\xbf"))
        self.assertIn("historico", c.get("/exportar/historico.csv?anos=2026&indicador=todos&visao=fy").headers["Content-Disposition"])

        # 7) Período inexistente e pasta vazia dão erro claro, sem gravar nada
        self.assertEqual(c.get("/api/painel?ano=2020&mes=1").status_code, 404)
        r = c.post("/api/atualizar", json={"pasta": tempfile.mkdtemp()})
        self.assertEqual(r.status_code, 422)
        self.assertIn("não encontrado", r.get_json()["erro"])
        self.assertEqual(len(c.get("/api/estado").get_json()["periodos"]), 2)

    def test_somente_leitura_bloqueia_gravacao(self):
        c = novo_app(self.entrada, somente_leitura=True)
        self.assertTrue(c.get("/api/estado").get_json()["somente_leitura"])
        self.assertEqual(c.post("/api/atualizar", json={}).status_code, 403)
        self.assertEqual(c.post("/api/investimento", json={"ano": 2026, "mes": 8, "valores": {}}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
