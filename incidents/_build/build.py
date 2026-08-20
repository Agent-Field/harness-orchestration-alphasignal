import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen, specs_a, specs_b, specs_c

ALL = specs_a.SPECS + specs_b.SPECS + specs_c.SPECS
for s in ALL:
    d = gen.write_incident(s)
    print("wrote", os.path.basename(d), len(open(os.path.join(d, "logs.txt")).readlines()), "log lines")
print("total incidents:", len(ALL))
