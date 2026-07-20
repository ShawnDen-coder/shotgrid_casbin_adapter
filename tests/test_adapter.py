"""Tests for the ShotGrid Casbin Adapter core module."""

# ruff: noqa: D102

import os

import pytest

from shotgrid_casbin_adapter.constants import CASBIN_FIELDS
from shotgrid_casbin_adapter.constants import DEFAULT_ENTITY_TYPE
from shotgrid_casbin_adapter.constants import SHOTGRID_API_KEY
from shotgrid_casbin_adapter.constants import SHOTGRID_PROJECT_ID
from shotgrid_casbin_adapter.constants import SHOTGRID_SCRIPT_NAME
from shotgrid_casbin_adapter.constants import SHOTGRID_URL
from shotgrid_casbin_adapter.core import Adapter
from shotgrid_casbin_adapter.filter import Filter
from shotgrid_casbin_adapter.filter import _build_sg_filters
from shotgrid_casbin_adapter.helpers import _build_rule_filters
from shotgrid_casbin_adapter.helpers import _entity_to_str
from shotgrid_casbin_adapter.helpers import _project_data
from shotgrid_casbin_adapter.helpers import _project_filter
from shotgrid_casbin_adapter.helpers import _rule_to_dict


# --- Helper function tests ---


class TestRuleToDict:
    """Tests for _rule_to_dict."""

    def test_basic_rule(self):
        assert _rule_to_dict("p", ["alice", "data1", "read"]) == {
            "sg_ptype": "p",
            "sg_v0": "alice",
            "sg_v1": "data1",
            "sg_v2": "read",
        }

    def test_short_rule(self):
        assert _rule_to_dict("g", ["alice", "admin"]) == {"sg_ptype": "g", "sg_v0": "alice", "sg_v1": "admin"}

    def test_empty_rule(self):
        assert _rule_to_dict("p", []) == {"sg_ptype": "p"}

    def test_with_project_id(self):
        result = _rule_to_dict("p", ["alice", "data1", "read"], project_id=42)
        assert result == {
            "sg_ptype": "p",
            "sg_v0": "alice",
            "sg_v1": "data1",
            "sg_v2": "read",
            "project": {"type": "Project", "id": 42},
        }

    def test_without_project_id(self):
        result = _rule_to_dict("p", ["alice"], project_id=None)
        assert "project" not in result


class TestEntityToStr:
    """Tests for _entity_to_str."""

    def test_full_entity(self):
        entity = {
            "sg_ptype": "p",
            "sg_v0": "alice",
            "sg_v1": "data1",
            "sg_v2": "read",
            "sg_v3": None,
            "sg_v4": None,
            "sg_v5": None,
        }
        assert _entity_to_str(entity) == "p, alice, data1, read"

    def test_short_entity(self):
        entity = {"sg_ptype": "g", "sg_v0": "alice", "sg_v1": "admin", "sg_v2": None}
        assert _entity_to_str(entity) == "g, alice, admin"

    def test_ptype_only(self):
        assert _entity_to_str({"sg_ptype": "p", "sg_v0": None}) == "p"


class TestBuildSgFilters:
    """Tests for _build_sg_filters."""

    def test_empty_filter(self):
        assert _build_sg_filters(Filter()) == []

    def test_ptype_filter(self):
        f = Filter()
        f.ptype = ["p"]
        assert _build_sg_filters(f) == [["sg_ptype", "in", ["p"]]]

    def test_multiple_fields(self):
        f = Filter()
        f.ptype = ["p"]
        f.v0 = ["alice", "bob"]
        assert _build_sg_filters(f) == [["sg_ptype", "in", ["p"]], ["sg_v0", "in", ["alice", "bob"]]]


class TestProjectFilter:
    """Tests for _project_filter."""

    def test_with_project_id(self):
        result = _project_filter(42)
        assert result == [["project", "is", {"type": "Project", "id": 42}]]

    def test_without_project_id(self):
        assert _project_filter(None) == []


class TestProjectData:
    """Tests for _project_data."""

    def test_with_project_id(self):
        result = _project_data(42)
        assert result == {"project": {"type": "Project", "id": 42}}

    def test_without_project_id(self):
        assert _project_data(None) == {}


class TestBuildRuleFilters:
    """Tests for _build_rule_filters."""

    def test_without_project(self):
        result = _build_rule_filters("p", ["alice", "data1"])
        assert result == [["sg_ptype", "is", "p"], ["sg_v0", "is", "alice"], ["sg_v1", "is", "data1"]]

    def test_with_project(self):
        result = _build_rule_filters("p", ["alice"], project_id=42)
        assert result[0] == ["project", "is", {"type": "Project", "id": 42}]
        assert result[1] == ["sg_ptype", "is", "p"]


# --- Adapter tests ---


@pytest.fixture
def mock_sg(mocker):
    """Fixture providing a mocked shotgun_api3.Shotgun instance."""
    return mocker.MagicMock()


@pytest.fixture
def adapter(mock_sg, mocker):
    """Fixture providing an Adapter with a mocked ShotGrid connection (no project scope)."""
    mocker.patch.dict(os.environ, {}, clear=True)
    return Adapter(sg=mock_sg)


@pytest.fixture
def project_adapter(mock_sg):
    """Fixture providing an Adapter scoped to a specific project."""
    return Adapter(sg=mock_sg, project_id=42)


class TestAdapterInit:
    """Tests for Adapter initialization."""

    def test_with_sg_instance(self, mock_sg, mocker):
        mocker.patch.dict(os.environ, {}, clear=True)
        adapter = Adapter(sg=mock_sg)
        assert adapter.sg is mock_sg
        assert adapter.entity_type == DEFAULT_ENTITY_TYPE
        assert adapter.project_id is None

    def test_custom_entity_type(self, mock_sg):
        adapter = Adapter(sg=mock_sg, entity_type="CustomEntity01")
        assert adapter.entity_type == "CustomEntity01"

    def test_project_id(self, mock_sg):
        adapter = Adapter(sg=mock_sg, project_id=42)
        assert adapter.project_id == 42

    def test_connect_via_params(self, mocker):
        mock_sg = mocker.MagicMock()
        mock_connect = mocker.patch("shotgrid_casbin_adapter.core._connect_sg", return_value=mock_sg)
        adapter = Adapter(base_url="https://test.sg.com", script_name="s", api_key="k")
        assert adapter.sg is mock_sg
        mock_connect.assert_called_once_with(base_url="https://test.sg.com", script_name="s", api_key="k")

    def test_missing_url_raises(self, mocker):
        mocker.patch.dict(os.environ, {}, clear=True)
        with pytest.raises(ValueError, match=SHOTGRID_URL):
            Adapter()

    def test_missing_script_name_raises(self, mocker):
        mocker.patch.dict(os.environ, {SHOTGRID_URL: "https://test.sg.com"}, clear=True)
        with pytest.raises(ValueError, match=SHOTGRID_SCRIPT_NAME):
            Adapter()

    def test_missing_api_key_raises(self, mocker):
        mocker.patch.dict(os.environ, {SHOTGRID_URL: "https://test.sg.com", SHOTGRID_SCRIPT_NAME: "s"}, clear=True)
        with pytest.raises(ValueError, match=SHOTGRID_API_KEY):
            Adapter()

    def test_entity_type_from_env(self, mock_sg, mocker):
        mocker.patch.dict(os.environ, {"SHOTGRID_ENTITY_TYPE": "MyEntity"}, clear=True)
        adapter = Adapter(sg=mock_sg)
        assert adapter.entity_type == "MyEntity"

    def test_project_id_from_env(self, mock_sg, mocker):
        mocker.patch.dict(os.environ, {SHOTGRID_PROJECT_ID: "99"}, clear=True)
        adapter = Adapter(sg=mock_sg)
        assert adapter.project_id == 99


class TestAdapterLoadPolicy:
    """Tests for Adapter.load_policy."""

    def test_load_policy(self, adapter, mock_sg, mocker):
        mock_sg.find.return_value = [
            {
                "id": 1,
                "sg_ptype": "p",
                "sg_v0": "alice",
                "sg_v1": "data1",
                "sg_v2": "read",
                "sg_v3": None,
                "sg_v4": None,
                "sg_v5": None,
            },
            {
                "id": 2,
                "sg_ptype": "g",
                "sg_v0": "alice",
                "sg_v1": "admin",
                "sg_v2": None,
                "sg_v3": None,
                "sg_v4": None,
                "sg_v5": None,
            },
        ]
        mocker.patch("shotgrid_casbin_adapter.core.persist.load_policy_line")

        adapter.load_policy(mocker.MagicMock())

        mock_sg.find.assert_called_once_with(DEFAULT_ENTITY_TYPE, [], ["id", *CASBIN_FIELDS])

    def test_load_policy_with_project(self, project_adapter, mock_sg, mocker):
        mock_sg.find.return_value = []
        mocker.patch("shotgrid_casbin_adapter.core.persist.load_policy_line")

        project_adapter.load_policy(mocker.MagicMock())

        mock_sg.find.assert_called_once_with(
            DEFAULT_ENTITY_TYPE,
            [["project", "is", {"type": "Project", "id": 42}]],
            ["id", *CASBIN_FIELDS],
        )


class TestAdapterSavePolicy:
    """Tests for Adapter.save_policy."""

    def test_save_policy_replaces_all(self, adapter, mock_sg):
        mock_sg.find.return_value = [{"id": 1}, {"id": 2}]

        mock_ast = type("Ast", (), {"policy": [["alice", "data1", "read"]]})()
        mock_model = type("Model", (), {"model": {"p": {"p": mock_ast}}})()

        result = adapter.save_policy(mock_model)

        assert result is True
        assert mock_sg.batch.call_count == 2  # delete + create

    def test_save_policy_with_project(self, project_adapter, mock_sg):
        mock_sg.find.return_value = [{"id": 1}]

        mock_ast = type("Ast", (), {"policy": [["alice", "data1", "read"]]})()
        mock_model = type("Model", (), {"model": {"p": {"p": mock_ast}}})()

        result = project_adapter.save_policy(mock_model)

        assert result is True
        # Verify find was called with project filter
        find_filters = mock_sg.find.call_args[0][1]
        assert find_filters == [["project", "is", {"type": "Project", "id": 42}]]
        # Verify create request includes project data
        create_batch = mock_sg.batch.call_args_list[1][0][0]
        assert create_batch[0]["data"]["project"] == {"type": "Project", "id": 42}


class TestAdapterAddPolicy:
    """Tests for Adapter.add_policy and add_policies."""

    def test_add_policy(self, adapter, mock_sg):
        adapter.add_policy("p", "p", ["alice", "data1", "read"])
        mock_sg.create.assert_called_once_with(
            DEFAULT_ENTITY_TYPE, {"sg_ptype": "p", "sg_v0": "alice", "sg_v1": "data1", "sg_v2": "read"}
        )

    def test_add_policy_with_project(self, project_adapter, mock_sg):
        project_adapter.add_policy("p", "p", ["alice", "data1", "read"])
        mock_sg.create.assert_called_once_with(
            DEFAULT_ENTITY_TYPE,
            {
                "sg_ptype": "p",
                "sg_v0": "alice",
                "sg_v1": "data1",
                "sg_v2": "read",
                "project": {"type": "Project", "id": 42},
            },
        )

    def test_add_policies(self, adapter, mock_sg):
        adapter.add_policies("p", "p", [["alice", "data1", "read"], ["bob", "data2", "write"]])
        requests = mock_sg.batch.call_args[0][0]
        assert len(requests) == 2
        assert all(r["request_type"] == "create" for r in requests)

    def test_add_policies_empty(self, adapter, mock_sg):
        adapter.add_policies("p", "p", [])
        mock_sg.batch.assert_not_called()


class TestAdapterRemovePolicy:
    """Tests for Adapter.remove_policy and remove_policies."""

    def test_remove_policy_found(self, adapter, mock_sg):
        mock_sg.find.return_value = [{"id": 1}]
        assert adapter.remove_policy("p", "p", ["alice", "data1", "read"]) is True
        mock_sg.delete.assert_called_once_with(DEFAULT_ENTITY_TYPE, 1)

    def test_remove_policy_not_found(self, adapter, mock_sg):
        mock_sg.find.return_value = []
        assert adapter.remove_policy("p", "p", ["alice", "data1", "read"]) is False

    def test_remove_policy_with_project(self, project_adapter, mock_sg):
        mock_sg.find.return_value = [{"id": 1}]
        assert project_adapter.remove_policy("p", "p", ["alice", "data1", "read"]) is True
        # Verify find was called with project filter
        find_filters = mock_sg.find.call_args[0][1]
        assert find_filters[0] == ["project", "is", {"type": "Project", "id": 42}]

    def test_remove_policies(self, adapter, mock_sg):
        mock_sg.find.side_effect = [[{"id": 1}], [{"id": 2}]]
        adapter.remove_policies("p", "p", [["alice", "data1", "read"], ["bob", "data2", "write"]])
        mock_sg.batch.assert_called_once()

    def test_remove_policies_empty(self, adapter, mock_sg):
        adapter.remove_policies("p", "p", [])
        mock_sg.find.assert_not_called()
        mock_sg.batch.assert_not_called()


class TestAdapterRemoveFilteredPolicy:
    """Tests for Adapter.remove_filtered_policy."""

    def test_removes_matching(self, adapter, mock_sg):
        mock_sg.find.return_value = [{"id": 1}, {"id": 2}]
        assert adapter.remove_filtered_policy("p", "p", 0, "alice") is True
        mock_sg.batch.assert_called_once()

    def test_no_match_returns_false(self, adapter, mock_sg):
        mock_sg.find.return_value = []
        assert adapter.remove_filtered_policy("p", "p", 0, "nobody") is False

    def test_invalid_index_returns_false(self, adapter, mock_sg):
        assert adapter.remove_filtered_policy("p", "p", 6, "alice") is False

    def test_with_project(self, project_adapter, mock_sg):
        mock_sg.find.return_value = [{"id": 1}]
        assert project_adapter.remove_filtered_policy("p", "p", 0, "alice") is True
        find_filters = mock_sg.find.call_args[0][1]
        assert find_filters[0] == ["project", "is", {"type": "Project", "id": 42}]


class TestAdapterUpdatePolicy:
    """Tests for Adapter.update_policy and update_policies."""

    def test_update_policy(self, adapter, mock_sg):
        mock_sg.find.return_value = [{"id": 1}]
        adapter.update_policy("p", "p", ["alice", "data1", "read"], ["alice", "data1", "write"])
        mock_sg.update.assert_called_once_with(
            DEFAULT_ENTITY_TYPE, 1, {"sg_ptype": "p", "sg_v0": "alice", "sg_v1": "data1", "sg_v2": "write"}
        )

    def test_update_policy_shorter_new_rule(self, adapter, mock_sg):
        mock_sg.find.return_value = [{"id": 1}]
        adapter.update_policy("p", "p", ["alice", "data1", "read"], ["alice", "data1"])
        mock_sg.update.assert_called_once_with(
            DEFAULT_ENTITY_TYPE, 1, {"sg_ptype": "p", "sg_v0": "alice", "sg_v1": "data1", "sg_v2": None}
        )

    def test_update_policy_not_found(self, adapter, mock_sg):
        mock_sg.find.return_value = []
        adapter.update_policy("p", "p", ["alice", "data1", "read"], ["bob", "data2", "write"])
        mock_sg.update.assert_not_called()

    def test_update_policies(self, adapter, mock_sg):
        mock_sg.find.side_effect = [[{"id": 1}], [{"id": 2}]]
        adapter.update_policies(
            "p",
            "p",
            [["alice", "data1", "read"], ["bob", "data2", "write"]],
            [["alice", "data1", "write"], ["bob", "data2", "read"]],
        )
        assert mock_sg.update.call_count == 2


class TestAdapterFilteredPolicy:
    """Tests for filtered policy loading."""

    def test_is_filtered_default(self, adapter):
        assert adapter.is_filtered() is False

    def test_load_filtered_policy(self, adapter, mock_sg, mocker):
        mock_sg.find.return_value = [
            {
                "id": 1,
                "sg_ptype": "p",
                "sg_v0": "alice",
                "sg_v1": "data1",
                "sg_v2": "read",
                "sg_v3": None,
                "sg_v4": None,
                "sg_v5": None,
            },
        ]
        mocker.patch("shotgrid_casbin_adapter.core.persist.load_policy_line")

        f = Filter()
        f.ptype = ["p"]
        adapter.load_filtered_policy(mocker.MagicMock(), f)

        assert adapter.is_filtered() is True
        assert mock_sg.find.call_args[0][1] == [["sg_ptype", "in", ["p"]]]

    def test_load_filtered_policy_with_project(self, project_adapter, mock_sg, mocker):
        mock_sg.find.return_value = []
        mocker.patch("shotgrid_casbin_adapter.core.persist.load_policy_line")

        f = Filter()
        f.ptype = ["p"]
        project_adapter.load_filtered_policy(mocker.MagicMock(), f)

        find_filters = mock_sg.find.call_args[0][1]
        assert find_filters[0] == ["project", "is", {"type": "Project", "id": 42}]
        assert find_filters[1] == ["sg_ptype", "in", ["p"]]
