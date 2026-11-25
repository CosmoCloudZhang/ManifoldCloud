"""Verify Flagship SQL against the approved columns, footprint and cuts."""

from contextlib import closing
from math import log10
from pathlib import Path
import re
import sqlite3
import tomllib
from types import SimpleNamespace

from manifoldcloud.flagship import build_count_query, build_data_query


ROOT = Path(__file__).resolve().parents[1]
TABLE = "euclid_fs2_mock_dr_v1_1_phz"
BOX = {"ra_min": 226.66667, "ra_max": 233.33333, "dec_min": 23.16209, "dec_max": 28.90335}
COLUMNS = [
    "galaxy_id", "halo_id", "kind", "random_index", "ra_gal", "dec_gal",
    "true_redshift_gal", "observed_redshift_gal",
    "lsst_u_el_model3_ext", "lsst_g_el_model3_ext", "lsst_r_el_model3_ext",
    "lsst_i_el_model3_ext", "lsst_z_el_model3_ext", "lsst_y_el_model3_ext",
    "dominant_shape", "bulge_fraction", "bulge_r50", "disk_r50",
    "bulge_axis_ratio", "disk_axis_ratio", "bulge_nsersic", "inclination_angle",
    "log_stellar_mass", "log_sfr", "color_kind", "euclid_nisp_h",
]


def _flux(magnitude):
    return 10 ** (-0.4 * (magnitude + 48.6))


def _connection(rows):
    connection = sqlite3.connect(":memory:")
    connection.create_function("log10", 1, log10, deterministic=True)
    connection.execute(f"CREATE TABLE {TABLE} ({', '.join(COLUMNS)})")
    connection.executemany(
        f"INSERT INTO {TABLE} (galaxy_id, ra_gal, dec_gal, kind, lsst_i_el_model3_ext) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    return connection


def test_mirror_queries_match_golden_files_byte_for_byte():
    with (ROOT / "config" / "default.toml").open("rb") as source:
        config = tomllib.load(source)
    flagship = config["flagship"]
    assert flagship["table"] == TABLE
    assert flagship["box"] == BOX
    assert flagship["columns"] == COLUMNS
    data_query = build_data_query(flagship["table"], flagship["columns"], [flagship["box"]],
                                  i_limit=config["cuts"]["preselection_i"])
    count_query = build_count_query(flagship["table"], [flagship["box"]])
    directory = ROOT / "scripts" / "queries"
    assert data_query.encode("utf-8") == (directory / "flagship_mirror_843.sql").read_bytes()
    assert count_query.encode("utf-8") == (directory / "flagship_mirror_843_count.sql").read_bytes()
    selected = re.search(r"\bSELECT\s+(.*?)\s+FROM\b", data_query, re.I | re.S)[1]
    columns = [column.strip() for column in selected.split(",")]
    assert columns == COLUMNS
    assert len(columns) == 26
    assert not any(word in name.lower() for word in ("odonnell", "error", "mag_gal") for name in columns)


def test_data_query_filters_both_boxes_with_half_open_bounds():
    second = SimpleNamespace(ra_min=210, ra_max=215, dec_min=23, dec_max=29)
    data_query = build_data_query(TABLE, COLUMNS, [BOX, second])
    rows = [
        (1, BOX["ra_min"], BOX["dec_min"], 0, _flux(24.0)),
        (2, BOX["ra_max"], 25, 0, _flux(24.0)),
        (3, 230, BOX["dec_max"], 0, _flux(24.0)),
        (4, 232, 25, 2, _flux(24.0)),
        (5, 232, 25, 1, _flux(26.6)),
        (6, 232, 25, 1, 0.0),
        (7, 209, 24, 1, _flux(25.0)),
        (8, 213, 24, 1, _flux(25.0)),
        (9, 213, 24, 2, _flux(25.0)),
        (10, 213, 29, 1, _flux(25.0)),
    ]
    with closing(_connection(rows)) as connection:
        result = connection.execute(data_query)
        assert [column[0] for column in result.description] == COLUMNS
        assert sorted(row[0] for row in result) == [1, 8]


def test_count_query_reports_all_and_galaxy_counts_at_every_cut():
    magnitudes = (26.0, 25.4, 25.0, 24.3, 23.8)
    rows = [(2 * index + kind, 230, 25, kind, _flux(magnitude))
            for index, magnitude in enumerate(magnitudes) for kind in (0, 2)]
    rows.extend(((100, 230, 25, 1, 0.0), (101, 230, 25, 3, -1.0),
                 (102, BOX["ra_max"], 25, 0, _flux(23.8))))
    with closing(_connection(rows)) as connection:
        result = connection.execute(build_count_query(TABLE, [BOX]))
        counts = dict(zip((column[0] for column in result.description), result.fetchone(), strict=True))

    expected = {"n_all": 12, "n_kind_01": 6}
    for cut, galaxy_count in zip((265, 255, 253, 245, 241), range(5, 0, -1), strict=True):
        expected[f"n_i{cut}"] = 2 * galaxy_count
        expected[f"n_i{cut}_kind_01"] = galaxy_count
    assert counts == expected
