"""Tests for the ShotGrid Casbin Adapter CLI module."""

# ruff: noqa: D102

import os

import pytest
from click.testing import CliRunner
from shotgun_api3.shotgun import Fault

from shotgrid_casbin_adapter.cli import cli
from shotgrid_casbin_adapter.constants import DEFAULT_ENTITY_TYPE
from shotgrid_casbin_adapter.constants import SHOTGRID_API_KEY
from shotgrid_casbin_adapter.constants import SHOTGRID_SCRIPT_NAME
from shotgrid_casbin_adapter.constants import SHOTGRID_URL


@pytest.fixture
def mock_sg(mocker):
    """Fixture providing a mocked shotgun_api3.Shotgun instance."""
    return mocker.MagicMock()


@pytest.fixture
def runner():
    """Fixture providing a Click test runner."""
    return CliRunner()


class TestInitCommand:
    """Tests for the 'init' CLI command."""

    def test_creates_fields(self, mock_sg, runner, mocker):
        mocker.patch("shotgrid_casbin_adapter.cli._get_sg", return_value=mock_sg)
        mock_sg.schema_field_read.return_value = {}

        result = runner.invoke(
            cli,
            ["init", "--base-url", "https://t.sg.com", "--script-name", "s", "--api-key", "k"],
        )

        assert result.exit_code == 0
        assert "Created 7 field(s)" in result.output
        assert mock_sg.schema_field_create.call_count == 7

    def test_skips_existing_fields(self, mock_sg, runner, mocker):
        mocker.patch("shotgrid_casbin_adapter.cli._get_sg", return_value=mock_sg)
        mock_sg.schema_field_read.return_value = {
            "ptype": {},
            "v0": {},
            "v1": {},
            "v2": {},
            "v3": {},
            "v4": {},
            "v5": {},
        }

        result = runner.invoke(
            cli,
            ["init", "--base-url", "https://t.sg.com", "--script-name", "s", "--api-key", "k"],
        )

        assert result.exit_code == 0
        assert "Created 0 field(s)" in result.output
        assert "skipped 7 existing" in result.output
        mock_sg.schema_field_create.assert_not_called()

    def test_custom_entity_type(self, mock_sg, runner, mocker):
        mocker.patch("shotgrid_casbin_adapter.cli._get_sg", return_value=mock_sg)
        mock_sg.schema_field_read.return_value = {}

        result = runner.invoke(
            cli,
            [
                "init",
                "--base-url",
                "https://t.sg.com",
                "--script-name",
                "s",
                "--api-key",
                "k",
                "--entity-type",
                "CustomEntity01",
            ],
        )

        assert result.exit_code == 0
        assert "CustomEntity01" in result.output

    def test_invalid_entity_type(self, mock_sg, runner, mocker):
        mocker.patch("shotgrid_casbin_adapter.cli._get_sg", return_value=mock_sg)
        mock_sg.schema_field_read.side_effect = Fault("invalid entity type")

        result = runner.invoke(
            cli,
            [
                "init",
                "--base-url",
                "https://t.sg.com",
                "--script-name",
                "s",
                "--api-key",
                "k",
                "--entity-type",
                "BogusType",
            ],
        )

        assert result.exit_code != 0
        assert "BogusType" in result.output
        assert "Site Preferences" in result.output

    def test_default_entity_type(self, mock_sg, runner, mocker):
        mocker.patch("shotgrid_casbin_adapter.cli._get_sg", return_value=mock_sg)
        mock_sg.schema_field_read.return_value = {}

        result = runner.invoke(
            cli,
            ["init", "--base-url", "https://t.sg.com", "--script-name", "s", "--api-key", "k"],
        )

        assert result.exit_code == 0
        assert DEFAULT_ENTITY_TYPE in result.output

    def test_missing_url_fails(self, runner, mocker):
        mocker.patch.dict(os.environ, {}, clear=True)
        result = runner.invoke(cli, ["init"])
        assert result.exit_code != 0

    def test_env_vars(self, mock_sg, runner, mocker):
        mocker.patch("shotgrid_casbin_adapter.cli._get_sg", return_value=mock_sg)
        mock_sg.schema_field_read.return_value = {}
        mocker.patch.dict(
            os.environ,
            {SHOTGRID_URL: "https://t.sg.com", SHOTGRID_SCRIPT_NAME: "s", SHOTGRID_API_KEY: "k"},
            clear=True,
        )

        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0
