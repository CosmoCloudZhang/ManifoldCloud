"""Retrieve the two simulated galaxy catalogues and record where each file came from.

diffsky         read chosen columns of a Diffsky shell, locally or by HTTPS byte ranges
fetch_diffsky   extract every shell to Parquet, resumably, with checksums
flagship        build the Flagship 2 SQL for CosmoHub
cosmohub        CosmoHub web API client
fetch_flagship  store the Flagship query results and verify them
status          report what has been acquired and whether it is intact

The commands in scripts/ call the main() functions of these modules.
"""
