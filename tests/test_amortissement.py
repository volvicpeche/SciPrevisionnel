import os
import sys
import pandas as pd
import pytest

# Ensure the module can be imported when tests run from subdirectories
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from SciPrevisionnel import calculer_tableau_amortissement


def test_capital_amortissement_sum_and_remaining_zero():
    montant = 1000
    taux = 0.05
    duree = 1
    df = calculer_tableau_amortissement(montant, taux, duree)
    assert pytest.approx(df['Capital'].sum()) == montant
    assert df['Capital Restant'].iloc[-1] == pytest.approx(0)

