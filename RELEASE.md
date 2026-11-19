# Releasing the TART tools image

The release is controlled by **tart_cargo's invoke script** — the same
script that releases the tart_cargo package. Both releases live in one
place, and the tools release tests the image with that script's stimela
gates (run these from this checkout's sibling `../tart_cargo`, or use
`invoke -r ../tart_cargo …` from anywhere):

```console
$ invoke -r ../tart_cargo tools-test                          # local build + stimela gates, no tagging
$ invoke -r ../tart_cargo tools-release --dry-run             # print the plan, change nothing
$ invoke -r ../tart_cargo tools-release --disko-version=1.5.0 --yes   # what disko's chain runs
```

This repo has no package version of its own: **the release is the git tag**.
Pushing `vMAJOR.MINOR.PATCH` triggers `.github/workflows/docker-publish.yml`,
which builds `ghcr.io/tart-telescope/tools:<tag>` for amd64 **and** arm64 and
pushes it to GHCR (arm64 on a self-hosted runner).

## What `tools-release` does

1. **pin** — with `--disko-version=X.Y.Z`, first wait until PyPI really has
   that release (the disko stage of the chain may have only just landed),
   then set the Dockerfile's exact `disko==X.Y.Z` pin. Exact pins, not `>=`:
   an image must be reproducible. Other packages keep their `>=` pins —
   raise those deliberately when a newer release is needed.
2. **build** — `docker build -t ghcr.io/tart-telescope/tools:<next>`
   **locally**. The build is what proves the (possibly just-changed) pins
   still resolve, and it is the image every gate below runs.
3. **gates** — this script's stimela tests against that local build:
   the YAML + dry-run recipe suite, every cab `command` checked inside the
   image (`docker run`), and the end-to-end `smoke` pipeline (offline, on
   the committed mz-up visibility data). The image is fed to stimela by
   converting the local docker build into its `.simg` cache
   (`docker-daemon:`) — without that, stimela would silently pull the
   *published* image from GHCR instead of the build under test.
   `--skip-tests` skips the gates (the build still validated the pins).
4. **tag** — commit (only if the pin changed), annotated tag `v<next>`,
   push with `--follow-tags`. That push is what triggers the multi-arch
   image build.
5. **wait** — poll GHCR until `ghcr.io/tart-telescope/tools:<tag>` exists
   (up to 60 min). tart_cargo must not bump its base image ahead of a
   pushed image tag — see `../tart_cargo/AGENTS.md`. `--no-wait` skips it.

Then release tart_cargo against the new tag:
`invoke -r ../tart_cargo release --tools-tag=<new tag>` — see
`../tart_cargo/RELEASE.md`.

It runs as stage 4 of disko's chain
(`invoke -r ../tart_cargo tools-release --level=patch --yes
--disko-version=<new>`); see `../disko/RELEASE.md` for the chain.

`invoke` and `plumbum` must be importable by whichever interpreter runs the
script (tart_cargo's venv carries them; disko's dev group carries them for
the chain).

Flags: `--level`, `--yes`, `--disko-version`, `--skip-tests`,
`--dry-run`, `--wait` / `--no-wait`.

## The Makefile targets (standalone)

`make docker` + `make test-all` still work on their own (tart2ms end to
end, disko, spotless, imports and the `tart_*` CLIs, all inside the local
`tart_tools` image) — useful while hacking on the Dockerfile. The release
no longer calls them: it tests with stimela, which exercises the cabs the
way the pipeline actually runs them.

## Safety

- prompts once (or `--yes`); `--dry-run` prints the whole plan;
- refuses if tracked files in this checkout are modified (untracked
  scratch is only reported);
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
2. Verify every cab command still resolves inside it (also runnable as
   `invoke -r ../tart_cargo test --with-image`):

   ```console
   $ docker run --rm --entrypoint "" ghcr.io/tart-telescope/tools:<tag> sh -c \
     'for cmd in tart_download_data tart_get_archive_data tart_set_mode tart2ms \
                 tart-gnss-acquire disko disko_draw spotless; do
        printf "%-30s " "$cmd"; which "$cmd" 2>&1 || echo "MISSING"
      done'
   ```

3. Then release tart_cargo, pointing its base image at this tag — see
   `../tart_cargo/RELEASE.md`.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `docker not found on PATH` | the tools release builds the image locally — install docker (or use the manual fallback) |
| stimela gates run the wrong image | the `.simg` seed step was skipped or failed; `tools-test` re-seeds `~/.singularity/ghcr.io-tart-telescope-tools:<tag>.simg` from `docker-daemon:` every run |
| arm64 leg still queued after a long wait | self-hosted runner offline; check `docker-publish.yml` runs and the runner, then re-poll (`tools-release` already tagged — do **not** re-tag) |
| pin change but gates skipped | `--skip-tests` builds the image only; that still validates the pin resolves, but run the full gates before shipping if you can |
| `docker build` fails on pip install | a pin no longer resolves — fix the `Dockerfile` and commit before tagging |
| GHCR wait times out | the image tag never appeared: check the workflow run; `--no-wait` releases are the usual cause of someone racing this |
