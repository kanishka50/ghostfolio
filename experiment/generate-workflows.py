#!/usr/bin/env python3
"""Generate the six pipeline-configuration workflows from the templates.

The point of generating them is that the configurations then CANNOT differ in
anything except the factors that define them. Editing a generated workflow by
hand defeats that guarantee - edit the template instead and re-run this.

    python experiment/generate-workflows.py

Configurations (the independent variable, at six levels):

    A Full             no cache | lint | all tests, one process
    B Cached           CACHE    | lint | all tests, one process
    C Minimal          no cache | ---- | 1/4 of tests, one process
    D Cached+Minimal   CACHE    | ---- | 1/4 of tests, one process
    E Cached+Parallel  CACHE    | lint and test as parallel jobs (3 VMs)
    F Cached+Workers   CACHE    | lint | all tests, ACROSS THE RUNNER'S CORES

"Minimal" is mechanical: lint removed, tests run with the runner's own
`--shard=1/4`. Nothing is selected by hand, so no subset can have been chosen
for its effect. Nx forwards `--shard` to Jest unchanged (58 test files -> 16).

Configurations E and F are two different meanings of "run the tests in
parallel", and separating them is the point of F:

    E spreads the work over THREE MACHINES. Each is a fresh VM that installs
      its own dependencies, so the install stage is paid three times.
    F spreads the work over the CORES OF ONE MACHINE. Nothing is duplicated.

B is the common control for both: B, E and F run identical work (cache, lint,
the whole suite) and differ only in how the test stage is distributed.

This generator is ported from the hmpps-activities-management fork. Only the
subject-specific commands differ; the configuration structure is identical.
"""

import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
TPL = ROOT / "experiment" / "templates"
OUT = ROOT / ".github" / "workflows"

NO_CACHE = "          # NO `cache:` key. This is an UNCACHED configuration."
CACHE = "          # Dependency caching ON - a defining factor of this configuration.\n          cache: 'npm'"

# The test setting is set EXPLICITLY in every configuration and is never
# inherited from the subject application (EXPERIMENT-PLAN.md section 3).
#
# Ghostfolio has TWO layers that can run tests concurrently, where hmpps had one:
#
#   Nx  `--parallel=N`  how many PROJECTS (api, client, common, ui) run at once.
#                       nx.json sets 1; the project's own npm script raises it
#                       to 4.
#   Jest `--runInBand`  whether each project's tests run in ONE process or in
#                       Jest's worker pool (default: cores - 1 workers).
#
# The definitions, stated for this subject:
#
#   one process  - Nx runs one project at a time (`--parallel=1`) AND Jest runs
#                  that project's tests in one process (`--runInBand`). Both
#                  force-serial settings are written out.
#   default      - Nx still one project at a time; `--runInBand` simply absent,
#                  so Jest picks its own worker count. Never a number chosen by
#                  hand. Every run logs `nproc`, so the count is recoverable.
#
# `--parallel=1` is held FIXED in all six configurations, so B and F differ in
# exactly one flag, `--runInBand`, just as they do on hmpps. Raising Nx's
# project parallelism in F as well would change two things at once and make
# B-vs-F mean something different here than on hmpps. The project's own
# `--parallel=4` is therefore not used by any configuration.
NX_TEST = "npx nx run-many --target=test --all --parallel=1 --skip-nx-cache"
TEST_ALL = NX_TEST + " --runInBand"
TEST_SHARD = NX_TEST + " --runInBand --shard=1/4"
TEST_WORKERS = NX_TEST

# The project's test script loads these from .env.example through
# `npx dotenv-cli`, which is not a dependency and would be downloaded inside the
# measured stage. The placeholder values are supplied directly instead.
TEST_ENV_VARS = [
    ("REDIS_HOST", "redis"),
    ("REDIS_PORT", "'6379'"),
    ("REDIS_PASSWORD", "pilot"),
    ("POSTGRES_DB", "ghostfolio-db"),
    ("POSTGRES_USER", "user"),
    ("POSTGRES_PASSWORD", "pilot"),
    ("ACCESS_TOKEN_SALT", "pilot-fixed-salt"),
    ("DATABASE_URL", "postgresql://user:pilot@postgres:5432/ghostfolio-db?connect_timeout=300"),
    ("JWT_SECRET_KEY", "pilot-fixed-secret"),
]
TEST_ENV = "\n".join(f"          {k}: {v}" for k, v in TEST_ENV_VARS)

LINT_CMD = "npx nx run-many --target=lint --all --skip-nx-cache"

LINT_BLOCK = f"""
      # ================= STAGE: LINT =================
      - name: Lint
        run: {LINT_CMD}

      - name: ECO-CI - measure lint
        uses: green-coding-solutions/eco-ci-energy-estimation@v5
        with:
          task: get-measurement
          label: lint
          send-data: false
"""

# Config C and D remove the lint stage entirely; the comment keeps the removal
# visible in the generated file rather than leaving a silent gap.
NO_LINT_BLOCK = """
      # ================= STAGE: LINT - REMOVED =================
      # This is a MINIMAL configuration: the lint stage is not run. Lint emits
      # no files, so no later stage loses an input. What is given up is
      # detection, not build correctness.
"""

SINGLE = [
    # id, name, cache line, lint block, test command, expected measurement rows
    ("A", "Full", NO_CACHE, LINT_BLOCK, TEST_ALL, 5),
    ("B", "Cached", CACHE, LINT_BLOCK, TEST_ALL, 5),
    ("C", "Minimal", NO_CACHE, NO_LINT_BLOCK, TEST_SHARD, 4),
    ("D", "Cached+Minimal", CACHE, NO_LINT_BLOCK, TEST_SHARD, 4),
    ("F", "Cached+Workers", CACHE, LINT_BLOCK, TEST_WORKERS, 5),
]

# Config E: three jobs. lint and test run concurrently; build+deploy waits for
# both. Each job installs for itself because each is a fresh VM.
PARALLEL_JOBS = [
    (
        "lint",
        "Lint (parallel with test)",
        "",
        f"""      - name: Lint
        run: {LINT_CMD}

      - name: ECO-CI - measure lint
        uses: green-coding-solutions/eco-ci-energy-estimation@v5
        with:
          task: get-measurement
          label: lint
          send-data: false
""",
        2,
    ),
    (
        "test",
        "Test (parallel with lint)",
        "",
        f"""      - name: Test
        env:
{TEST_ENV}
        run: {TEST_ALL}

      - name: ECO-CI - measure test
        uses: green-coding-solutions/eco-ci-energy-estimation@v5
        with:
          task: get-measurement
          label: test
          send-data: false
""",
        2,
    ),
    (
        "build",
        "Build and deploy",
        "    needs: [lint, test]",
        """      - name: Build
        run: npm run build:production

      - name: ECO-CI - measure build
        uses: green-coding-solutions/eco-ci-energy-estimation@v5
        with:
          task: get-measurement
          label: build
          send-data: false

      - name: Deploy (package built app into image)
        run: docker build -f Dockerfile.experiment -t ghostfolio:packaged .

      - name: ECO-CI - measure deploy
        uses: green-coding-solutions/eco-ci-energy-estimation@v5
        with:
          task: get-measurement
          label: deploy
          send-data: false
""",
        3,
    ),
]

HEADER = "# GENERATED FILE - do not edit. Regenerate with:\n#   python experiment/generate-workflows.py\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    single_tpl = (TPL / "single-job.yml.tpl").read_text(encoding="utf-8")

    for cid, name, cache, lint, test_cmd, rows in SINGLE:
        text = (
            single_tpl.replace("@@CONFIG@@", cid)
            .replace("@@CONFIG_NAME@@", name)
            .replace("@@CACHE_LINE@@", cache)
            .replace("@@CACHE_EXPECTED@@", "none" if cache is NO_CACHE else "hit")
            .replace("@@LINT_BLOCK@@", lint)
            .replace("@@TEST_ENV@@", TEST_ENV)
            .replace("@@TEST_CMD@@", test_cmd)
            .replace("@@EXPECTED_ROWS@@", str(rows))
        )
        assert "@@" not in text, f"unfilled placeholder in config {cid}"
        path = OUT / f"config-{cid.lower()}.yml"
        path.write_text(HEADER + text, encoding="utf-8", newline="\n")
        print(f"wrote {path.relative_to(ROOT)}")

    head = (TPL / "parallel-header.yml.tpl").read_text(encoding="utf-8")
    job_tpl = (TPL / "parallel-job.yml.tpl").read_text(encoding="utf-8")
    parts = []
    for job_id, job_name, needs, work, rows in PARALLEL_JOBS:
        parts.append(
            job_tpl.replace("@@JOB_ID@@", job_id)
            .replace("@@JOB_NAME@@", job_name)
            .replace("@@NEEDS@@", needs)
            .replace("@@CACHE_EXPECTED@@", "hit")   # every Config E job is cached
            .replace("@@WORK@@", work)
            .replace("@@EXPECTED_ROWS@@", str(rows))
        )
    # The header ends with "jobs:"; jobs are separated by one blank line.
    text = head + "\n".join(parts)
    assert "@@" not in text, "unfilled placeholder in config E"
    path = OUT / "config-e.yml"
    path.write_text(HEADER + text, encoding="utf-8", newline="\n")
    print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
