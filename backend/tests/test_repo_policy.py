"""Repository security policy: the 2026-10-25/26 fixes, turned into rules that fail the build.

Unit tests, no stack and no secrets: they read the compose files, Dockerfiles, .dockerignore
and the lock file. Each rule names the incident or gap it guards (Security_Hardening_refactor.md,
DevSecOps_Pipeline_refactor.md). Loosening one is a reviewed change, never a quiet edit.
"""
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILES = ["docker-compose-v2.yml", "docker-compose.test.yml"]
DOCKERFILES = ["Dockerfile.backend", "Dockerfile.frontend"]
BACKEND_SERVICES = {"docker-compose-v2.yml": "backend", "docker-compose.test.yml": "backend-test"}
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")


def _compose(name):
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


def _instructions(dockerfile):
    """Dockerfile instructions with line continuations joined, comments dropped."""
    text = (ROOT / dockerfile).read_text(encoding="utf-8")
    lines = [l for l in text.splitlines() if not l.lstrip().startswith("#")]
    return [i.strip() for i in re.sub(r"\\\n", " ", "\n".join(lines)).splitlines() if i.strip()]


# ── Network exposure (2026-10-25 S1: ports were published on every interface) ──
@pytest.mark.parametrize("compose", COMPOSE_FILES)
def test_published_ports_are_loopback(compose):
    for name, svc in _compose(compose)["services"].items():
        for port in svc.get("ports", []):
            assert str(port).startswith("127.0.0.1:"), f"{compose}:{name} publishes {port}"


# ── Secrets (S3: published default passwords) ──────────────────────────────────
@pytest.mark.parametrize("compose", COMPOSE_FILES)
def test_secrets_are_required(compose):
    text = (ROOT / compose).read_text(encoding="utf-8")
    refs = re.findall(r"\$\{([A-Z0-9_]+)(:?[-?+]?)", text)
    secret = [(v, op) for v, op in refs if re.search(r"PASSWORD|SECRET|API_KEY|TOKEN", v)]
    assert secret, "expected secret interpolations to check"
    for var, op in secret:
        assert op == ":?", f"{compose}: ${{{var}}} must be ${{{var}:?...}}, never defaulted"


# ── Runtime hardening (G15) ─────────────────────────────────────────────────────
@pytest.mark.parametrize("compose", COMPOSE_FILES)
def test_backend_runtime_hardening(compose):
    svc = _compose(compose)["services"][BACKEND_SERVICES[compose]]
    assert "no-new-privileges:true" in svc.get("security_opt", [])
    assert svc.get("cap_drop") == ["ALL"]
    # uvicorn as PID 1 doesn't reap exited children; on 2026-10-27 one left the test container
    # unstoppable until Docker force-killed it. `init` runs a reaper as PID 1.
    assert svc.get("init") is True


# ── Healthchecks (G12: `localhost` hit IPv6 ::1 and failed for ~39 h) ─────────────
@pytest.mark.parametrize("compose", COMPOSE_FILES)
def test_compose_healthchecks_avoid_localhost(compose):
    for name, svc in _compose(compose)["services"].items():
        probe = " ".join(svc.get("healthcheck", {}).get("test", []))
        assert "localhost" not in probe, f"{compose}:{name} healthcheck probes localhost"


@pytest.mark.parametrize("dockerfile", DOCKERFILES)
def test_dockerfile_healthchecks_avoid_localhost(dockerfile):
    for ins in _instructions(dockerfile):
        if ins.startswith("HEALTHCHECK"):
            assert "localhost" not in ins, f"{dockerfile}: {ins}"


# ── Supply chain (G2, G3, G4) ───────────────────────────────────────────────────
@pytest.mark.parametrize("compose", COMPOSE_FILES)
def test_compose_images_pinned_by_digest(compose):
    for name, svc in _compose(compose)["services"].items():
        if "image" in svc:
            assert DIGEST.search(svc["image"]), f"{compose}:{name} image not digest-pinned"


@pytest.mark.parametrize("dockerfile", DOCKERFILES)
def test_dockerfile_bases_pinned_by_digest(dockerfile):
    froms = [i.split()[1] for i in _instructions(dockerfile) if i.startswith("FROM ")]
    assert froms
    for image in froms:
        assert DIGEST.search(image), f"{dockerfile}: FROM {image} not digest-pinned"


def test_requirements_locked():
    """Every requirement is an exact pin (or a hashed URL) with a hash; no index overrides."""
    text = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    entries = [e.strip() for e in re.sub(r"\\\n", " ", text).splitlines()
               if e.strip() and not e.lstrip().startswith("#")]
    assert len(entries) > 100, "expected the compiled lock, not the top-level list"
    for entry in entries:
        assert not entry.startswith("-"), f"option line not allowed in the lock: {entry}"
        spec = entry.split(" --hash")[0].split(";")[0].strip()
        assert re.fullmatch(r"[A-Za-z0-9_.\-]+==[^\s=]+", spec) or " @ https://" in spec, spec
        assert "--hash=sha256:" in entry, f"no hash: {spec}"


def test_backend_image_installs_with_hashes_and_runs_offline():
    ins = _instructions("Dockerfile.backend")
    assert any("--require-hashes" in i and "requirements.txt" in i for i in ins)
    assert "ENV HF_HUB_OFFLINE=1" in ins


# ── Build context (S2: .env baked into the image until 2026-10-25) ───────────────
def test_dockerignore_excludes_secrets_and_databases():
    patterns = {l.strip() for l in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()}
    for required in ("**/.env", "**/*.env", "**/*.db", "backend/tests/"):
        assert required in patterns, f".dockerignore lacks {required}"
