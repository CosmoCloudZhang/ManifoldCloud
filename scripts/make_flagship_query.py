"""Generate the mirror patch extraction and count queries for CosmoHub."""

from pathlib import Path

from manifoldcloud.config import load
from manifoldcloud.flagship import build_count_query, build_data_query
from manifoldcloud.provenance import write_text


def main():
    config = load()
    catalogue = config.flagship
    folder = Path(__file__).resolve().parent / "queries"
    boxes = [catalogue.box]
    for filename, sql in (
        ("flagship_mirror_843.sql", build_data_query(catalogue.table, catalogue.columns, boxes,
                                                    i_limit=config.cuts.preselection_i)),
        ("flagship_mirror_843_count.sql", build_count_query(catalogue.table, boxes)),
    ):
        path = folder / filename
        write_text(path, sql)
        print(path)


if __name__ == "__main__":
    main()
