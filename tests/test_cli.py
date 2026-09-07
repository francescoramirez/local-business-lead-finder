from __future__ import annotations

from typer.testing import CliRunner

from leadfinder.cli import app

runner = CliRunner()


def test_help_lists_main_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "search" in result.stdout
    assert "dry-run" in result.stdout
    assert "presets" in result.stdout
    assert "gui" in result.stdout
    assert "analyze" in result.stdout
    assert "stats" in result.stdout
    assert "backup" in result.stdout
    assert "analytics" in result.stdout
    assert "campaigns" in result.stdout
    assert "insights" in result.stdout
    assert "experiments" in result.stdout
    assert "doctor" in result.stdout
    assert "templates" in result.stdout
    assert "costs" in result.stdout
    assert "demo-data" in result.stdout


def test_presets_lists_business_types() -> None:
    result = runner.invoke(app, ["presets"])
    assert result.exit_code == 0
    assert "cafe" in result.stdout
    assert "electrician" in result.stdout


def test_dry_run_works_without_api_key() -> None:
    result = runner.invoke(
        app,
        [
            "dry-run",
            "--business",
            "cafe",
            "--location",
            "Mar del Plata",
            "--country",
            "AR",
            "--region",
            "Buenos Aires",
            "--fields",
            "enterprise",
        ],
    )
    assert result.exit_code == 0
    assert "Text Search Enterprise" in result.stdout
    assert "Mar del Plata" in result.stdout
    assert "No API requests were made" in result.stdout
    assert "Estimated list cost" in result.stdout
    assert "page(s)" in result.stdout


def test_analyze_classifies_social_without_http() -> None:
    result = runner.invoke(app, ["analyze", "https://instagram.com/example"])
    assert result.exit_code == 0
    assert "Social" in result.stdout
    assert "instagram" in result.stdout.lower()


def test_dry_run_cordoba_is_not_buenos_aires() -> None:
    result = runner.invoke(
        app,
        [
            "dry-run",
            "--business",
            "cafe",
            "--location",
            "Cordoba",
            "--region",
            "Cordoba",
            "--country",
            "AR",
        ],
    )
    assert result.exit_code == 0
    assert "Cordoba" in result.stdout
    assert "Buenos Aires" not in result.stdout


def test_version_and_offline_commands() -> None:
    from leadfinder import __version__

    version = runner.invoke(app, ["--version"])
    assert version.exit_code == 0
    assert __version__ in version.stdout
    insights = runner.invoke(app, ["insights", "--days", "90"])
    assert insights.exit_code == 0
    experiments = runner.invoke(app, ["experiments"])
    assert experiments.exit_code == 0
    doctor = runner.invoke(app, ["doctor"])
    assert doctor.exit_code in {0, 1}
    assert "LeadFinder Doctor" in doctor.stdout
    assert "gsk_" not in doctor.stdout.lower()
