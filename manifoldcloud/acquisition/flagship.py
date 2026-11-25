"""Build Flagship extraction and count SQL in the CosmoHub Expert Mode syntax."""

from collections.abc import Mapping
from math import isfinite
import re

I_FLUX = "lsst_i_el_model3_ext"
I_MAG = f"-2.5 * log10({I_FLUX}) - 48.6"
KINDS = "kind IN (0, 1)"
COUNT_CUTS = (26.5, 25.5, 25.3, 24.5, 24.1)


def _identifier(name):
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", name):
        raise ValueError(f"Invalid Flagship SQL identifier: {name!r}")
    return name


def _number(value):
    if not isfinite(value):
        raise ValueError("Flagship SQL bounds and cuts must be finite")
    return str(value)


def _footprint(boxes):
    clauses = []
    for box in boxes:
        fields = box if isinstance(box, Mapping) else vars(box)
        ra_min, ra_max, dec_min, dec_max = (fields[key] for key in ("ra_min", "ra_max", "dec_min", "dec_max"))
        if not 0 <= ra_min < ra_max <= 360 or not -90 <= dec_min < dec_max <= 90:
            raise ValueError("Flagship box bounds must be ordered and within the sky coordinate ranges")
        clauses.append(
            f"(ra_gal >= {_number(ra_min)} AND ra_gal < {_number(ra_max)}\n"
            f"    AND dec_gal >= {_number(dec_min)} AND dec_gal < {_number(dec_max)})"
        )
    if not clauses:
        raise ValueError("Supply at least one Flagship box")
    return clauses[0] if len(clauses) == 1 else "(" + "\n  OR ".join(clauses) + ")"


def build_data_query(table, columns, boxes, *, i_limit=26.5):
    """Select the requested intrinsic-photometry columns and the galaxy sample."""
    names = [_identifier(column) for column in columns]
    if not names or len(set(names)) != len(names):
        raise ValueError("Select a nonempty list of distinct Flagship columns")
    selection = ",\n  ".join(names)
    return (f"SELECT\n  {selection}\nFROM {_identifier(table)}\n"
            f"WHERE {_footprint(boxes)}\n  AND {KINDS}\n  AND {I_FLUX} > 0\n"
            f"  AND {I_MAG} < {_number(i_limit)}\n")


def build_count_query(table, boxes):
    """Count all objects and galaxies, with and without each depth cut."""
    expressions = ["COUNT(*) AS n_all", f"SUM(CASE WHEN {KINDS} THEN 1 ELSE 0 END) AS n_kind_01"]
    for cut in COUNT_CUTS:
        label = f"n_i{int(round(10 * cut))}"
        bright = f"{I_FLUX} > 0 AND {I_MAG} < {cut}"
        expressions.append(f"SUM(CASE WHEN {bright} THEN 1 ELSE 0 END) AS {label}")
        expressions.append(f"SUM(CASE WHEN {KINDS} AND {bright} THEN 1 ELSE 0 END) AS {label}_kind_01")
    selection = ",\n  ".join(expressions)
    return f"SELECT\n  {selection}\nFROM {_identifier(table)}\nWHERE {_footprint(boxes)}\n"
