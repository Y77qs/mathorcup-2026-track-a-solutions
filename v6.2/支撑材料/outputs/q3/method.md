# Q3 method (as implemented in EXP-0042 / EXP-0043)

1. Style-conditional generation: shrunk empirical marginals + shrunk Gaussian copula, kappa/kappa_R selected INSIDE each outer training set (per-fold selection recorded in EXP-0042/outputs.json per_fold_tuning).
2. Raw conditional spectra are written first (samples_raw.csv); the constrained design (samples.csv) is obtained by projection with declared bounds.
3. Constraints: 33 linear-calibrated concentrations >= 0; DMS/diacetyl/4VG c' <= c_source; trans-2-nonenal on the CHEMICAL column; stale hops only as a labelled training-fitted proxy.
4. Diagnostics: empirical V (normalised by D_train), signed U (never clipped), marginals, dependence, diversity, nearest-neighbour, duplicate share, edge fraction.
5. Transfer: convex QP with quantile anchor; controls are source-fixed and target-mean projection; every solve records status and primal/dual residuals.
