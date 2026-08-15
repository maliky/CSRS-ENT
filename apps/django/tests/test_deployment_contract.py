from pathlib import Path


def test_first_preproduction_deploy_depends_only_on_local_health() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    script = (
        repository_root
        / "infrastructure"
        / "deploy"
        / "csrs-ent-preprod-deploy-root"
    ).read_text(encoding="utf-8")

    assert "http://127.0.0.1:18007/healthz/" in script
    assert "http://127.0.0.1:18007/readyz/" in script
    assert "https://preprod.ent.koba.sarl" not in script
