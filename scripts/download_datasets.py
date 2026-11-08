"""Download the three Week-1 public datasets into data/raw/.

Source: https://github.com/mwaskom/seaborn-data
Check each dataset's terms before redistributing; data/ is git-ignored on purpose.
"""

from pathlib import Path
from urllib.request import urlretrieve

BASE = "https://raw.githubusercontent.com/mwaskom/seaborn-data/master/{}.csv"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

if __name__ == "__main__":
    RAW.mkdir(parents=True, exist_ok=True)
    for name in ("tips", "penguins", "titanic"):
        urlretrieve(BASE.format(name), RAW / f"{name}.csv")
        print("downloaded", name)
