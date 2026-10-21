"""Regras de negócio puras: Δ%, cores, faróis do Cash Cost e formatação brasileira."""
import unittest

import tests  # noqa: F401  (ajusta o caminho de importação)
from painel import config
from painel import formatacao as fmt
from painel.config import INDICADORES, POR_CODIGO, cor_do_delta, delta_indicador, farol_cash_cost, severidade


class TestFaroisCashCost(unittest.TestCase):
    # (Δ, farol esperado): fronteiras em -2%, 0% e +4%
    CASOS = [(None, "cinza"), (-0.30, "verde"), (-0.02, "verde"), (-0.0199, "amarelo"), (-0.0001, "amarelo"),
             (0.0, "amarelo"), (0.0001, "vermelho"), (0.04, "vermelho"), (0.0401, "preto"), (0.25, "preto")]

    def test_fronteiras(self):
        for delta, esperado in self.CASOS:
            self.assertEqual(farol_cash_cost(delta), esperado, delta)

    def test_mesmo_farol_em_cartao_tabela_e_grafico(self):
        cash = [i for i in INDICADORES if i.cor == "cashcost"]
        self.assertEqual([i.codigo for i in cash], ["cash_cost_total_usdt", "cash_cost_opex_usdt", "cash_cost_ga_rt"])
        for ind in cash:
            for delta, esperado in self.CASOS:
                self.assertEqual(cor_do_delta(ind.cor, delta), esperado)
                self.assertEqual(severidade(ind, delta), esperado)

    def test_sem_orcamento_fica_indisponivel(self):
        ind = POR_CODIGO["cash_cost_total_usdt"]
        self.assertIsNone(delta_indicador(ind, 90.0, 0.0))
        self.assertIsNone(delta_indicador(ind, 90.0, None))
        self.assertEqual(cor_do_delta("cashcost", None), "cinza")


class TestCoresDosOutrosCartoes(unittest.TestCase):
    def test_regras(self):
        self.assertEqual(cor_do_delta("custo", 0.001), "vermelho")
        self.assertEqual(cor_do_delta("custo", -0.5), "verde")
        self.assertEqual(cor_do_delta("invest", 0.051), "vermelho")
        self.assertEqual(cor_do_delta("invest", 0.05), "verde")
        self.assertEqual(cor_do_delta("beneficio", 0.001), "verde")
        self.assertEqual(cor_do_delta("beneficio", 0), "vermelho")


class TestDelta(unittest.TestCase):
    def test_delta_sobre_valor_arredondado(self):
        ind = POR_CODIGO["custo_opex_mbrl"]          # 1 casa decimal
        self.assertTrue(config.DELTA_SOBRE_VALOR_ARREDONDADO)
        # exibidos: 10,5 e 10,0 -> +5,0% (com todas as casas daria +4,2%)
        self.assertAlmostEqual(delta_indicador(ind, 10.46, 10.04), 10.5 / 10.0 - 1)


class TestFormatacao(unittest.TestCase):
    def test_numeros(self):
        self.assertEqual(fmt.num(1234.5, 1), "1.234,5")
        self.assertEqual(fmt.num(None), "—")
        self.assertEqual(fmt.pct(0.084), "+8,4%")
        self.assertEqual(fmt.pct(-0.1), "-10,0%")
        self.assertEqual(fmt.valor_indicador(44.71, "%", 1), "44,7%")

    def test_leitura_de_numero_digitado(self):
        self.assertEqual(fmt.parse_ptbr("21.500"), 21500)
        self.assertEqual(fmt.parse_ptbr("1.234,5"), 1234.5)
        self.assertEqual(fmt.parse_ptbr("-0,5"), -0.5)
        self.assertEqual(fmt.parse_ptbr("12.5"), 12.5)          # ponto sem grupos de 3 = decimal
        with self.assertRaises(ValueError):
            fmt.parse_ptbr("abc")
        with self.assertRaises(ValueError):
            fmt.parse_ptbr("")


class TestIndicadores(unittest.TestCase):
    def test_dez_indicadores_um_manual(self):
        self.assertEqual(len(INDICADORES), 10)
        self.assertEqual([i.codigo for i in config.MANUAIS], ["investimento_kbrl"])
        self.assertEqual(POR_CODIGO["investimento_kbrl"].nome, "Investimento (Capex/Opex/Oro) KBRL")
        self.assertEqual(set(config.CARTOES_CUSTOS + config.CARTOES_FINANCEIROS), set(POR_CODIGO))


if __name__ == "__main__":
    unittest.main()
