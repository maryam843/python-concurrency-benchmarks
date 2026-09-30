"""Generate the small synthetic fixture files used by the tests and CI (no real data is committed).

    python tools/make_fixtures.py

- tests/fixtures/air_quality_tiny.csv: 300 hourly rows in the exact UCI Air Quality format
  (semicolon separator, decimal comma, -200 = missing, trailing empty rows).
"""

from __future__ import annotations

import math
import random
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
AQ_HEADER = "Date;Time;CO(GT);PT08.S1(CO);NMHC(GT);C6H6(GT);PT08.S2(NMHC);NOx(GT);PT08.S3(NOx);NO2(GT);" \
            "PT08.S4(NO2);PT08.S5(O3);T;RH;AH;;"


def _comma(x: float, nd: int = 1) -> str:
    return f"{x:.{nd}f}".replace(".", ",")


def make_air_quality(path: Path = FIXTURES / "air_quality_tiny.csv", rows: int = 300, seed: int = 360) -> Path:
    rng = random.Random(seed)
    lines = [AQ_HEADER]
    for h in range(rows):
        day, hour = divmod(h + 18, 24)
        date = f"{10 + day:02d}/03/2004"
        t = 12 + 6 * math.sin((hour - 9) / 24 * 2 * math.pi) + rng.uniform(-1.5, 1.5)
        t_txt = "-200" if rng.random() < 0.06 else _comma(t)
        rh = _comma(rng.uniform(30, 70))
        vals = ["-200" if rng.random() < 0.05 else _comma(rng.uniform(0.5, 4)), str(rng.randint(900, 1500)),
                "-200", _comma(rng.uniform(2, 20)), str(rng.randint(700, 1200)), str(rng.randint(50, 300)),
                str(rng.randint(800, 1300)), str(rng.randint(40, 150)), str(rng.randint(1200, 1900)),
                str(rng.randint(700, 1400)), t_txt, rh, _comma(rng.uniform(0.5, 1.2), 4)]
        lines.append(";".join([date, f"{hour:02d}.00.00", *vals]) + ";;")
    lines += [";" * 16, ";" * 16]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(make_air_quality())
