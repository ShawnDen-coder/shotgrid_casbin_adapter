"""Tests for the ShotGrid Casbin Adapter core module."""

# ruff: noqa: D102

import os

import pytest

from shotgrid_casbin_adapter.constants import CASBIN_FIELDS
from shotgrid_casbin_adapter.constants import DEFAULT_ENTITY_TYPE
from shotgrid_casbin_adapter.constants import SHOTGRID_API_KEY
from shotgrid_casbin_adapter.constants import SHOTGRID_SCRIPT_NAME
from shotgrid_casbin_adapter.constants import SHOTGRID_URL
from shotgrid_casbin_adapter.core import Adapter
from shotgrid_casbin_adapter.filter import Filter
from shotgrid_casbin_adapter.filter import _build_sg_filters
from shotgrid_casbin_adapter.helpers import _entity_to_str
from shotgrid_casbin_adapter.helpers import _rule_to_dict


# --- Helper function tests ---


class TestRuleToDict:
    """Tests for _rule_to_dict."""

    def test_basic_rule(self):
        assert _rule_to_dict("p", ["alice", "data1", "read"]) == {
            "ptype": "p",
            "v0": "alice",
            "v1": "data1",
            "v2": "read",
        }

    def test_short_rule(self):
        assert _rule_to_dict("g", ["alice", "admin"]) == {"ptype": "g", "v0": "alice", "v1": "admin"}

    def test_empty_rule(self):
        assert _rule_to_dict("p", []) == {"ptype": "p"}


class TestEntityToStr:
    """Tests for _entity_to_str."""

    def test_full_entity(self):
        entity = {"ptype": "p", "v0": "alice", "v1": "data1", "v2": "read", "v3": None, "v4": None, "v5": None}
        assert _entity_to_str(entity) == "p, alice, data1, read"

    def test_short_entity(self):
        entity = {"ptype": "g", "v0": "alice", "v1": "admin", "v2": None}
        assert _entity_to_str(entity) == "g, alice, admin"

    def test_ptype_only(self):
        assert _entity_to_str({"ptype": "p", "v0": None}) == "p"


class TestBuildSgFilters:
    """Tests for _build_sg_filters."""

    def test_empty_filter(self):
        assert _build_sg_filters(Filter()) == []

    def test_ptype_filter(self):
        f = Filter()
        f.ptype = ["p"]
        assert _build_sg_filters(f) == [["ptype", "in", ["p"]]]

    def test_multiple_fields(self):
        f = Filter()
        f.ptype = ["p"]
        f.v0 = ["alice", "bob"]
        assert _build_sg_filters(f) == [["ptype", "in", ["p"]], ["v0", "in", ["alice", "bob"]]]


# --- Adapter tests ---


@pytest.fixture
def mock_sg(mocker):
    """Fixture providing a mocked shotgun_api3.Shotgun instance."""
    return mocker.MagicMock()


@pytest.fixture
def adapter(mock_sg):
    """Fixture providing an Adapter with a mocked ShotGrid connection."""
    return Adapter(sg=mock_sg)


class TestAdapterInit:
    """Tests for Adapter initialization."""

    def test_with_sg_instance(self, mock_sg):
        adapter = Adapter(sg=mock_sg)
        assert adapter.sg is mock_sg
        assert adapter.entity_type == DEFAULT_ENTITY_TYPE

    def test_custom_entity_type(self, mock_sg):
        adapter = Adapter(sg=mock_sg, entity_type="CustomEntity01")
        assert adapter.entity_type == "CustomEntity01"

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


class TestAdapterLoadPolicy:
    """Tests for Adapter.load_policy."""

    def test_load_policy(self, adapter, mock_sg, mocker):
        mock_sg.find.return_value = [
            {"id": 1, "ptype": "p", "v0": "alice", "v1": "data1", "v2": "read", "v3": None, "v4": None, "v5": None},
            {"id": 2, "ptype": "g", "v0": "alice", "v1": "admin", "v2": None, "v3": None, "v4": None, "v5": None},
        ]
        mocker.patch("shotgrid_casbin_adapter.core.persist.load_policy_line")

        adapter.load_policy(mocker.MagicMock())

        mock_sg.find.assert_called_once_with(DEFAULT_ENTITY_TYPE, [], ["id", *CASBIN_FIELDS])


class TestAdapterSavePolicy:
    """Tests for Adapter.save_policy."""

    def test_save_policy_replaces_all(self, adapter, mock_sg):
        mock_sg.find.return_value = [{"id": 1}, {"id": 2}]

        mock_ast = type("Ast", (), {"policy": [["alice", "data1", "read"]]})()
        mock_model = type("Model", (), {"model": {"p": {"p": mock_ast}}})()

        result = adapter.save_policy(mock_model)

        assert result is True
        assert mock_sg.batch.call_count == 2  # delete + create


class TestAdapterAddPolicy:
    """Tests for Adapter.add_policy and add_policies."""

    def test_add_policy(self, adapter, mock_sg):
        adapter.add_policy("p", "p", ["alice", "data1", "read"])
        mock_sg.create.assert_called_once_with(
            DEFAULT_ENTITY_TYPE, {"ptype": "p", "v0": "alice", "v1": "data1", "v2": "read"}
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


class TestAdapterUpdatePolicy:
    """Tests for Adapter.update_policy and update_policies."""

    def test_update_policy(self, adapter, mock_sg):
        mock_sg.find.return_value = [{"id": 1}]
        adapter.update_policy("p", "p", ["alice", "data1", "read"], ["alice", "data1", "write"])
        mock_sg.update.assert_called_once_with(
            DEFAULT_ENTITY_TYPE, 1, {"ptype": "p", "v0": "alice", "v1": "data1", "v2": "write"}
        )

    def test_update_policy_shorter_new_rule(self, adapter, mock_sg):
        mock_sg.find.return_value = [{"id": 1}]
        adapter.update_policy("p", "p", ["alice", "data1", "read"], ["alice", "data1"])
        mock_sg.update.assert_called_once_with(
            DEFAULT_ENTITY_TYPE, 1, {"ptype": "p", "v0": "alice", "v1": "data1", "v2": None}
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
            {"id": 1, "ptype": "p", "v0": "alice", "v1": "data1", "v2": "read", "v3": None, "v4": None, "v5": None},
        ]
        mocker.patch("shotgrid_casbin_adapter.core.persist.load_policy_line")

        f = Filter()
        f.ptype = ["p"]
        adapter.load_filtered_policy(mocker.MagicMock(), f)

        assert adapter.is_filtered() is True
        assert mock_sg.find.call_args[0][1] == [["ptype", "in", ["p"]]]
