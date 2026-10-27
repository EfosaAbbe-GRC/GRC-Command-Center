"""Inspects a BUILT backend image: what shipped, not what the Dockerfile says should ship.

Set GRC_IMAGE to the image to check (CI's image job does this); skipped otherwise:
    GRC_IMAGE=grc_command_center-backend python -m pytest -q -m image tests/test_image_hygiene.py
Needs only docker, no stack and no secrets. Guards S2 (.env baked into /app until 2026-10-25),
F3, and G4/G11 (models fetched at runtime) in DevSecOps_Pipeline_refactor.md.
"""
import os
import subprocess
import uuid

import pytest

IMAGE = os.environ.get("GRC_IMAGE")
pytestmark = [
    pytest.mark.image,
    pytest.mark.skipif(not IMAGE, reason="set GRC_IMAGE to a built backend image"),
]


def _run(*cmd):
    """(exit code, stdout, stderr) of a command in a throwaway container with no network."""
    # Named so a timeout can remove it: killing the docker CLI leaves the container running.
    name = f"grc-image-test-{uuid.uuid4().hex[:12]}"
    try:
        r = subprocess.run(["docker", "run", "--rm", "--name", name, "--network", "none",
                            "--entrypoint", cmd[0], IMAGE, *cmd[1:]], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=600)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True)
        raise
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def test_no_secrets_databases_or_tests_in_image():
    rc, out, err = _run("sh", "-c", "find /app \\( -name '.env' -o -name '*.env' -o -name '*.db' "
                                    "-o -name 'tests' \\) -print")
    assert rc == 0, err
    assert out == "", f"must not ship: {out}"


def test_runs_as_non_root():
    rc, out, err = _run("id", "-u")
    assert rc == 0 and out != "0", out + err


def test_no_compiler_in_runtime_image():
    rc, out, err = _run("sh", "-c", "command -v gcc cc g++ || true")
    assert out == "", f"compiler present: {out}"


def test_models_load_with_no_network():
    """--network none: if either model needed the internet, this fails."""
    code = ("import os; assert os.environ['HF_HUB_OFFLINE'] == '1';"
            "from langchain_huggingface import HuggingFaceEmbeddings;"
            "from sentence_transformers import CrossEncoder;"
            "v = HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2').embed_query('access control');"
            "s = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2').predict([('a', 'b')]);"
            "print(len(v), len(s))")
    rc, out, err = _run("python", "-c", code)
    assert rc == 0, err
    assert out.splitlines()[-1] == "384 1", out + err
    # The hub degrades quietly on an unreadable cache file; treat that as a broken bake.
    assert "Permission denied" not in err, err


def test_pii_redaction_works_in_image():
    """2026-10-26: a rebuild pulled a yanked spaCy dependency and every redact() call raised,
    so every question was refused. Nothing short of running it in the built image catches that."""
    code = ("from core import pii; pii.warm_up(); s = pii.status(); print(s['status']);"
            "print(pii.redact('Our vendor contact Maria Gonzalez replied')[0])")
    rc, out, err = _run("python", "-c", code)
    assert rc == 0, err
    assert out.splitlines()[-2:] == ["ready", "Our vendor contact [PERSON] replied"], out + err
