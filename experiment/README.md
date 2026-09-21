# Green DevOps measurement harness

Added to a fork of `ghostfolio/ghostfolio` (AGPL-3.0) for the research project
_Towards Green DevOps: Measuring and Optimising the Resource Consumption and
Environmental Impact of CI/CD Pipelines_ (Kanishka, University of Kelaniya).

**The upstream application is not modified.** Everything added lives in
`experiment/`, `.github/workflows/config-*.yml`,
`.github/workflows/cache-warmup.yml`, `Dockerfile.experiment` and
`Dockerfile.experiment.dockerignore`. Each run verifies that `apps/`, `libs/`,
`nx.json`, `package.json` and `package-lock.json` still match upstream commit
`e55f9f0e43b022a8db6e5aac4e6d8aa247a11399`, and fails if they do not.

The harness is ported from the `hmpps-activities-management` fork; only the
subject-specific commands differ.

## The six configurations

| Config            | Cache | Lint | Tests                                   | Machines |
| ----------------- | ----- | ---- | --------------------------------------- | -------- |
| A Full            | no    | yes  | all, one process                        | 1        |
| B Cached          | yes   | yes  | all, one process                        | 1        |
| C Minimal         | no    | no   | `--shard=1/4`, one process              | 1        |
| D Cached+Minimal  | yes   | no   | `--shard=1/4`, one process              | 1        |
| E Cached+Parallel | yes   | yes  | all, lint and test on separate machines | 3        |
| F Cached+Workers  | yes   | yes  | all, Jest's own default worker count    | 1        |

"One process" here means `nx run-many --parallel=1 --runInBand`: Nx runs one
project at a time and Jest runs each project's tests in a single process.
F drops `--runInBand` and nothing else. `--parallel=1` is the same in all six,
so B and F differ in one flag, as on hmpps. The project's own npm script uses
`--parallel=4`; no configuration uses it.

## Files

| File                                 | Purpose                                                        |
| ------------------------------------ | -------------------------------------------------------------- |
| `experiment/templates/`              | The single source for all six workflows                        |
| `experiment/generate-workflows.py`   | Generates `config-a.yml` … `config-f.yml` so they cannot drift |
| `.github/workflows/cache-warmup.yml` | Unmeasured; creates the npm cache (see below)                  |
| `experiment/run-pilot.sh`            | Dispatches runs strictly serially in a seeded random order     |
| `experiment/collect-results.sh`      | Downloads artefacts and concatenates them into one CSV         |
| `experiment/analyse.py`              | Per-configuration and per-stage summaries                      |
| `Dockerfile.experiment`              | Deploy stage: package already-built artefacts                  |

## Running it

```bash
python experiment/generate-workflows.py          # after editing a template
gh workflow run cache-warmup.yml --repo kanishka50/ghostfolio   # once, see below
bash experiment/run-pilot.sh 10 20260922         # 60 runs, serial, seeded
bash experiment/collect-results.sh               # download + combine
python experiment/analyse.py                     # summaries only
```

## The cache warm-up

Every cached configuration fails if its npm cache did not restore, so an
uncached install can never be recorded as a cached one. `setup-node` saves the
cache only when the whole job succeeds (`post-if: success()`), so a failed
cached run never creates the cache it was missing: re-dispatching would fail
the same way every time. `cache-warmup.yml` creates it instead, with the same
setup-node inputs and therefore the same cache key. Run it once for a new
subject, and again if GitHub evicts the cache (after 7 days unused).

Nothing is published to npm, pushed to a registry, or sent to ECO-CI's servers
(`send-data: false` on every measurement).
