import pandas as pd

from app.core.welltype import classify


def sv(inc):
    return pd.DataFrame({"md": [i * 100.0 for i in range(len(inc))], "inc": inc})


def test_types():
    assert classify(sv([0, 1, 2, 3])) == "Vertical"
    assert classify(sv([0, 10, 30, 30, 31])) == "J"
    assert classify(sv([0, 20, 40, 40, 20, 5])) == "S"
    assert classify(sv([0, 30, 60, 88, 90])) == "Horizontal"
    assert classify(sv([0, 5])) is None and classify(None) is None
