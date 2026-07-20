"""Filter module for ShotGrid Casbin policy queries.

This module defines the :class:`Filter` class used for filtered policy loading
and the :func:`_build_sg_filters` helper that translates a :class:`Filter`
instance into ShotGrid's ``[field, "in", values]`` filter syntax.

Typical usage example:

    from shotgrid_casbin_adapter.filter import Filter, _build_sg_filters

    f = Filter()
    f.ptype = ["p"]
    f.v0 = ["alice"]
    sg_filters = _build_sg_filters(f)
    # => [["ptype", "in", ["p"]], ["v0", "in", ["alice"]]]

Attributes:
    Filter: A filter class for filtered policy loading.
"""

from shotgrid_casbin_adapter.constants import CASBIN_FIELD_NAMES
from shotgrid_casbin_adapter.constants import CASBIN_FIELDS


class Filter:
    """Filter for loading filtered policies from ShotGrid.

    Each attribute is a list of values to match against the corresponding
    Casbin field. An empty list means the field is not filtered.

    Attributes:
        ptype: List of policy type values to filter by.
        v0: List of v0 field values to filter by.
        v1: List of v1 field values to filter by.
        v2: List of v2 field values to filter by.
        v3: List of v3 field values to filter by.
        v4: List of v4 field values to filter by.
        v5: List of v5 field values to filter by.
    """

    def __init__(self) -> None:
        """Initialize a Filter with empty filter lists."""
        self.ptype: list[str] = []
        self.v0: list[str] = []
        self.v1: list[str] = []
        self.v2: list[str] = []
        self.v3: list[str] = []
        self.v4: list[str] = []
        self.v5: list[str] = []


def _build_sg_filters(filter_obj: Filter) -> list[list[str | list[str]]]:
    """Build ShotGrid filter syntax from a Casbin Filter object.

    Translates the Filter's ``ptype``/``v0``-``v5`` lists into ShotGrid's
    ``[field, "in", values]`` filter format. Fields with empty lists are
    omitted from the resulting filters.

    Args:
        filter_obj: A :class:`Filter` instance whose non-empty attribute
            lists are translated into ShotGrid filters.

    Returns:
        A list of ShotGrid filter expressions, e.g.
        ``[["ptype", "in", ["p"]], ["v0", "in", ["alice"]]]``.
    """
    return [
        [sg_field, "in", vals]
        for base_name, sg_field in zip(CASBIN_FIELD_NAMES, CASBIN_FIELDS, strict=True)
        if (vals := getattr(filter_obj, base_name, []))
    ]
