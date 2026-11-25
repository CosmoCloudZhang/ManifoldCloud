# Codex task: build the ManifoldCloud data pipeline (unattended overnight run)

You are working in the repository root, the folder `ManifoldCloud/`. Nobody is available until morning. Do not wait for answers. Where a choice is needed, use the defaults in this prompt, record the choice, and continue.

## 1. Read first

1. `documents/data_pipeline_plan.md`. It is the authority for design, column lists, numbers and checks.
2. This prompt. Where the two differ, this prompt wins.
3. `documents/reference/`. Two small helpers that were tested against the real Diffsky files. They are reference material, not part of the package.

## 2. Goal for tonight

| Steps | What to do tonight |
|---|---|
| S00 to S04, S06, S07 | Complete them, including their checks |
| S05 | Write the fetch script and run the pilot only (steps 487, 442, 392, 300) |
| S10 to S13 | Write the modules, scripts and unit tests on synthetic fixtures; run them on the Diffsky pilot shells |
| S08, S09, full S05 | Do not attempt. They belong to the mentor |

## 3. Defaults that replace the plan's open decisions

**Approval.** The mentor approved the steps tagged CODEX on 25 November 2026.

**Git.**
- If the folder is not a repository, run `git init`. Add no remote. Never push.
- First commit: `environment.yml` and `documents/` as they are now, with the message `baseline before pipeline work`.
- After each step whose check passes, commit with a message such as `S04: Diffsky reader`.
- Stage explicit paths only. Never use `git add -A` or `git add .`. Leave all other existing files untracked.

**Environment.** Do not create, update or modify any conda environment.
- Create a virtual environment inside the repository that reuses the mentor environment's packages:

  ```bash
  <conda>/envs/CosmoConda/bin/python -m venv --system-site-packages .venv
  ```

  ```bash
  .venv/bin/python -m pip install --no-cache-dir hdf5plugin pytest responses
  ```

  ```bash
  .venv/bin/python -m pip install --no-cache-dir --no-deps -e .
  ```

- Use `.venv/bin/python` for every command. Add `.venv/` to `.gitignore`.
- Still edit `environment.yml` as step S01 says, so the documented environment stays correct. Do not run `conda env update`.
- If the network is unavailable for `pip`:
  - write tests as `unittest.TestCase` classes, which `pytest` can also run later;
  - mock HTTP with `unittest.mock` in place of `responses`;
  - run tests with `<conda>/envs/CosmoConda/bin/python -B -m unittest discover -s tests`;
  - say so at the top of the report.
- If `hdf5plugin` installs but `h5py.h5z.filter_avail(32026)` is false, build the reader on `documents/reference/blosc2_fallback_decoder.py`, and record it in the decisions log.

**Data root tonight.** Use `data/` at the repository root, through `MANIFOLDCLOUD_DATA_ROOT`. It is git-ignored. Pilot data only.

**Network allow-list.**
- The Python package index, for the three packages above.
- The Diffsky base URL of plan section 2.1, for the pilot and the optional network tests: at most 500 MB transferred in total and at most 4 connections.
- Nothing else. In particular, send no request of any kind to `cosmohub.pic.es` or `api.cosmohub.pic.es`, and upload nothing anywhere.

**Credentials.** Never ask for, look for, read or use a real password or token. Do not sign in to any service. All CosmoHub code is tested against mocked HTTP only.

**Files.**
- Do not modify or delete anything under `lectures/` or `notebooks/`, or any file that existed before tonight, except `environment.yml`.
- New files go only where the plan's layout puts them, plus `figures/data_validation/` and `report/`.
- Do not write outside the repository.

**Limits.** No single command longer than 30 minutes. Nothing that needs more than about 8 GB of memory. Process one Diffsky shell at a time.

## 4. Working rules

1. Work through the steps in order. Finish a step's check before starting the next step.
2. Paste each check's command and its real output into the report. Do not summarise a check as passed without the output.
3. If a check fails, make up to three honest attempts to fix the cause. Never weaken a check, change an expected number, or skip a test to make it pass.
4. If it still fails, mark the step BLOCKED with the evidence, then continue with every later step that does not depend on it.
5. Record every deviation from the plan in `documents/decisions_log.md`, with the reason.
6. Keep the code simple: plain functions, short scripts, a docstring at the top of every module, in the style of `lectures/lecture04/output/check_environment.py`.
7. Prefer the installed libraries over new dependencies. Add no package beyond the three named above.

## 5. Notes for specific steps

**S04 and S05.** The plan gives exact row counts for steps 487, 442, 392 and 300. They were measured on the real files; treat any mismatch as a bug in the reader, not in the numbers. `documents/reference/https_range_file.py` shows byte-range reading that worked, but was slow (0.23 MB/s); the plan's 2 MB/s gate still applies.

**S07.** `--mode manual` must work with no network at all. Include the end-to-end test that plants a fake password and asserts it appears in no log, no exception text, no output and no written file.

**S10 to S13.** Flagship data will not exist tonight.
- Build small synthetic tables that follow the raw schemas of plan sections 3.1 and 3.2, and unit-test every function on them.
- Run the scripts on the Diffsky pilot shells, writing under `data/`.
- Mark every check that needs Flagship data as `PENDING (needs S09)`. Do not invent Flagship numbers.

## 6. Final deliverable

Write `documents/overnight_report.md` containing:

1. A table of all steps with status `DONE`, `PENDING` or `BLOCKED`.
2. For each step, the check commands and their pasted output.
3. The list of files created or changed.
4. Deviations from the plan, with reasons.
5. Open questions for the mentor.
6. What the mentor must do next: S08, S09 and the full S05 run, with the exact commands.

Finish by running the whole test suite and `git status`, and paste both outputs at the end of the report. Commit the report.

## 7. When to stop

Stop and write the report when the S13 code is done, or when no remaining step can make progress. Do not start anything outside this list.
