"""Tipe sumur dari profil inklinasi survey (Rec 07): Vertical / J / S / Horizontal.

Klien 28 Nov: Room dikelompokkan per tipe sumur, otomatis dari survey. Aturan (inklinasi dalam derajat):
  maks < 10°                                   -> Vertical
  maks ≥ 80°                                   -> Horizontal
  inklinasi terdalam ≤ maks − 15° (drop-off)   -> S
  selain itu (build-hold)                      -> J
Sumur yang masih dibor dinilai dari survey sejauh ini: S dalam fase hold atau horizontal dalam fase build masih
terbaca J sampai survey berikutnya masuk."""
from __future__ import annotations

import pandas as pd

TYPES = ("Horizontal", "J", "S", "Vertical")
VERTICAL_MAX = 10.0
HORIZONTAL_MIN = 80.0
DROP_MIN = 15.0


def classify(survey: pd.DataFrame | None) -> str | None:
    if survey is None or "inc" not in survey or "md" not in survey:
        return None
    sv = survey.dropna(subset=["md", "inc"]).sort_values("md")
    if len(sv) < 3:
        return None
    inc = sv["inc"].astype(float)
    mx, last = float(inc.max()), float(inc.iloc[-1])
    if mx < VERTICAL_MAX:
        return "Vertical"
    if mx >= HORIZONTAL_MIN:
        return "Horizontal"
    if last <= mx - DROP_MIN:
        return "S"
    return "J"
