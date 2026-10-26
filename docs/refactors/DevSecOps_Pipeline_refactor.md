# DevSecOps pipeline: shift-left security gates, supply-chain pinning, change evidence

**Status:** DRAFT 2026-10-26, awaiting EXECUTE (GOVERNANCE.md §A). Needs **no Groq**, so it can run
on a weekday. **Principle: shift left, security first** (owner's standing rule): every gate is a
test that fails before the fix, and blocks merges after it.

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

1. **Lock Python deps to exactly what runs today.** Generate `backend/requirements.lock` from the
   current image's `pip freeze` (153 packages), with `--generate-hashes` via pip-tools. The
   Dockerfile installs `pip install --require-hashes -r requirements.lock`.
   **Verify:** `pip freeze` in the rebuilt image ≡ the pre-change freeze (empty diff).
2. **Pin base images by digest** (`image@sha256:…`), using the digests of the images in use
   today. Dependabot (L2) proposes digest bumps as reviewable PRs instead of silent drift.
3. **Bake the embedding model into the image at a pinned revision (fixes G4):**
   - a build step `snapshot_download("sentence-transformers/all-MiniLM-L6-v2", revision=<commit
     sha>)` into `/opt/models`;
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
5. **New policy tests: red first, then they guard** (unit, no stack):

| Test | Asserts | Guards |
| --- | --- | --- |
| `test_compose_policy.py::test_published_ports_are_loopback` | every `ports:` entry in both compose files starts with `127.0.0.1:` | 2026-10-25 S1 |
| `…::test_secrets_are_required` | every `*PASSWORD*`, `*SECRET*`, `*API_KEY*` interpolation is `${VAR:?…}`, never `:-default` | S3 |
| `test_dockerignore_policy.py` | `.env` patterns are unanchored (`**/.env`); `**/*.db` excluded | S2 |
| `test_image_hygiene` (CI image job) | the built image has no `.env`, `*.db`, `tests/`; runs as non-root; model present; `HF_HUB_OFFLINE=1` | F3 + G4 |
| `test_golden_mappings_hygiene.py` | (from the v12 draft) no benchmark question copied into a trigger | benchmark integrity |
| `test_requirements_locked` | every line in `requirements.lock` is `==` with `--hash` | G2 |

## 4. Phase 1: the CI workflow (`.github/workflows/security.yml`)

Workflow default `permissions: contents: read`. Each job elevates only what it needs. **Every
third-party action is pinned to a full commit SHA** (a tag can be moved; an SHA can't).

| Job | Tool | Blocks the merge when | Evidence produced |
| --- | --- | --- | --- |
| `secrets` | **gitleaks** (full history on the first run, diff after) | any finding. The deny-list strings in `security_config.py` and its tests are allowlisted in `.gitleaks.toml`, one justification per entry. | SARIF in the Security tab |
| `unit` | pytest `-m "not integration"`, Python 3.11 | any failure | JUnit report |
| `sast` | **CodeQL** (python, javascript-typescript), default + security-extended | a new high-severity alert | Security tab alerts |
| `deps` | **pip-audit** on `requirements.lock`; `npm audit --omit=dev` | CRITICAL/HIGH **with a fix available** | report artifact |
| `image` | build both images (cache) → `test_image_hygiene` → **Trivy** image (vuln + secret + misconfig) + Trivy config (Dockerfiles, compose) | hygiene failure; secret finding; CRITICAL vuln with a fix | SARIF + JSON |
| `sbom` | Trivy → **CycloneDX SBOM** per image; **`actions/attest-build-provenance`** + `attest-sbom` | — (always produced) | signed attestations, SBOM artifacts (90-day retention) |
| `frontend` | `npm ci` + `eslint` | lint errors | log |

**Exceptions are risk acceptances, not silence.** Any accepted finding goes in `.trivyignore` /
`.gitleaks.toml` with **an owner, a justification and an expiry date**, the same discipline as the
TPRM module's `risk_acceptances`. Expired entries fail the build.

**Baseline policy:**
- secrets, unit, policy and hygiene gates **block from day one**;
- vulnerability gates block **CRITICAL-with-fix** from day one;
- HIGH is reported for the first week, reviewed with the owner, then promoted to blocking.

That avoids alert fatigue without leaving the gate open-ended.

## 5. Phase 2: repository guardrails (owner approves each; applied via `gh api`)

1. **Dependabot** alerts and security updates on. `.github/dependabot.yml` for pip, npm, docker and
   github-actions, weekly, grouped.
2. **Branch protection on `main`:** required status checks = the §4 jobs; no force-push; no
   deletion. Admin enforcement stays off only as documented break-glass.
3. **Decision D1: the change flow.**
   - **(a) PR-based, recommended.** Claude opens a PR that cites its approved draft, the checks
     run, and **the owner merges**. That gives real CM-3 evidence (who proposed, who approved,
     which checks passed) and a genuine **separation of duties: the AI authors, the human
     approves.** It's Shepard's "AI proposes, human commits", enforced by the platform instead of
     by habit.
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

## 8. Control evidence it produces (supports, does not by itself satisfy; mappings hand-reviewed)

| NIST SP 800-53 | Evidence from this pipeline |
| --- | --- |
| CM-3 Configuration change control | PR record: draft cited, checks passed, owner's merge (D1a) |
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

Then:
- one clean PR goes fully green;
- **after Phase 0:** `pip freeze` diff is empty, the model works with egress blocked, pytest is
  unchanged (77 + 1 skipped plus the new tests), and readiness is ready.

## 10. Order and timing

**Phase 0 → 1 → 2 this week (no Groq).** Then **Saturday's security change becomes the first change
to go through the pipeline as a PR**, which proves the gates on a real change.

Phase 0 rebuilds the images, but with identical packages and the same model revision (verified,
§3), so the v12 benchmark series isn't disturbed.

## Rollback

Workflow and policy files: `git revert`. Branch protection: `gh api` removal (owner). Lock and
digest pinning: revert plus rebuild returns to tag- and range-based resolution (not recommended).
