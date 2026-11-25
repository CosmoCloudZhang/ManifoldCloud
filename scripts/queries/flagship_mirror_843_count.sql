SELECT
  COUNT(*) AS n_all,
  SUM(CASE WHEN kind IN (0, 1) THEN 1 ELSE 0 END) AS n_kind_01,
  SUM(CASE WHEN lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 26.5 THEN 1 ELSE 0 END) AS n_i265,
  SUM(CASE WHEN kind IN (0, 1) AND lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 26.5 THEN 1 ELSE 0 END) AS n_i265_kind_01,
  SUM(CASE WHEN lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 25.5 THEN 1 ELSE 0 END) AS n_i255,
  SUM(CASE WHEN kind IN (0, 1) AND lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 25.5 THEN 1 ELSE 0 END) AS n_i255_kind_01,
  SUM(CASE WHEN lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 25.3 THEN 1 ELSE 0 END) AS n_i253,
  SUM(CASE WHEN kind IN (0, 1) AND lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 25.3 THEN 1 ELSE 0 END) AS n_i253_kind_01,
  SUM(CASE WHEN lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 24.5 THEN 1 ELSE 0 END) AS n_i245,
  SUM(CASE WHEN kind IN (0, 1) AND lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 24.5 THEN 1 ELSE 0 END) AS n_i245_kind_01,
  SUM(CASE WHEN lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 24.1 THEN 1 ELSE 0 END) AS n_i241,
  SUM(CASE WHEN kind IN (0, 1) AND lsst_i_el_model3_ext > 0 AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 24.1 THEN 1 ELSE 0 END) AS n_i241_kind_01
FROM euclid_fs2_mock_dr_v1_1_phz
WHERE (ra_gal >= 226.66667 AND ra_gal < 233.33333
    AND dec_gal >= 23.16209 AND dec_gal < 28.90335)
