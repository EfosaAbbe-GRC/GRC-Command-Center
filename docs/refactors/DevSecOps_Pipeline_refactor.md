# DevSecOps pipeline: shift-left security gates, supply-chain pinning, change evidence

**Status:** DRAFT 2026-10-26, **revised the same day after a gap re-assessment (§11)**, awaiting
EXECUTE (GOVERNANCE.md §A). Needs **no Groq**, so it can run on a weekday. **Principle: shift left,
security first** (owner's standing rule): every gate is a test that fails before the fix, and
blocks merges after it.

**Why now:** the repo has **no CI at all**. Two outside prompts framed the gap:
- a LinkedIn GRC-engineering post: pipeline outputs as control evidence;
- Susan Shepard, *Build It in a Day, Own It Forever* (2026-10-19): a tool you build enters audit
  scope, so it needs its own IT general controls (change management, access, evidence integrity).

This draft makes Command Center produce that evidence **about itself**.

## 1. Gaps (verified 2026-10-26)

| ID | Gap | Evidence | Risk |
| --- | --- | --- | --- |
| G1 | **No CI** | no `.github/`, no workflow | every check depends on someone remembering to run it |
| G2 | **10 of 26 Python requirements unpinned** (`langchain*`, `sentence-transformers`, `sqlalchemy`, `asyncpg`, `numpy`…). The running image resolves to **153** packages. | `requirements.txt`; `pip freeze` | an image rebuild silently pulls newer versions. That's a supply-chain risk, **and a hidden benchmark variable** (already seen 2026-09-29: "rebuilds pull newer unpinned transitive deps") |
| G3 | **Base images pinned by tag, not digest:** `python:3.11-slim`, `node:20-alpine`, `nginx:alpine` (floating), `postgres:16-alpine`, `prodrigestivill/postgres-backup-local:16-alpine` | Dockerfiles, compose | the same tag can resolve to different contents |
| G4 | **The embedding model is downloaded at runtime, unpinned.** `rag.py` loads `HuggingFaceEmbeddings("all-MiniLM-L6-v2")` lazily on the **first question after each container start**, fetching the latest revision from Hugging Face. There's no revision pin, no local copy and no integrity check. | no model files anywhere in the container's filesystem after today's rebuild; the container reaches huggingface.co (HTTP 200); `rag.py:325–335` | **supply chain** (an upstream change or compromise alters every retrieval), **availability** (no internet, no RAG; a second loader hung on 2026-10-26), **reproducibility** (a silent benchmark variable). The FAISS index has a SHA-256 check; the model that reads it has none. |
| G5 | No SAST, no dependency-vulnerability scan, no image scan. **Dependabot is off.** | GitHub API, 2026-10-25 | known-vulnerable code ships unnoticed |
| G6 | **Secret scanning covers known token formats only.** GitHub push protection didn't (and wouldn't) catch the plain-text passwords removed on 2026-10-25. | that incident | the next generic secret gets pushed too |
| G7 | **`main` is unprotected;** commits go straight to it | GitHub API (404 on branch protection) | no enforced change record and no gate |
| G8 | **Tests aren't separated:** 4 unit files (`test_security_config`, `test_login_throttle`, `test_rag_grading`, `test_pii`) and 9 integration files that need the live stack, with no markers | file scan | CI can't run "the fast ones" |
| G9 | No SBOM, no build provenance | — | an auditor can't see what shipped |
| G10 | **The AI acts on GitHub as the owner.** Claude's `gh` session is the owner's own admin account. | `gh api user` | an AI-authored PR "approved" by the same identity isn't separation of duties; an admin token can also bypass any branch protection |
| G11 | **A second model is runtime-downloaded too:** the re-ranker `cross-encoder/ms-marco-MiniLM-L-6-v2` | `rag.py:351–352` | same as G4 |
| G12 | **The frontend healthcheck has never passed** (4,690 consecutive failures, ~39 h). `wget localhost` resolves to IPv6 `::1`; nginx listens on IPv4 only. The site itself serves fine (HTTP 200 on `127.0.0.1`). | `docker inspect` health log | a monitoring control that is always red is a blind one; a real outage would look identical |
| G13 | **The backend image is 7.46 GB:** `torch` ships with the full CUDA stack (15 `nvidia-*` packages + `triton`) on a CPU-only host, and `build-essential` (a compiler) stays in the runtime image | `pip freeze`; `Dockerfile.backend` | attack surface and CVE noise; the image may not fit a GitHub runner's ~14 GB free disk |
| G14 | **Public-repo basics missing:** no `SECURITY.md`; private vulnerability reporting off; secret scanning's non-provider (generic) patterns off | GitHub API | a finder has no private way to report; generic secrets go unflagged |
| G15 | **No container runtime hardening:** no `no-new-privileges`, no `cap_drop` | compose files | a compromised process keeps default Linux capabilities |

## 2. Design: four layers, cheapest first

| Layer | Where | Purpose |
| --- | --- | --- |
| **L0** | developer machine, before commit (optional `pre-commit`) | the fastest feedback: secrets and forbidden files never leave the laptop |
| **L1** | GitHub Actions on every PR and push to `main` | **the enforced gates** (§4) |
| **L2** | repository settings | gates can't be bypassed: branch protection, Dependabot |
| **L3** | scheduled weekly | new CVEs in unchanged code and images |

GitHub Actions is free for public repos. Nothing here calls Groq.

## 3. Phase 0: groundwork with no behaviour change (do first)

Each step is verified to change **nothing** at runtime, so the benchmark series stays comparable.

0. **Record the baseline first:** `pip freeze` of the running image (captured 2026-10-26, 153
   packages), the pytest count (README says 89 passed, 1 skipped; re-measured on execute), and
   the image size.
1. **Lock Python deps to exactly what runs today.** Rename the hand-written list to
   `backend/requirements.in` and compile it with pip-tools (`--generate-hashes`, constrained to
   the captured freeze) into a hashed `backend/requirements.txt`. That `.in`→`.txt` pair is the
   layout Dependabot's pip updater understands; a custom `requirements.lock` name would be
   skipped. **Compile inside `python:3.11-slim`, not on Windows**, because platform markers
   resolve differently. The Dockerfile installs `pip install --require-hashes -r requirements.txt`.
   **Verify:** `pip freeze` in the rebuilt image ≡ the baseline (empty diff).
2. **Pin base images by digest** (`image@sha256:…`). `postgres:16-alpine` and the backup image are
   still on this machine, so their in-use digests are pinned exactly. **Honest limit:**
   `python:3.11-slim`, `node:20-alpine` and `nginx:alpine` have been pruned locally, so the digest
   the current images were built from can't be recovered. Those three are pinned to today's
   registry digest, and Python is checked to still be 3.11.17. The Python packages are what
   matters for the benchmark, and those are hash-locked (step 1), but OS packages may differ.
   Dependabot (L2) proposes digest bumps as reviewable PRs instead of silent drift.
3. **Bake both models into the image at pinned revisions (fixes G4, G11):**
   - a build step `snapshot_download(<repo>, revision=<commit sha>)` into `/opt/models` for
     **`sentence-transformers/all-MiniLM-L6-v2` and `cross-encoder/ms-marco-MiniLM-L-6-v2`**;
   - `HF_HOME=/opt/models` and **`HF_HUB_OFFLINE=1` at runtime**, so the backend can't fetch
     models from the internet at all;
   - `rag.py` is unchanged (same model name), which keeps benchmark isolation;
   - the revision pinned is the one Hugging Face serves today. **Honest limit:** which revision
     v8–v11 used can't be proven after the fact. The model's `main` branch is believed stable, but
     that's unverified.
   - **Verify:** with outbound network blocked, the first question still works (test stack, no
     Groq needed for the embedding step); and the image's model files hash-match the pinned
     revision.
4. **Test markers (G8):** `pytestmark = pytest.mark.integration` in the 9 stack-dependent files;
   register the marker in `pyproject.toml`. CI runs `-m "not integration"`.
   **Trap found on re-assessment:** markers deselect tests *after* their modules are imported, and
   `tests/_creds.py` raises at import when there is no `.env` (by design: no fallback). In CI the 9
   integration modules would crash collection before the marker could skip them. Fix: integration
   modules get credentials from a fixture that resolves them lazily (still no fallback, still
   fails loudly when the stack is actually used), plus a unit test that collection succeeds with no
   `.env` present.
4a. **Small fixes with no runtime effect:**
   - frontend healthcheck `localhost` → `127.0.0.1` in `Dockerfile.frontend` and both compose
     files (G12);
   - backend: `security_opt: [no-new-privileges:true]` and `cap_drop: [ALL]` (it already runs as a
     non-root user and needs no capabilities) (G15);
   - backend: a multi-stage build so `build-essential` stays in the builder stage (G13); verified
     by the same empty `pip freeze` diff;
   - stale text: the backend image `LABEL` still says "Gemini 2.0 Flash RAG + RBAC + SQLite", and
     the single-worker comment cites SQLite. The real reason now is that the login throttle is
     in-memory and needs one worker.
   **Not in this change:** CPU-only `torch` would cut the image by gigabytes, but it changes the
   runtime numerics library, so it's a benchmark variable. It gets its own draft and benchmark
   check after the v12 verdict (2026-11-07).
5. **New policy tests: red first, then they guard** (unit, no stack):

| Test | Asserts | Guards |
| --- | --- | --- |
| `test_compose_policy.py::test_published_ports_are_loopback` | every `ports:` entry in both compose files starts with `127.0.0.1:` | 2026-10-25 S1 |
| `…::test_backend_runtime_hardening` | backend has `no-new-privileges` and `cap_drop: [ALL]` | G15 |
| `…::test_healthchecks_use_ipv4_loopback` | no healthcheck probes `localhost` | G12 |
| `test_collection_without_env` | the test suite collects with no `.env` present | the CI trap in step 4 |
| `…::test_secrets_are_required` | every `*PASSWORD*`, `*SECRET*`, `*API_KEY*` interpolation is `${VAR:?…}`, never `:-default` | S3 |
| `test_dockerignore_policy.py` | `.env` patterns are unanchored (`**/.env`); `**/*.db` excluded | S2 |
| `test_image_hygiene` (CI image job) | the built image has no `.env`, `*.db`, `tests/`; runs as non-root; model present; `HF_HUB_OFFLINE=1` | F3 + G4 |
| `test_golden_mappings_hygiene.py` | (from the v12 draft) no benchmark question copied into a trigger | benchmark integrity |
| `test_requirements_locked` | every requirement in the compiled `requirements.txt` is `==` with `--hash` | G2 |

## 4. Phase 1: the CI workflow (`.github/workflows/security.yml`)

Workflow default `permissions: contents: read` (the repo default is already read-only, verified).
Each job elevates only what it needs. **Every third-party action is pinned to a full commit SHA**
(a tag can be moved; an SHA can't). Also: `actions/checkout` with `persist-credentials: false`;
no `pull_request_target` trigger; outside contributors' PRs need approval before workflows run.

| Job | Tool | Blocks the merge when | Evidence produced |
| --- | --- | --- | --- |
| `secrets` | **gitleaks** (full history on the first run, diff after) | any **new** finding. The full-history run *will* find the passwords removed on 2026-10-25: git history keeps them. They are already public, rotated, and refused at startup by the deny-list, so they're recorded in a reviewed **baseline file** (one justification each), not a broad allowlist that could hide future ones. History isn't rewritten, since that wouldn't un-publish them. The deny-list strings in `security_config.py` and its tests are allowlisted per entry. | SARIF in the Security tab |
| `unit` | pytest `-m "not integration"`, Python 3.11 | any failure | JUnit report |
| `sast` | **CodeQL** (python, javascript-typescript), default + security-extended | a new high-severity alert | Security tab alerts |
| `deps` | **pip-audit** on `requirements.lock`; `npm audit --omit=dev` | CRITICAL/HIGH **with a fix available** | report artifact |
| `image` | free runner disk first (G13) → build both images (cache) → `test_image_hygiene` → **Trivy** image (vuln + secret + misconfig) + Trivy config (Dockerfiles, compose) | hygiene failure; secret finding; CRITICAL vuln with a fix | SARIF + JSON |
| `sbom` | Trivy → **CycloneDX SBOM** per image; **`actions/attest-build-provenance`** + `attest-sbom` | — (always produced) | signed attestations, SBOM artifacts (90-day retention) |

**Honest limit on attestations:** the images aren't published anywhere. The laptop builds its own,
so the attestations describe what *CI* built, not byte-for-byte what runs locally. The lock file
and digest pins make the two builds the same inputs; they don't make them the same artifact. The
real fix, "build once in CI, push to a registry, compose pulls by digest", is named in §7 for after
the image is slimmed.

**Image hygiene scope:** "runs as non-root" applies to the backend. The frontend's stock
`nginx:alpine` starts its master process as root, so it's a recorded exception with an expiry
until it moves to an unprivileged nginx image (§7).
| `frontend` | `npm ci` + `eslint` | lint errors | log |

**Exceptions are risk acceptances, not silence.** Any accepted finding goes in `.trivyignore` /
`.gitleaks.toml` with **an owner, a justification and an expiry date**, the same discipline as the
TPRM module's `risk_acceptances`. Expired entries fail the build. Trivy enforces expiry natively
(`exp:` in `.trivyignore`); gitleaks has no expiry field, so a small checker test reads the
owner, reason and expiry from each allowlist entry and fails on any missing or past date.

**Baseline policy:**
- secrets, unit, policy and hygiene gates **block from day one**;
- vulnerability gates block **CRITICAL-with-fix** from day one;
- HIGH is reported for the first week, reviewed with the owner, then promoted to blocking.

That avoids alert fatigue without leaving the gate open-ended.

## 5. Phase 2: repository guardrails (owner approves each; applied via `gh api`)

1. **Dependabot** alerts and security updates on. `.github/dependabot.yml` for pip, npm, docker and
   github-actions, weekly, grouped.
   **Benchmark rule:** a runtime dependency bump changes what the benchmark measures. So security
   fixes merge any time and are logged in the benchmark history; non-security bumps wait until
   between benchmark series (not during v12: 10-31 to 11-07).
2. **Branch protection on `main`:** require a PR; required status checks = the §4 jobs; 1
   approving review from a code owner; dismiss stale approvals; approval of the most recent push
   required; no force-push; no deletion; **admins included**. Break-glass means the owner
   temporarily lifts protection, which GitHub records in the audit log, and the reason is noted in
   `SESSION.md`.
3. **`CODEOWNERS`:** the owner owns `.github/`, `.gitleaks.toml`, `.trivyignore`, the policy
   tests, both Dockerfiles and both compose files. **That stops anyone, the AI included, from
   quietly weakening a gate in the same PR that would have failed it.**
4. **Public-repo basics (G14):** add `SECURITY.md` (how to report a vulnerability privately);
   turn on private vulnerability reporting and the generic (non-provider) secret-scanning
   patterns.
5. **Decision D1: the change flow.**
   - **(a) PR-based with a separate identity for the AI, recommended.** Re-assessment found the
     original wording overclaimed: Claude's `gh` login *is* the owner's admin account (G10), so a
     PR it opened would show the owner as author and approver, and its token could bypass
     protection. Real separation of duties needs **a second GitHub account for the AI** (GitHub
     allows one free machine account per person) with a **fine-grained token scoped to this one
     repo**: contents and pull requests write, no admin. It can push branches and open PRs; it
     can't approve its own PR, merge past protection, or change settings. Then the record is
     honest: the bot proposed, the owner approved, the checks passed. That's real CM-3 / AC-5
     evidence, and Shepard's "AI proposes, human commits" enforced by the platform. **Owner
     action:** create the account and token (about 10 minutes, guided).
   - **(a′) PR-based, same identity:** if the owner prefers not to create a second account, the
     PR flow still gives gates and a change record. But separation of duties is then
     **procedural** (commit trailers say who wrote what), not enforced, and the docs will say so.
   - **(b)** Keep direct pushes; checks run after the fact. A weaker gate: CI reports, but can't
     block.

## 6. Phase 3 (optional): local `pre-commit` (L0)

gitleaks + a block on committing `.env` / `*.db` / files over 5 MB + the unit tests. CI is the
enforced backstop; this only makes failures arrive sooner.

## 7. Later (named so they aren't forgotten)

- **Integration tests in CI.** They need a synthetic corpus and index fixture (the real corpus
  isn't in the repo, by design) and compose in CI with throwaway secrets. This is also where the
  database-hardening tests from the owner's pending security change will run.
- **L3 schedule:** a weekly Trivy rescan of the published images, so new CVEs appear in code that
  didn't change.
- **DAST:** an OWASP ZAP baseline scan against the test stack in CI.
- Signed commits.
- **CPU-only `torch`** (G13): its own draft with a benchmark check, after the v12 verdict.
- **Build once, deploy the same artifact:** CI pushes images to GHCR, compose pulls by digest, so
  the attestation covers what actually runs.
- **Frontend on an unprivileged nginx image**, which clears the non-root exception.
- **Egress allow-list:** once the models are baked in, the backend needs outbound access only to
  the Groq API. Restrict the rest (defense in depth).
- **OpenSSF Scorecard** as an outside measure of the repo's security practices.

## 8. Control evidence it produces (supports, does not by itself satisfy; mappings hand-reviewed)

| NIST SP 800-53 | Evidence from this pipeline |
| --- | --- |
| CM-3 Configuration change control | PR record: draft cited, checks passed, owner's merge (D1a) |
| AC-5 Separation of duties | bot identity authors, owner approves; enforced only under D1(a), procedural under D1(a′) |
| CM-2 / CM-6 Baseline and settings | policy tests on ports, secrets and images |
| CM-8 Component inventory | CycloneDX SBOM per build |
| RA-5 Vulnerability monitoring | Trivy, pip-audit, npm audit, Dependabot, CodeQL |
| SI-2 Flaw remediation | Dependabot PRs + expiring exceptions |
| SA-11 Developer testing | unit + policy tests + SAST on every change |
| SR-3 / SR-4 / SR-11 Supply chain, provenance | digest/hash pinning, pinned model revision, build-provenance attestations |
| IA-5(7) No embedded static authenticators | gitleaks with generic rules |
| AC-6 Least privilege | read-only default token; per-job permissions |

## 9. Verification: prove each gate fails before trusting that it passes

On a throwaway branch, open **deliberately bad PRs**. Each must go **red**, then be closed:

| Bad change | Gate that must fail |
| --- | --- |
| add `API_PASSWORD=Sup3rS3cret!x9` to a tracked file | `secrets` |
| change a compose port to `"8001:8001"` | `unit` (`test_published_ports_are_loopback`) |
| add a `:-defaultpw` fallback to a secret | `unit` (`test_secrets_are_required`) |
| copy benchmark #16 into a trigger | `unit` (golden hygiene) |
| remove `**/.env` from `.dockerignore` and add a dummy `backend/.env` | `image` (hygiene) |
| unpin a requirement | `unit` (`test_requirements_locked`) |
| change a workflow file from the bot account | merge blocked until code-owner review (`CODEOWNERS`) |
| the bot tries to approve or merge its own PR | refused by the platform (D1a only) |
| add an exception with a past expiry date | `unit` (exception checker) |

Then:
- one clean PR goes fully green;
- **after Phase 0:** `pip freeze` diff is empty; **both** models work with egress blocked; the
  pytest count equals the recorded baseline plus the new tests; readiness is ready; the frontend
  shows **healthy**.

## 10. Order and timing

**Phase 0 → 1 → 2 this week (no Groq).** Then **Saturday's security change becomes the first change
to go through the pipeline as a PR**, which proves the gates on a real change.

Phase 0 rebuilds the images, but with identical Python packages and models pinned to the revision
served today (verified, §3), so the v12 benchmark series isn't disturbed. If the bot account
(D1a) isn't ready by Saturday, Saturday's change goes in under documented break-glass rather than
waiting.

## 11. Re-assessment log (2026-10-26, before any execution)

The owner asked for a gap check before EXECUTE. Read-only checks against the live system found:

| # | Finding | Draft change |
| --- | --- | --- |
| 1 | D1 overclaimed: the AI's GitHub identity is the owner's admin account | G10; D1 split into (a)/(a′); AC-5 row; `CODEOWNERS` |
| 2 | A second runtime-downloaded model (re-ranker) | G11; step 3 covers both |
| 3 | CI would crash at test collection (`_creds` raises at import) | step 4 trap + fix + guard test |
| 4 | Frontend healthcheck failing for ~39 h (IPv6 `localhost`) | G12; step 4a; policy test |
| 5 | Three base-image digests unrecoverable (pruned locally) | step 2 honest limit |
| 6 | 7.46 GB image: CUDA torch + compiler in runtime | G13; multi-stage now; CPU torch later |
| 7 | A `requirements.lock` name that Dependabot wouldn't update | step 1: `.in` → `.txt` |
| 8 | gitleaks' first run would go red on already-public history | baseline file, not allowlist |
| 9 | gitleaks has no expiry field, so "expired fails" was unenforceable | checker test |
| 10 | Dependabot bumps would silently move the benchmark | benchmark rule in §5 |
| 11 | Attestations overclaimed: they describe CI's build, not the laptop's | honest limit + §7 |
| 12 | No `SECURITY.md`, private reporting off, generic secret patterns off | G14; §5 item 4 |
| 13 | No `no-new-privileges` / `cap_drop` | G15; step 4a |
| 14 | Stale facts: test count (77 vs README 89), "Gemini … SQLite" label | step 0; step 4a |

## Rollback

Workflow and policy files: `git revert`. Branch protection: `gh api` removal (owner). Lock and
digest pinning: revert plus rebuild returns to tag- and range-based resolution (not recommended).
