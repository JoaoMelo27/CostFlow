"""Testes do Painel Financeiro. Rodar todos:  python -m unittest discover -s tests -v"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "exemplos"))
