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
        mock_sg.find_one.return_value = None  # No existing admin policy

        result = runner.invoke(
            cli,
            ["init", "--base-url", "https://t.sg.com", "--script-name", "s", "--api-key", "k"],
        )

        assert result.exit_code == 0
        assert "Created 6 field(s)" in result.output
        assert mock_sg.schema_field_create.call_count == 6
        # Should also seed admin policy
        mock_sg.create.assert_called_once()
        assert "Seeded default admin policy" in result.output

    def test_skips_existing_fields(self, mock_sg, runner, mocker):
        mocker.patch("shotgrid_casbin_adapter.cli._get_sg", return_value=mock_sg)
        mock_sg.schema_field_read.return_value = {
            "sg_ptype": {},
            "code": {},
            "sg_v1": {},
            "sg_v2": {},
            "sg_v3": {},
            "sg_v4": {},
            "sg_v5": {},
        }
        mock_sg.find_one.return_value = None  # No existing admin policy

        result = runner.invoke(
            cli,
            ["init", "--base-url", "https://t.sg.com", "--script-name", "s", "--api-key", "k"],
        )

        assert result.exit_code == 0
        assert "Created 0 field(s)" in result.output
        assert "skipped 6 existing" in result.output
        mock_sg.schema_field_create.assert_not_called()
        # Admin policy still seeded
        mock_sg.create.assert_called_once()

    def test_custom_entity_type(self, mock_sg, runner, mocker):
        mocker.patch("shotgrid_casbin_adapter.cli._get_sg", return_value=mock_sg)
        mock_sg.schema_field_read.return_value = {}
        mock_sg.find_one.return_value = None

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
        mock_sg.find_one.return_value = None

        result = runner.invoke(
            cli,
            ["init", "--base-url", "https://t.sg.com", "--script-name", "s", "--api-key", "k"],
        )

        assert result.exit_code == 0
        assert DEFAULT_ENTITY_TYPE in result.output

    def test_project_id_option(self, mock_sg, runner, mocker):
        mocker.patch("shotgrid_casbin_adapter.cli._get_sg", return_value=mock_sg)
        mock_sg.schema_field_read.return_value = {}
        mock_sg.find_one.return_value = None

        result = runner.invoke(
            cli,
            ["init", "--base-url", "https://t.sg.com", "--script-name", "s", "--api-key", "k", "--project-id", "42"],
        )

        assert result.exit_code == 0
        assert "project 42" in result.output
        # Verify create was called with project data
        create_call_data = mock_sg.create.call_args[0][1]
        assert create_call_data["project"] == {"type": "Project", "id": 42}

    def test_admin_policy_seeded(self, mock_sg, runner, mocker):
        mocker.patch("shotgrid_casbin_adapter.cli._get_sg", return_value=mock_sg)
        mock_sg.schema_field_read.return_value = {}
        mock_sg.find_one.return_value = None

        result = runner.invoke(
            cli,
            ["init", "--base-url", "https://t.sg.com", "--script-name", "s", "--api-key", "k"],
        )

        assert result.exit_code == 0
        create_call_data = mock_sg.create.call_args[0][1]
        assert create_call_data["sg_ptype"] == "p"
        assert create_call_data["code"] == "admin"
        assert create_call_data["sg_v1"] == "*"
        assert create_call_data["sg_v2"] == "*"

    def test_admin_policy_skipped_if_exists(self, mock_sg, runner, mocker):
        mocker.patch("shotgrid_casbin_adapter.cli._get_sg", return_value=mock_sg)
        mock_sg.schema_field_read.return_value = {}
        mock_sg.find_one.return_value = {"id": 1, "type": "CustomEntity01"}  # Admin policy already exists

        result = runner.invoke(
            cli,
            ["init", "--base-url", "https://t.sg.com", "--script-name", "s", "--api-key", "k"],
        )

        assert result.exit_code == 0
        mock_sg.create.assert_not_called()
        assert "already exists, skipping" in result.output

    def test_missing_url_fails(self, runner, mocker):
        mocker.patch.dict(os.environ, {}, clear=True)
        result = runner.invoke(cli, ["init"])
        assert result.exit_code != 0

    def test_env_vars(self, mock_sg, runner, mocker):
        mocker.patch("shotgrid_casbin_adapter.cli._get_sg", return_value=mock_sg)
        mock_sg.schema_field_read.return_value = {}
        mock_sg.find_one.return_value = None
        mocker.patch.dict(
            os.environ,
            {SHOTGRID_URL: "https://t.sg.com", SHOTGRID_SCRIPT_NAME: "s", SHOTGRID_API_KEY: "k"},
            clear=True,
        )

        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0
