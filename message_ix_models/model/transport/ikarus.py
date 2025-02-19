"""Prepare non-LDV data from the IKARUS model via :file:`GEAM_TRP_techinput.xlsx`."""

import logging
from functools import lru_cache, partial
from operator import le
from typing import TYPE_CHECKING

import pandas as pd
import xarray as xr
from genno import Computer, Key, KeySeq, Quantity, quote
from genno.core.key import single_key
from iam_units import registry
from openpyxl import load_workbook

from message_ix_models.util import (
    cached,
    convert_units,
    make_matched_dfs,
    package_data_path,
    same_node,
    same_time,
    series_of_pint_quantity,
)

from .key import bcast_tcl, bcast_y
from .non_ldv import UNITS

if TYPE_CHECKING:
    from message_ix_models.types import ParameterData

log = logging.getLogger(__name__)

#: Name of the input file.
#:
#: The input file uses the old, MESSAGE V names for parameters:
#:
#: - inv_cost = inv
#: - fix_cost = fom
#: - technical_lifetime = pll
#: - input (efficiency) = minp
#: - output (efficiency) = moutp
#: - capacity_factor = plf
FILE = "GEAM_TRP_techinput.xlsx"

#: Mapping from parameters to 3-tuples of units:
#:
#: 1. Factor for units appearing in the input file.
#: 2. Units appearing in the input file.
#: 3. Target units for MESSAGEix-GLOBIOM.
_UNITS = dict(
    # Appearing in input file
    inv_cost=(1.0e6, "EUR_2000 / vehicle", "MUSD_2005 / vehicle"),
    fix_cost=(1000.0, "EUR_2000 / vehicle / year", "MUSD_2005 / vehicle / year"),
    var_cost=(0.01, "EUR_2000 / kilometer", None),
    technical_lifetime=(1.0, "year", None),
    availability=(100, "kilometer / vehicle / year", None),
    # NB this is written as "GJ / km" in the file
    input=(0.01, "GJ / (vehicle kilometer)", None),
    output=(1.0, "", None),
    # Created below
    capacity_factor=(1.0, None, None),
)

#: Rows and columns appearing in each :data:`CELL_RANGE`.
_SHEET_INDEX = dict(
    index=[
        "inv_cost",
        "fix_cost",
        "var_cost",
        "technical_lifetime",
        "availability",
        "input",
        "output",
    ],
    columns=[2000, 2005, 2010, 2015, 2020, 2025, 2030],
)

#: For each technology (keys), values are 3-tuples giving:
#:
#: 1. source index entry in the extracted files.
#: 2. technology index entry in the extracted files.
#: 3. starting and final cells delimiting tables in :data:`FILE`.
SOURCE = {
    "rail_pub": ("IKARUS", "regional train electric efficient", "C103:I109"),
    "drail_pub": ("IKARUS", "commuter train diesel efficient", "C37:I43"),
    "dMspeed_rai": ("IKARUS", "intercity train diesel efficient", "C125:I131"),
    "Mspeed_rai": ("IKARUS", "intercity train electric efficient", "C147:I153"),
    "Hspeed_rai": ("IKARUS", "high speed train efficient", "C169:I175"),
    "con_ar": ("Krey/Linßen", "Airplane jet", "C179:I185"),
    # Same parametrization as 'con_ar' (per cell references in spreadsheet):
    "conm_ar": ("Krey/Linßen", "Airplane jet", "C179:I185"),
    "conE_ar": ("Krey/Linßen", "Airplane jet", "C179:I185"),
    "conh_ar": ("Krey/Linßen", "Airplane jet", "C179:I185"),
    "ICE_M_bus": ("Krey/Linßen", "Bus diesel", "C197:I203"),
    "ICE_H_bus": ("Krey/Linßen", "Bus diesel efficient", "C205:I211"),
    "ICG_bus": ("Krey/Linßen", "Bus CNG", "C213:I219"),
    # Same parametrization as 'ICG_bus'. Conversion factors will be applied.
    "ICAe_bus": ("Krey/Linßen", "Bus CNG", "C213:I219"),
    "ICH_bus": ("Krey/Linßen", "Bus CNG", "C213:I219"),
    "PHEV_bus": ("Krey/Linßen", "Bus CNG", "C213:I219"),
    "FC_bus": ("Krey/Linßen", "Bus CNG", "C213:I219"),
    # Both equivalent to 'FC_bus'
    "FCg_bus": ("Krey/Linßen", "Bus CNG", "C213:I219"),
    "FCm_bus": ("Krey/Linßen", "Bus CNG", "C213:I219"),
    "Trolley_bus": ("Krey/Linßen", "Bus electric", "C229:I235"),
}


def make_indexers(*args) -> dict[str, xr.DataArray]:
    """Return indexers corresponding to `SOURCE`.

    These can be used for :mod:`xarray`-style advanced indexing to select from the data
    in the IKARUS CSV files using the dimensions (source, t) and yield a new dimension
    ``t_new``.
    """
    t_new, source, t = zip(*[(k, v[0], v[1]) for k, v in SOURCE.items()])
    return dict(
        source=xr.DataArray(list(source), coords={"t_new": list(t_new)}),
        t=xr.DataArray(list(t), coords={"t_new": list(t_new)}),
    )


def make_output(input_data: dict[str, pd.DataFrame], techs) -> "ParameterData":
    """Make ``output`` data corresponding to IKARUS ``input`` data."""
    result = make_matched_dfs(
        input_data["input"], output=registry.Quantity(1.0, UNITS["output"])
    )

    @lru_cache
    def c_for(t: str) -> str:
        """Return e.g. "transport vehicle rail" for a specific rail technology `t`."""
        return f"transport vehicle {techs[techs.index(t)].parent.id.lower()}"

    # - Set "commodity" and "level" labels.
    # - Set units.
    # - Fill "node_dest" and "time_dest".
    result["output"] = (
        result["output"]
        .assign(commodity=lambda df: df["technology"].apply(c_for), level="useful")
        .pipe(same_node)
        .pipe(same_time)
    )

    return result


@cached
def read_ikarus_data(occupancy, k_output, k_inv_cost):
    """Read the IKARUS data from :data:`FILE`.

    No transformation is performed.

    **NB** this function takes only simple arguments so that :func:`.cached` computes
    the same key every time to avoid the slow step of opening/reading the spreadsheet.
    :func:`get_ikarus_data` then conforms the data to particular context settings.

    .. note:: superseded by the computations set up by :func:`prepare_computer`.
    """
    # Open the input file using openpyxl
    wb = load_workbook(
        package_data_path("transport", FILE), read_only=True, data_only=True
    )
    # Open the 'updateTRPdata' sheet
    sheet = wb["updateTRPdata"]

    # 'technology name' -> pd.DataFrame
    dfs = {}
    for tec, (*_, cell_range) in SOURCE.items():
        # - Read values from table for one technology, e.g. "regional train electric
        #   efficient" = rail_pub.
        # - Extract the value from each openpyxl cell object.
        # - Set all non numeric values to NaN.
        # - Transpose so that each variable is in one column.
        # - Convert from input units to desired units.
        df = (
            pd.DataFrame(list(sheet[slice(*cell_range.split(":"))]), **_SHEET_INDEX)
            .applymap(lambda c: c.value)
            .apply(pd.to_numeric, errors="coerce")
            .transpose()
            .apply(convert_units, unit_info=UNITS, store="quantity")
        )

        # Convert IKARUS data to MESSAGEix-scheme parameters

        # TODO handle "availability" to provide distance_nonldv

        # Output efficiency: occupancy multiplied by an efficiency factor from config
        # NB this no longer depends on the file contents, and could be moved out of this
        #    function.
        output = registry.Quantity(
            occupancy[tec], "passenger / vehicle"
        ) * k_output.get(tec, 1.0)
        df["output"] = series_of_pint_quantity([output] * len(df.index), index=df.index)

        df["inv_cost"] *= k_inv_cost.get(tec, 1.0)

        # Include variable cost * availability in fix_cost
        df["fix_cost"] += df["availability"] * df["var_cost"]

        # Store
        dfs[tec] = df.drop(columns=["availability", "var_cost"])

    # Finished reading IKARUS data from spreadsheet
    wb.close()

    # - Concatenate to pd.DataFrame with technology and param as columns.
    # - Reformat as a pd.Series with a 3-level index: year, technology, param
    return (
        pd.concat(dfs, axis=1, names=["technology", "param"])
        .rename_axis(index="year")
        .stack(["technology", "param"])
    )


def prepare_computer(c: Computer):
    """Prepare `c` to perform model data preparation using IKARUS data.

    ====================================================================================

    The data is read from from ``GEAM_TRP_techinput.xlsx``, and the processed data is
    exported into ``non_LDV_techs_wrapped.csv``.

    .. note:: superseded by the computations set up by :func:`prepare_computer`.

    Parameters
    ----------
    context : .Context

    Returns
    -------
    data : dict of (str -> pandas.DataFrame)
        Keys are MESSAGE parameter names such as 'input', 'fix_cost'.
        Values are data frames ready for :meth:`~.Scenario.add_par`.
        Years in the data include the model horizon indicated by
        :attr:`.Config.base_model_info`, plus the additional year 2010.
    """
    # TODO identify whether capacity_factor is needed
    c.configure(rename_dims={"source": "source"})

    c.add_single("ikarus indexers", quote(make_indexers()))
    c.add_single("y::ikarus", lambda data: list(filter(partial(le, 2000), data)), "y")
    k_u = c.add("ikarus adjust units", Quantity(1.0, units="(vehicle year) ** -1"))

    # NB this (harmlessly) duplicates an addition in .ldv.prepare_computer()
    # TODO deduplicate
    k_fi = c.add(
        "factor_input",
        "transport input factor:t-y",
        "y",
        "t::transport",
        "t::transport agg",
        "config",
    )

    parameters = ["fix_cost", "input", "inv_cost", "technical_lifetime", "var_cost"]

    # For as_message_df(), common mapping from message_ix dimension IDs to short IDs in
    # computed quantities
    dims_common = dict(commodity="c", node_loc="n", node_origin="n", technology="t")
    # For as_message_df(), fixed values for all data
    common = dict(mode="all", time="year", time_origin="year")

    # Create a chain of tasks for each parameter
    final = {}
    for name in ["availability"] + parameters:
        # Base key for computations related to parameter `name`
        ks = KeySeq(f"ikarus {name}:c-t-y")

        # Refer to data loaded from file
        # Extend over missing periods in the model horizon
        key = c.add(
            ks[0] * "source",
            "extend_y",
            ks.base * "source" + "exo",
            "y::ikarus",
            strict=True,
        )

        if name in ("fix_cost", "inv_cost"):
            # Adjust for "availability". The IKARUS source gives these costs, and
            # simultaneously an "availability" in [length]. Implicitly, the costs are
            # those to construct/operate enough vehicles/infrastructure to provide that
            # amount of availability. E.g. a cost of 1000 EUR and availability of 10 km
            # give a cost of 100 EUR / km.
            key = c.add(ks[1], "div", key, Key("ikarus availability", "tyc", "0"))
            # Adjust units
            key = c.add(ks[2], "mul", key, k_u)

        # Select desired values
        c.add(ks[3], "select", key, "ikarus indexers")
        key = c.add(ks[4], "rename_dims", ks[3], quote({"t_new": "t"}))

        if name == "input":
            # Apply scenario-specific input efficiency factor
            key = single_key(c.add("nonldv efficiency::adj", "mul", k_fi, key))
            # Drop existing "c" dimension
            key = single_key(c.add(key / "c", "drop_vars", key, quote("c")))
            # Fill (c, l) dimensions based on t
            key = c.add(ks[5], "mul", key, bcast_tcl.input)
        elif name == "technical_lifetime":
            # Round up technical_lifetime values due to incompatibility in handling
            # non-integer values in the GAMS code
            key = c.add(ks[5], "round", key)

        # Broadcast across "n" dimension
        key = c.add(ks[6], "mul", key, "n:n:ex world")

        if name in ("fix_cost", "input", "var_cost"):
            # Broadcast across valid (yv, ya) pairs
            key = c.add(ks[7], "mul", key, bcast_y.model)

        # Convert to target units
        try:
            target_units = quote(UNITS[name])
        except KeyError:  # "availability"
            pass
        else:
            key = c.add(ks[8], "convert_units", key, target_units)

        # Mapping between short dimension IDs in the computed quantities and the
        # dimensions in the respective MESSAGE parameters
        dims = dims_common.copy()
        dims.update(
            {
                "fix_cost": dict(year_act="ya", year_vtg="yv"),
                "input": dict(year_act="ya", year_vtg="yv", level="l"),
                "var_cost": dict(year_act="ya", year_vtg="yv"),
            }.get(name, dict(year_vtg="y"))
        )

        # Convert to message_ix-compatible data frames
        key = c.add(
            f"transport nonldv {name}::ixmp",
            "as_message_df",
            key,
            name=name,
            dims=dims,
            common=common,
        )

        if name in parameters:
            # The "availability" task would error, since it is not a MESSAGE parameter
            final[name] = key

    # Derive "output" data from "input"
    key = "transport nonldv output::ixmp"
    final["output"] = c.add(
        key, make_output, "transport nonldv input::ixmp", "t::transport"
    )

    # Merge all data together
    k_all = "transport nonldv::ixmp+ikarus"
    c.add(k_all, "merge_data", *final.values())

    # NB we do *not* call c.add("transport_data", ...) here; that is done in
    # .non_ldv.prepare_computer() only if IKARUS is the selected data source for non-LDV
    # data. Other derived quantities (emissions factors) are also prepared there based
    # on these outputs.
