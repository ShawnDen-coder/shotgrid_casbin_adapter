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
    # => [["sg_ptype", "in", ["p"]], ["code", "in", ["alice"]]]

Attributes:
    Filter: A filter class for filtered policy loading.
"""

from shotgrid_casbin_adapter.constants import CASBIN_FIELDS


# Mapping from Filter attribute names to ShotGrid API field names.
# v0 maps to "code" (built-in field), v1-v5 map to sg_v1-sg_v5.
_FILTER_ATTR_TO_SG_FIELD: dict[str, str] = {
    "ptype": CASBIN_FIELDS[0],  # sg_ptype
    "v0": CASBIN_FIELDS[1],  # code
    "v1": CASBIN_FIELDS[2],  # sg_v1
    "v2": CASBIN_FIELDS[3],  # sg_v2
    "v3": CASBIN_FIELDS[4],  # sg_v3
    "v4": CASBIN_FIELDS[5],  # sg_v4
    "v5": CASBIN_FIELDS[6],  # sg_v5
}


class Filter:
    """Filter for loading filtered policies from ShotGrid.

    Each attribute is a list of values to match against the corresponding
    Casbin field. An empty list means the field is not filtered.

    Attributes:
        ptype: List of policy type values to filter by.
        v0: List of v0 field values to filter by (maps to ``code``).
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
    ``[field, "in", values]`` filter format. ``v0`` maps to the ``code``
    field. Fields with empty lists are omitted.

    Args:
        filter_obj: A :class:`Filter` instance whose non-empty attribute
            lists are translated into ShotGrid filters.

    Returns:
        A list of ShotGrid filter expressions, e.g.
        ``[["sg_ptype", "in", ["p"]], ["code", "in", ["alice"]]]``.
    """
    return [
        [sg_field, "in", vals]
        for attr_name, sg_field in _FILTER_ATTR_TO_SG_FIELD.items()
        if (vals := getattr(filter_obj, attr_name, []))
    ]
