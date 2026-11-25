SELECT
  galaxy_id,
  halo_id,
  kind,
  random_index,
  ra_gal,
  dec_gal,
  true_redshift_gal,
  observed_redshift_gal,
  lsst_u_el_model3_ext,
  lsst_g_el_model3_ext,
  lsst_r_el_model3_ext,
  lsst_i_el_model3_ext,
  lsst_z_el_model3_ext,
  lsst_y_el_model3_ext,
  dominant_shape,
  bulge_fraction,
  bulge_r50,
  disk_r50,
  bulge_axis_ratio,
  disk_axis_ratio,
  bulge_nsersic,
  inclination_angle,
  log_stellar_mass,
  log_sfr,
  color_kind,
  euclid_nisp_h
FROM euclid_fs2_mock_dr_v1_1_phz
WHERE (ra_gal >= 226.66667 AND ra_gal < 233.33333
    AND dec_gal >= 23.16209 AND dec_gal < 28.90335)
  AND kind IN (0, 1)
  AND lsst_i_el_model3_ext > 0
  AND -2.5 * log10(lsst_i_el_model3_ext) - 48.6 < 26.5
