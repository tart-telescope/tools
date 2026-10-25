# Releasing the TART tools image

This repo has no package version of its own: **the release is the git tag**.
Pushing `vMAJOR.MINOR.PATCH` triggers `.github/workflows/docker-publish.yml`,
which builds `ghcr.io/tart-telescope/tools:<tag>` for amd64 **and** arm64 and
pushes it to GHCR.

```console
$ invoke release --dry-run                      # print the plan, change nothing
$ invoke release                                # prompts, then tests + tags
$ invoke release --disko-version=1.5.0 --yes    # what disko's chain runs
```

It can be run standalone, or as stage 4 of disko's chain
(`invoke -r ~/tart-telescope/tools release --level=patch --yes
--disko-version=<new>`); see `~/github/disko/RELEASE.md` for the chain and
`tart_cargo/AGENTS.md` for the image-version policy in full.

## Tasks

```console
$ invoke --list
  bump      Show (or compute) the next image tag — the image version lives in tags.
  release   test -> pin -> tag -> CI builds the image -> wait for GHCR.
  test      Build the image and run every docker test target (make test-all).
```

`invoke` and `plumbum` must be importable by whatever interpreter runs these
(both are installed globally today; disko's dev group carries them for the
chain). Run commands from this directory, or use `invoke -r <path>`.

### `test` — the image is the test

`make docker` builds `tart_tools` locally, then `make test-all` runs every
target against it:

| target | checks |
|---|---|
| `testd` | `tart2ms` end to end on `test/vis_*.hdf` |
| `testdisko` | `disko --ms … --HDF … --healpix --fov 140deg --res 0.5deg` |
| `testspot` | `spotless` on the same measurement set |
| `test-imports` | `tart2ms`, `disko`, `spotless`, `tart_tools` all import |
| `test-tart-tools` | the `tart_*` CLIs respond to `--help` |

Because the image build pip-installs everything the `Dockerfile` pins from
PyPI, building it is also the proof that the pins resolve. `--quick` skips the
build and tests the image you already have.

### `bump`

The version lives in tags, so this only shows `v1.2.3 -> v1.2.4`
(`--level patch|minor|major`, `--dry-run` to preview). Use
`git tag --sort=-v:refname` semantics: pick the next version after the latest
**pushed** tag.

### `release`

1. **pin** — with `--disko-version=X.Y.Z`, first wait until PyPI really has
   that release (the disko stage of the chain may have only just landed), then
   set the Dockerfile's pin to `disko==X.Y.Z`. Exact pins, not `>=`: an image
   must be reproducible, so a rebuild six months from now gets the same disko
   instead of "whatever is newest". Other packages keep their `>=` pins —
   raise those deliberately when a newer release is needed.
2. **test** — `make docker` + `make test-all` (or `--skip-tests`, which then
   still builds the image so the new pin is validated).
3. **tag** — commit (only if the pin changed), annotated tag `v<next>`, push
   with `--follow-tags`. That push is what triggers the image build.
4. **wait** — poll GHCR until `ghcr.io/tart-telescope/tools:<tag>` exists
   (up to 60 min: arm64 runs on a self-hosted runner). tart_cargo must not
   bump its base image ahead of a pushed image tag — see
   `tart_cargo/AGENTS.md`. `--no-wait` skips it, in which case tell whoever
   releases tart_cargo to wait themselves.

Flags: `--level`, `--yes`, `--disko-version`, `--skip-tests`,
`--dry-run`, `--wait` / `--no-wait`.

## Safety

- prompts once (or `--yes`); `--dry-run` prints the whole plan;
- refuses if tracked files are modified (untracked scratch, e.g. `.qwen/` or
  `__pycache__/`, is only reported);
- refuses to tag an existing version;
- nothing here pushes unless the prompt is answered.

## Manual fallback

```console
$ make docker && make test-all
$ vim Dockerfile                 # raise pins if that is the point
$ git commit -am "Release vX.Y.Z: pin disko==A.B.C"
$ git tag -a vX.Y.Z -m "Release vX.Y.Z"
$ git push --follow-tags origin main
$ gh run list --workflow docker-publish.yml --watch
$ docker manifest inspect ghcr.io/tart-telescope/tools:vX.Y.Z
```

## After the release

1. Verify the image: `docker manifest inspect ghcr.io/tart-telescope/tools:<tag>`.
2. Verify every cab command still resolves inside it (the check from
   `tart_cargo/AGENTS.md`, also runnable as `invoke -r <tart_cargo> test
   --with-image`):

   ```console
   $ docker run --rm --entrypoint "" ghcr.io/tart-telescope/tools:<tag> sh -c \
     'for cmd in tart_download_data tart_get_archive_data tart_set_mode tart2ms \
                 tart-gnss-acquire disko disko_draw spotless; do
        printf "%-30s " "$cmd"; which "$cmd" 2>&1 || echo "MISSING"
      done'
   ```

3. Then release tart_cargo, pointing its base image at this tag — see
   `tart_cargo/RELEASE.md`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| arm64 leg still queued after a long wait | self-hosted runner offline; check `docker-publish.yml` runs and the runner, then re-poll (`invoke release` already tagged — do **not** re-tag) |
| pin change but tests skipped | `--skip-tests` builds the image only; that still validates the pin resolves, but run `make test-all` before shipping if you can |
| `make docker` fails on pip install | a pin no longer resolves — fix the `Dockerfile` and commit before tagging |
| GHCR wait times out | the image tag never appeared: check the workflow run; `--no-wait` releases are the usual cause of someone racing this |
