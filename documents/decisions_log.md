# Data pipeline decisions

## 2026-11-25 overnight run

- The overnight prompt authorises local Git initialization and a baseline commit. The baseline contains the existing environment recipe and documents.
- The overnight prompt uses a repository virtual environment with the mentor's installed packages, limits live acquisition to the four-shell Diffsky pilot, defers S08, S09 and full S05, and sets the overnight data root to the ignored `data/` directory.
- S00 uses the mentor environment's existing build tooling for editable installation to avoid downloading build dependencies outside the package allow-list.
- S01 used approved outbound access to PyPI after the restricted sandbox could not resolve the package index. The three requested distributions resolved pytest's required dependencies `iniconfig` and `pluggy` inside `.venv`. The mentor conda environment was unchanged.
- S02 uses noise seeds 42 and 43 for Flagship and Diffsky, respectively, and a student subset fraction of 0.02. These are configurable defaults for reproducible runs and can be revised after the mentor measures the final files.
- S04 keeps fsspec's HTTP file interface and uses strict 206 responses, exact range endpoints, bounded metadata caching and coalesced prefetch. The Diffsky server reports `*` for total size in `Content-Range`; the reader accepts this with the exact offsets and verifies the received length. HEAD supplies the file size.
