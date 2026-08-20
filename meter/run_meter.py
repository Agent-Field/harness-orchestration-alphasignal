"""Run the meter over the fixture traces: print the ladder table, save the slide."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import pandas as pd
from meter.blast_radius import (load_runs, load_ground_truth, ladder_table,
                                ladder_plot, save_plot)

HERE = Path(__file__).parent
runs = load_runs(HERE / "fixtures/runs.json")
truth = load_ground_truth(HERE / "fixtures/ground_truth.json")

df = ladder_table(runs, truth)
pd.set_option("display.width", 200, "display.max_columns", 30,
              "display.float_format", lambda v: f"{v:7.3f}")
table = df.to_string()
print(table)
(HERE / "out/ladder_table.txt").write_text(table + "\n")
df.to_csv(HERE / "out/ladder_table.csv")

fig = ladder_plot(df)
print("\nsaved:", save_plot(fig, HERE / "out/ladder.png"))
