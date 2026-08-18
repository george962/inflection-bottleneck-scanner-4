import pandas as pd

from inflection_scanner.features.fundamentals import fundamental_features


def test_fundamental_features_margin_change():
    cols=["q0","q1","q2","q3","q4"]
    income=pd.DataFrame([[120,110,105,100,100],[24,20,18,16,10],[60,55,52,50,45]],index=["Total Revenue","Operating Income","Gross Profit"],columns=cols)
    cash=pd.DataFrame([[18,17,16,15,10]],index=["Free Cash Flow"],columns=cols)
    out=fundamental_features({"income":income,"cashflow":cash,"balance":pd.DataFrame()})
    assert round(out["revenue_yoy"],2)==.2
    assert out["operating_margin_change_yoy"]>0
