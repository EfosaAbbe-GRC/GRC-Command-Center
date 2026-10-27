"""Bake the two Hugging Face models into the backend image at pinned revisions.

Runs at image build time only. The backend then runs with HF_HUB_OFFLINE=1, so it can't
fetch a model from the internet at all. Before 2026-10-26 both models were downloaded,
unpinned, on the first question after every container start (DevSecOps_Pipeline_refactor.md,
gaps G4 and G11).

Pins are each repo's `main` commit on 2026-10-26. `main` last changed 2026-06-01 (embedder)
and 2026-08-09 (re-ranker), so every benchmark from v8 (2026-09-27) on used these revisions.
To move a pin: update the revision and weight hash together, in a reviewed change, and treat
it as a benchmark variable.
"""
import hashlib
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

# repo -> (commit, sha256 of model.safetensors as published in the repo's LFS pointer)
MODELS = {
    "sentence-transformers/all-MiniLM-L6-v2": (
        "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
        "53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db",
    ),
    "cross-encoder/ms-marco-MiniLM-L-6-v2": (
        "233902d25c440f23af6f7d6e94d2946bac0bee0a",
        "821d1aa69520101d6e0737f78a042ae25b19e5cb9160701909d10434f4aeb0ae",
    ),
}

# The repos also carry the same weights as ONNX, OpenVINO, TF, Flax, Rust and pickle files.
# sentence-transformers loads model.safetensors; skipping the rest also avoids pickle (.bin).
IGNORE = ["onnx/*", "openvino/*", "*.h5", "*.msgpack", "*.ot", "pytorch_model.bin"]


def main() -> None:
    for repo, (revision, weights_sha256) in MODELS.items():
        path = Path(snapshot_download(repo, revision=revision, ignore_patterns=IGNORE))
        got = hashlib.sha256((path / "model.safetensors").read_bytes()).hexdigest()
        if got != weights_sha256:
            sys.exit(f"{repo}: model.safetensors sha256 {got} != pinned {weights_sha256}")
        # The app loads each model by name with no revision, which means "main". Offline, the
        # hub resolves "main" through refs/main, and a by-commit download doesn't write it.
        ref = path.parents[1] / "refs" / "main"
        ref.parent.mkdir(parents=True, exist_ok=True)
        ref.write_text(revision)
        print(f"baked {repo}@{revision}")


if __name__ == "__main__":
    main()
