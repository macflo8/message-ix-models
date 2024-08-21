import logging
from typing import Mapping

import message_ix

from message_ix_models.model.build import apply_spec
from message_ix_models.model.material.data_aluminum import gen_data_aluminum
from message_ix_models.model.material.data_ammonia_new import gen_all_NH3_fert
from message_ix_models.model.material.data_cement import gen_data_cement
from message_ix_models.model.material.data_generic import gen_data_generic
from message_ix_models.model.material.data_methanol_new import gen_data_methanol_new
from message_ix_models.model.material.data_other_industry import (
    add_coal_lowerbound_2020,
    add_elec_lowerbound_2020,
    add_new_ind_hist_act,
    get_hist_act,
    modify_demand_and_hist_activity,
    modify_industry_demand,
    remove_baseyear_bounds,
)
from message_ix_models.model.material.data_petro import gen_data_petro_chemicals
from message_ix_models.model.material.data_power_sector import gen_data_power_sector
from message_ix_models.model.material.data_steel import gen_data_steel
from message_ix_models.model.material.data_util import (
    add_cement_bounds_2020,
    add_emission_accounting,
    calibrate_for_SSPs,
    maybe_add_water_tecs,
)
from message_ix_models.model.material.share_constraints import add_coal_constraint
from message_ix_models.model.material.util import read_config
from message_ix_models.util import (
    add_par_data,
    identify_nodes,
    package_data_path,
)
from message_ix_models.util.compat.message_data import (
    calibrate_UE_gr_to_demand,
    calibrate_UE_share_constraints,
)
from message_ix_models.util.compat.message_data import (
    manual_updates_ENGAGE_SSP2_v417_to_v418 as engage_updates,
)
from message_ix_models.util.scenarioinfo import ScenarioInfo

log = logging.getLogger(__name__)

DATA_FUNCTIONS = [
    # gen_data_buildings,
    gen_data_methanol_new,
    gen_all_NH3_fert,
    # gen_data_ammonia, ## deprecated module!
    gen_data_generic,
    gen_data_steel,
    gen_data_cement,
    gen_data_petro_chemicals,
    gen_data_power_sector,
    gen_data_aluminum,
]

# add as needed/implemented
SPEC_LIST = [
    "generic",
    "common",
    "steel",
    "cement",
    "aluminum",
    "petro_chemicals",
    "buildings",
    "power_sector",
    "fertilizer",
    "methanol",
]


# Try to handle multiple data input functions from different materials
def add_data(scenario, dry_run=False):
    """Populate `scenario` with MESSAGEix-Materials data."""
    # Information about `scenario`
    info = ScenarioInfo(scenario)

    # Check for two "node" values for global data
    if {"World", "R11_GLB"} < set(info.set["node"]):
        log.warning("Remove 'R11_GLB' from node list for data generation")
        info.set["node"].remove("R11_GLB")
    if {"World", "R12_GLB"} < set(info.set["node"]):
        log.warning("Remove 'R12_GLB' from node list for data generation")
        info.set["node"].remove("R12_GLB")

    for func in DATA_FUNCTIONS:
        # Generate or load the data; add to the Scenario
        log.info(f"from {func.__name__}()")
        data = func(scenario)
        add_par_data(scenario, data, dry_run=dry_run)

    log.info("done")


def build(
    scenario: message_ix.Scenario,
    old_calib: bool,
    iea_data_path: str = None,
    version: str = "default",
) -> message_ix.Scenario:
    """Set up materials accounting on `scenario`."""

    # Get the specification
    # Apply to the base scenario
    spec = get_spec()

    maybe_add_water_tecs(scenario)

    apply_spec(scenario, spec, add_data, fast=True)  # dry_run=True
    if "SSP_dev" not in scenario.model:
        engage_updates._correct_balance_td_efficiencies(scenario)
        engage_updates._correct_coal_ppl_u_efficiencies(scenario)
        engage_updates._correct_td_co2cc_emissions(scenario)
    from message_ix_models import ScenarioInfo

    s_info = ScenarioInfo(scenario)
    nodes = s_info.N

    # Adjust exogenous energy demand to incorporate the endogenized sectors
    # Adjust the historical activity of the useful level industry technologies
    # Coal calibration 2020
    if old_calib:
        modify_demand_and_hist_activity(scenario)
    else:
        remove_baseyear_bounds(scenario)
        last_hist_year = scenario.par("historical_activity")["year_act"].max()
        modify_industry_demand(scenario, last_hist_year, iea_data_path)
        add_new_ind_hist_act(scenario, [last_hist_year], iea_data_path)
    add_emission_accounting(scenario)

    # scenario.commit("no changes")
    add_coal_lowerbound_2020(scenario)
    add_cement_bounds_2020(scenario, "high_temp")

    # Market penetration adjustments
    # NOTE: changing demand affects the market penetration
    # levels for the enduse technologies.
    # FIXME: context.ssp only works for SSP1/2/3 currently missing SSP4/5
    calibrate_UE_gr_to_demand(
        scenario,
        s_info,
        data_path=package_data_path("material"),
        ssp="SSP2",
        region=identify_nodes(scenario),
    )
    calibrate_UE_share_constraints(scenario, s_info)

    # Electricity calibration to avoid zero prices for CHN.
    if "R12_CHN" in nodes:
        add_elec_lowerbound_2020(scenario)

    df = scenario.par(
        "bound_activity_lo",
        filters={"node_loc": "R12_RCPA", "technology": "sp_el_I", "year_act": 2020},
    )
    scenario.check_out()
    scenario.remove_par("bound_activity_lo", df)
    scenario.commit("remove sp_el_I min bound on RCPA in 2020")

    calibrate_for_SSPs(scenario)
    # add share constraint for coal_i based on 2020 IEA data
    add_coal_constraint(scenario)
    # overwrite non-Materials industry technology calibration
    calib_data = get_hist_act(
        scenario, [1990, 1995, 2000, 2010, 2015, 2020], iea_data_path
    )
    scenario.check_out()
    for k, v in calib_data.items():
        scenario.add_par(k, v)
    scenario.commit("new calibration of other industry")
    add_coal_constraint(scenario)
    return scenario


def get_spec() -> Mapping[str, ScenarioInfo]:
    """Return the specification for materials accounting."""
    require = ScenarioInfo()
    add = ScenarioInfo()
    remove = ScenarioInfo()

    # Load configuration
    # context = Context.get_instance(-1)
    context = read_config()

    # Update the ScenarioInfo objects with required and new set elements
    for type in SPEC_LIST:
        for set_name, config in context["material"][type].items():
            # for cat_name, detail in config.items():
            # Required elements
            require.set[set_name].extend(config.get("require", []))

            # Elements to add
            add.set[set_name].extend(config.get("add", []))

            # Elements to remove
            remove.set[set_name].extend(config.get("remove", []))

    return dict(require=require, add=add, remove=remove)
