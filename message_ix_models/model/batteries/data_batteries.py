import ixmp
import message_ix
import pandas as pd
from data_mats_global import gen_mats_data
from data_trade_glb import gen_trade_data
from message_data.tools.utilities import get_optimization_years
from message_ix import make_df

COMMENTS = "resource_1xAgrades_100xBgrades_80USD_EV150USD_cheapB_10y"
carbon_tax = 80
transport_CO2_tax = 150

# Parameterize lifetime and km driven yearly of EVs
# lifetime expressed in years
# Mileage expessed in tkm/year
lifetime = 10
mileage = 15

# %% md
# Set-up model
# Specify filename and name of sheet for data extraction
FILENAME = (
    "/home/lorenzou/eptex/indecol/USERS/Lorenzo/message_ix/inputs/input_LIBs.xlsx"
)
sheet_name = "Graphite_format"
SHEET_HIST = "Capacities"
# demand_sheet = 'demand'
TRADE_SHEET = "GLB_trade"
HISTORY = [2015, 2020]
model_horizon = [2030, 2040, 2050, 2060, 2070, 2080, 2090, 2100]
regions = imports_input["node_loc"].unique()
MOD = "MaterialsTransport_Global"
prtp_techs = [
    "ELC_100",
    "HFC_ptrp",
    "IAHe_ptrp",
    "IAHm_ptrp",
    "ICAe_ffv",
    "ICAm_ptrp",
    "ICE_conv",
    "ICE_L_ptrp",
    "ICE_nga",
    "ICH_chyb",
    "IGH_ghyb",
    "PHEV_ptrp",
]
years_df = scenario.vintage_and_active_years()
vintage_years, act_years = years_df["year_vtg"], years_df["year_act"]


def set_up_ixmp_platform(mp):
    mp.add_unit("Mt")
    mp.add_unit("GWh")
    mp.add_unit("GWa/Mt")
    mp.add_unit("MUSD/Mt")
    mp.add_unit("Mt/Mt")
    mp.add_unit("GWh/Mvehicle")

    r12_dict = pd.read_csv("r12_platform_regions.csv").to_dict("records")
    for reg_dict in r12_dict:
        mp.add_region(**reg_dict)


def get_base_scenario():
    mp = ixmp.Platform()
    scen = "Baseline"

    baseline = message_ix.Scenario(mp, model=MOD, scenario=scen)

    scenario = baseline.clone(
        MOD, COMMENTS, "Looking for reference", shift_first_model_year=2025
    )  # , keep_solution = False)

    # scenario = baseline.clone(mod,
    #                           'Materials_Transport_2020_resources_km',
    #                           'change years',
    #                           keep_solution = False)
    scenario = baseline.clone(
        MOD,
        COMMENTS,
        "Looking for reference",
        shift_first_model_year=2025,
        keep_solution=False,
    )
    scenario.check_out()
    return scenario


def add_model_structure(scenario):
    imports_exports_sheet = "import_exports"
    entry_data = pd.read_excel(FILENAME, sheet_name)

    comms_filtered = entry_data["parameter"]

    comms_filtered = comms_filtered.loc[
        ~comms_filtered.str.contains("technical_lifetime")
        & ~comms_filtered.str.contains("fix_cost")
        & ~comms_filtered.str.contains("var_cost")
        & ~comms_filtered.str.contains("inv_cost")
        & ~comms_filtered.str.contains("capacity_factor")
    ]

    unique_commodities = []
    unique_levels = []

    for comm in comms_filtered:
        unique_commodities.append(comm.split("|")[1])
        unique_levels.append(comm.split("|")[2])

    unique_commodities = list(dict.fromkeys(unique_commodities))
    unique_levels = list(dict.fromkeys(unique_levels))
    unique_techs = entry_data["technology"].unique().tolist()

    scenario.add_set("commodity", unique_commodities)
    scenario.add_set("level", unique_levels)
    scenario.add_set("technology", unique_techs)

    trade_techs = pd.read_excel(FILENAME, imports_exports_sheet)
    unique_trade = trade_techs["technology"].unique().tolist()
    scenario.add_set("technology", unique_trade)

    trade_techs = pd.read_excel(FILENAME, TRADE_SHEET)
    unique_trade = trade_techs["technology"].unique().tolist()
    scenario.add_set("technology", unique_trade)

    mode = ["all"]
    scenario.add_set("mode", mode)
    scenario.commit("Data_prep")


# %% md
## Read input data from Excel files
scenario = gen_mats_data(FILENAME, sheet_name, scenario)

scenario.commit("tecno_economic_mats")


def generate_trade_io(scenario):
    filename_trade = (
        "/home/lorenzou/eptex/indecol/USERS/Lorenzo/"
        "message_ix/inputs/struct_imports_exports.xlsx"
    )

    imports_input = pd.read_excel(
        filename_trade, sheet_name="input_import", index_col=0
    )
    imports_output = pd.read_excel(
        filename_trade, sheet_name="output_import", index_col=0
    )
    exports_input = pd.read_excel(
        filename_trade, sheet_name="input_export", index_col=0
    )
    exports_output = pd.read_excel(
        filename_trade, sheet_name="output_export", index_col=0
    )

    scenario.check_out()

    exports_input = exports_input.astype({"year_vtg": int, "year_act": int})
    exports_output = exports_output.astype({"year_vtg": int, "year_act": int})

    scenario.add_par("input", imports_input)
    scenario.add_par("input", exports_input)
    scenario.add_par("output", imports_output)
    scenario.add_par("output", exports_output)

    scenario.commit("imports_exports")

    scenario = gen_trade_data(FILENAME, TRADE_SHEET, scenario)

    scenario.commit("glb_trade_tech")


# %% md
## Replace exogenuous LIBs demand with initial activity up
df = pd.read_excel(
    "/home/lorenzou/eptex/indecol/USERS/Lorenzo/message_ix/inputs/Battery_growth.xlsx",
    sheet_name="Sheet1",
    index_col=0,
    nrows=1,
)
df = df.transpose()
df = df.T.reset_index().T
batt_size = df.interpolate(method="linear", axis=0).round()
batt_size = batt_size.reset_index()

model_horizon = [
    2025,
    2030,
    2035,
    2040,
    2045,
    2050,
    2055,
    2060,
    2070,
    2080,
    2090,
    2100,
    2110,
]
scenario.add_par("interestrate", model_horizon, value=0.05, unit="-")


# %% md
## Add capacities
def add_hist_data(scenario, regions):
    data_historical = pd.read_excel(FILENAME, SHEET_HIST)
    for region in regions:
        df = data_historical[data_historical["region"] == region]

        for tec in df["technology"].unique():
            hist_activity = pd.DataFrame(
                {
                    "node_loc": region,
                    "year_act": HISTORY,
                    "mode": "all",
                    "time": "year",
                    "unit": "Mt",
                    "technology": tec,
                    "value": df.loc[(df["technology"] == tec), "production"],
                }
            )
            scenario.add_par("historical_activity", hist_activity)

        for tec in df["technology"].unique():
            c_factor = scenario.par("capacity_factor", filters={"technology": tec})[
                "value"
            ].values[0]
            value = df.loc[(df["technology"] == tec), "new_production"] / c_factor
            unit = df.loc[(df["technology"] == tec), "units"]
            hist_capacity = pd.DataFrame(
                {
                    "node_loc": region,
                    "year_vtg": HISTORY,
                    "unit": unit,
                    "technology": tec,
                    "value": value,
                }
            )
            scenario.add_par("historical_new_capacity", hist_capacity)

    scenario.commit("adding hist capacities and  activity")


# %% md
## adding constraints to supply chains
def add_supply_constraints(regions, scenario, unique_techs):
    # IS IN MD IN NOTEBOOK, so maybe not needed?
    unique_techs_LIBs = []
    for tech in unique_techs:
        if "LIB" in tech or "anode" in tech or "cathode" in tech:
            unique_techs_LIBs.append(tech)

    for region in regions:
        for tec in unique_techs:
            df = make_df(
                "growth_activity_up",
                node_loc=region,
                year_act=model_horizon,
                time="year",
                unit="-",
                technology=tec,
                value=0.3,
            )
            scenario.add_par("growth_activity_up", df)

    for region in regions:
        for tec in unique_techs_LIBs:
            df = make_df(
                "growth_activity_up",
                node_loc=region,
                year_act=model_horizon,
                time="year",
                unit="-",
                technology=tec,
                value=0.6,
            )
            scenario.add_par("growth_activity_up", df)

    scenario.commit("adding growth constraints")

    scenario.check_out()

    LIBs = []
    for tech in unique_techs:
        if "LIB" in tech:
            unique_techs_LIBs.append(tech)

    for region in regions:
        for tec in LIBs:
            df = make_df(
                "initial_activity_up",
                node_loc=region,
                year_act=model_horizon,
                time="year",
                unit="GWh",
                technology=tec,
                value=15,
            )
            scenario.add_par("initial_activity_up", df)

    for region in regions:
        for tec in unique_techs:
            df = make_df(
                "initial_activity_up",
                node_loc=region,
                year_act=model_horizon,
                time="year",
                unit="Mt",
                technology=tec,
                value=1,
            )
            scenario.add_par("initial_activity_up", df)
    scenario.commit("new test with act up")


# %% md
# Adding data to the parameter
# TODO: find out how 'shares' was defined
for region in regions:
    df = pd.DataFrame(
        {
            "shares": shares,
            "node_share": region,
            "year_act": [2020],
            "time": "year",
            "value": [0.5],
            "unit": "Mt",
        }
    )
    scenario.add_par("share_commodity_lo", df)
# %% md
scenario.commit(comment="Define parameters for minimumn co hydroxide supply from cu")


# %% md
## Add carbon price
def add_carbon_price():
    horizon = get_optimization_years(scenario)
    tax_emission_df = {
        "node": "World",
        "type_emission": "TCE",
        "type_tec": "all",
        "type_year": horizon,
        "unit": "USD/tC",
    }

    # calculate period correction factor to reflect average carbon price in a period
    length5 = sum(1.05 ** pd.Series([-4, -3, -2, -1, 0])) / 5  # for 5-year periods
    length10 = (
        sum(1.05 ** pd.Series([-9, -8, -7, -6, -5, -4, -3, -2, -1, 0])) / 10
    )  # for 10-year periods
    period_correction = (
        pd.Series([length5] * 9)
        ._append(pd.Series([length10] * 4))
        .reset_index(drop=True)
    )  # combine correction factors for 5- and 10-year periods

    # add exponential growing carbon price of 80 USD2010/tCO2 in 2040
    # add carbon price
    tax_emission = make_df(
        tax_emission_df,
        value=carbon_tax
        * (44 / 12)
        / 1.10774
        * 1.05 ** (pd.Series(horizon) - 2040)
        * period_correction,
    )  # add exponential growing carbon price of 80 USD2010/tCO2 in 2040

    scenario.check_out()
    scenario.add_par("tax_emission", tax_emission)
    scenario.commit("diagnostic carbon price added")


# %% md
## Estimate LIB cost
def estimate_lib_cost():
    # WAS SET AS MARKDOWN in notebook, so maybe not needed?
    cost_lib = batt_size.copy()
    costs = [250, 250, 200, 200, 150, 150, 150, 150, 150, 150, 150, 150, 150, 150]
    # costs = [350, 350, 300, 300, 250, 250, 250, 250, 250, 250, 250, 250, 250, 250]
    EV_fake = [
        "ELC_100",
        "ELC_100",
        "ELC_100",
        "ELC_100",
        "ELC_100",
        "ELC_100",
        "ELC_100",
        "ELC_100",
        "ELC_100",
        "ELC_100",
        "ELC_100",
        "ELC_100",
        "ELC_100",
        "ELC_100",
    ]

    cost_phev = batt_size.copy()
    cost_phev[0] = 20
    PHEV_fake = [
        "PHEV_ptrp",
        "PHEV_ptrp",
        "PHEV_ptrp",
        "PHEV_ptrp",
        "PHEV_ptrp",
        "PHEV_ptrp",
        "PHEV_ptrp",
        "PHEV_ptrp",
        "PHEV_ptrp",
        "PHEV_ptrp",
        "PHEV_ptrp",
        "PHEV_ptrp",
        "PHEV_ptrp",
        "PHEV_ptrp",
    ]

    cost_evs = scenario.par("inv_cost")
    cost_evs = cost_evs[cost_evs["technology"] == "ELC_100"]

    cost_evs_phev = scenario.par("inv_cost")
    cost_evs_phev = cost_evs_phev[cost_evs_phev["technology"] == "PHEV_ptrp"]

    cost_lib["cost"] = costs
    cost_lib[0] = cost_lib[0] * cost_lib["cost"]
    cost_lib = cost_lib.rename(columns={"index": "year_vtg", 0: "lib_cost"})
    cost_lib["technology"] = EV_fake

    cost_phev["cost"] = costs
    cost_phev[0] = cost_phev[0] * cost_phev["cost"]
    cost_phev = cost_phev.rename(columns={"index": "year_vtg", 0: "lib_cost"})
    cost_phev["technology"] = PHEV_fake

    cost_evs = pd.merge(cost_evs, cost_lib, how="left").fillna(0)
    cost_evs["value"] = cost_evs["value"] - cost_evs["lib_cost"]
    cost_evs = cost_evs.drop(["lib_cost", "cost"], axis=1)

    cost_evs_phev = pd.merge(cost_evs_phev, cost_phev, how="left").fillna(0)
    cost_evs_phev["value"] = cost_evs_phev["value"] - cost_evs_phev["lib_cost"]
    cost_evs_phev = cost_evs_phev.drop(["lib_cost", "cost"], axis=1)

    results = pd.concat([cost_evs, cost_evs_phev], axis=0)


# %% md
## Bound new cap here
def add_bound_new_cap(scenario):
    df = pd.read_excel("out_cap.xlsx", sheet_name="Sheet1")  # , nrows = 40)

    # scenario.add_par('soft_new_capacity_up', df)
    scenario.add_par("bound_total_capacity_lo", df)

    scenario.commit("test_cap_up")


def update_costs():
    new_cost_techs = ["ICE_conv", "ELC_100", "PHEV_ptrp"]

    cost_techs = scenario.par("inv_cost")[
        scenario.par("inv_cost")["technology"].isin(new_cost_techs)
    ]

    cost_techs["value"].loc[cost_techs["technology"] == "ELC_100"] = 12200
    cost_techs["value"].loc[cost_techs["technology"] == "PHEV_ptrp"] = 14500
    cost_techs["value"].loc[cost_techs["technology"] == "ICE_conv"] = 17000
    scenario.check_out()
    scenario.add_par("inv_cost", cost_techs)
    # scenario.add_par("inv_cost",inv_cost_phev)

    scenario.commit("cheaper_EVs_PHEVs")


# %% md
## Try to change capacity factor of EVs
def change_cap_factor():
    ptrp_techs2 = ["ELC_100", "PHEV_ptrp"]  # is MD in notebook

    cap_factor_new = scenario.par("capacity_factor")
    cap_factor_new = cap_factor_new[cap_factor_new["technology"].isin(prtp_techs)]

    cap_factor_new["mileage_multiplier"] = mileage / cap_factor_new["value"]
    cap_factor_new["value"] = (
        cap_factor_new["value"] * cap_factor_new["mileage_multiplier"]
    )
    cap_factor_new = cap_factor_new.drop(["mileage_multiplier"], axis=1)

    cap_factor_update = scenario.par("capacity_factor")
    cap_factor_update.update(cap_factor_new)
    cap_factor_update = cap_factor_update.astype({"year_vtg": int, "year_act": int})

    technical_lifetime_evs = scenario.par("technical_lifetime")
    technical_lifetime_evs = technical_lifetime_evs[
        technical_lifetime_evs["technology"].isin(prtp_techs)
    ]

    technical_lifetime_evs["lifetime_multiplier"] = (
        lifetime / technical_lifetime_evs["value"]
    )
    technical_lifetime_evs["value"] = (
        technical_lifetime_evs["value"] * technical_lifetime_evs["lifetime_multiplier"]
    )
    technical_lifetime_evs = technical_lifetime_evs.drop(
        ["lifetime_multiplier"], axis=1
    )

    tech_life = scenario.par("technical_lifetime")
    tech_life.update(technical_lifetime_evs)
    tech_life = tech_life.astype({"year_vtg": int, "value": int})

    scenario.check_out()
    scenario.add_par("technical_lifetime", tech_life)
    scenario.add_par("capacity_factor", cap_factor_new)

    scenario.commit("changing lifetime and km")


# %% md
## Addon here
years_df = scenario.vintage_and_active_years()
years_df = years_df.loc[years_df["year_vtg"] >= 2020]
years_df_final = pd.DataFrame(columns=["year_vtg", "year_act"])

for vtg in years_df["year_vtg"].unique():
    years_df_temp = years_df.loc[years_df["year_vtg"] == vtg]
    years_df_temp = years_df_temp.loc[years_df["year_act"] < vtg + lifetime]
    years_df_final = pd.concat([years_df_temp, years_df_final], ignore_index=True)
vintage_years, act_years = years_df_final["year_vtg"], years_df_final["year_act"]


# %% md
## PHEVs addon
def add_phev_addon():
    addon_libs_comm_phev = []
    addon_libs_techs_phev = []
    scenario.add_set("commodity", "PHEV_LIB")

    for comm in unique_commodities:
        for region in regions:
            if "LIB" in comm:
                addon_libs_techs_phev.append("PHEV_ptrp_" + str(comm))
                scenario.add_set("technology", "PHEV_ptrp_" + str(comm))

                tech_in = make_df(
                    "input",
                    # **base_input,
                    node_loc=region,
                    node_origin=region,
                    technology="PHEV_ptrp_" + str(comm),
                    year_vtg=vintage_years,
                    year_act=act_years,
                    mode="all",
                    time="year",
                    time_origin="year",
                    commodity=comm,
                    level="final",
                    value=1,
                    unit="GWh",
                )
                scenario.add_par("input", tech_in)

                tech_out = make_df(
                    "output",
                    # **base_output,
                    node_loc=region,
                    node_dest=region,
                    technology="PHEV_ptrp_" + str(comm),
                    commodity="PHEV_LIB",
                    year_vtg=vintage_years,
                    year_act=act_years,
                    mode="all",
                    time="year",
                    time_dest="year",
                    level="useful",
                    value=1.0,
                    unit="GWh",
                )
                scenario.add_par("output", tech_out)

                LIB_in_PHEV = make_df(
                    "input",
                    # **base_output,
                    node_loc=region,
                    node_origin=region,
                    technology="PHEV_ptrp",
                    commodity="PHEV_LIB",
                    year_vtg=vintage_years,
                    year_act=act_years,
                    mode="all",
                    time="year",
                    time_origin="year",
                    level="useful",
                    value=1 / (mileage * lifetime),
                    unit="GWh/Mvehicle",
                )
                scenario.add_par("input", LIB_in_PHEV)

    addon_libs_techs_phev = list(set(addon_libs_techs_phev))
    for tech in addon_libs_techs_phev:
        scenario.add_set("addon", tech)

    type_addon = "LIBs_for_PHEVs"
    tech = "PHEV_ptrp"

    scenario.add_cat("addon", type_addon, addon_libs_techs_phev)

    scenario.add_set(
        "map_tec_addon", pd.DataFrame({"technology": tech, "type_addon": [type_addon]})
    )

    for region in regions:
        df = pd.DataFrame(
            {
                "node": region,
                "technology": tech,
                "year_vtg": vintage_years,
                "year_act": act_years,
                "mode": "all",
                "time": "year",
                "type_addon": type_addon,
                "value": 1,
                "unit": "-",
            }
        )
        scenario.add_par("addon_conversion", df)

        df = pd.DataFrame(
            {
                "node": region,
                "technology": tech,
                "year_act": act_years,
                "mode": "all",
                "time": "year",
                "type_addon": type_addon,
                "value": 1,
                "unit": "-",
            }
        )
        scenario.add_par("addon_lo", df)

        input_cap_new = pd.DataFrame(
            {
                "node_loc": region,
                "technology": "PHEV_ptrp",
                "year_vtg": batt_size["index"],
                "node_origin": region,
                "commodity": "PHEV_LIB",
                "level": "useful",
                "time": "year",
                "time_origin": "year",
                "value": 15,
                "unit": "GWh/Mvehicle",
            }
        )
        scenario.add_par("input_cap_new", input_cap_new)

    for region in regions:
        for tech in addon_libs_techs_phev:
            LIB_cap = make_df(
                "capacity_factor",
                node_loc=region,
                technology=tech,
                year_vtg=vintage_years,
                year_act=act_years,
                time="year",
                value=1 / (mileage),
                unit="GWh/Mvehicle",
            )
            scenario.add_par("capacity_factor", LIB_cap)


# %% md
## BEVs addon
def add_bev_addon():
    addon_libs_comm = []
    addon_libs_techs = []
    scenario.add_set("commodity", "EV_LIB")

    for comm in unique_commodities:
        for region in regions:
            if "LIB" in comm:
                addon_libs_techs.append("ELC100_" + str(comm))
                scenario.add_set("technology", "ELC100_" + str(comm))

                tech_in = make_df(
                    "input",
                    # **base_input,
                    node_loc=region,
                    node_origin=region,
                    technology="ELC100_" + str(comm),
                    year_vtg=vintage_years,
                    year_act=act_years,
                    mode="all",
                    time="year",
                    time_origin="year",
                    commodity=comm,
                    level="final",
                    value=1,
                    unit="GWh",
                )
                scenario.add_par("input", tech_in)

                tech_out = make_df(
                    "output",
                    # **base_output,
                    node_loc=region,
                    node_dest=region,
                    technology="ELC100_" + str(comm),
                    commodity="EV_LIB",
                    year_vtg=vintage_years,
                    year_act=act_years,
                    mode="all",
                    time="year",
                    time_dest="year",
                    level="useful",
                    value=1.0,
                    unit="GWh",
                )
                scenario.add_par("output", tech_out)

                LIB_in_ELC = make_df(
                    "input",
                    # **base_output,
                    node_loc=region,
                    node_origin=region,
                    technology="ELC_100",
                    commodity="EV_LIB",
                    year_vtg=vintage_years,
                    year_act=act_years,
                    mode="all",
                    time="year",
                    time_origin="year",
                    level="useful",
                    value=1 / (mileage * lifetime),
                    unit="GWh/Mvehicle",
                )
                scenario.add_par("input", LIB_in_ELC)

    addon_libs_techs = list(set(addon_libs_techs))
    for tech in addon_libs_techs:
        scenario.add_set("addon", tech)

    type_addon = "LIBs_for_EVs"
    tech = "ELC_100"

    scenario.add_cat("addon", type_addon, addon_libs_techs)

    scenario.add_set(
        "map_tec_addon", pd.DataFrame({"technology": tech, "type_addon": [type_addon]})
    )

    for region in regions:
        df = pd.DataFrame(
            {
                "node": region,
                "technology": tech,
                "year_vtg": vintage_years,
                "year_act": act_years,
                "mode": "all",
                "time": "year",
                "type_addon": type_addon,
                "value": 1,
                "unit": "-",
            }
        )
        scenario.add_par("addon_conversion", df)

    for region in regions:
        df = pd.DataFrame(
            {
                "node": region,
                "technology": tech,
                "year_act": act_years,
                "mode": "all",
                "time": "year",
                "type_addon": type_addon,
                "value": 1,
                "unit": "-",
            }
        )
        scenario.add_par("addon_lo", df)

    for region in regions:
        input_cap_new = pd.DataFrame(
            {
                "node_loc": region,  ## this has to be each region
                "technology": "ELC_100",  ## ELC 100?
                "year_vtg": batt_size["index"],
                "node_origin": region,  ## Each region
                "commodity": "EV_LIB",
                "level": "useful",
                "time": "year",
                "time_origin": "year",
                "value": batt_size[0],
                "unit": "GWh/Mvehicle",
            }
        )
        # print(input_cap_new)
        scenario.add_par("input_cap_new", input_cap_new)

    for region in regions:
        for tech in addon_libs_techs:
            LIB_cap = make_df(
                "capacity_factor",
                node_loc=region,
                technology=tech,
                year_vtg=vintage_years,
                year_act=act_years,
                time="year",
                value=1 / (mileage),
                unit="GWh/Mvehicle",
            )
            scenario.add_par("capacity_factor", LIB_cap)


# %% md
## Adding resource volume
def add_ressource_volume(scenario):
    df = pd.read_excel(FILENAME, sheet_name="resource_volume")
    scenario.add_par("resource_volume", df)
    scenario.commit("Added resources volumes")
    scenario.check_out()

    df = pd.read_excel(FILENAME, sheet_name="resource_cost")
    scenario.add_par("resource_cost", df)
    scenario.commit("Added resources cost")
    scenario.check_out()


# %% md
## Add accounting of CO2 emissions from transport as a separate set
## Also add tax on those CO2 emissions from LDVs
def add_co2_accounting():
    scenario.add_set("type_tec", "transport")

    df = scenario.par("input")

    unique = pd.DataFrame()
    for tech in prtp_techs:
        x = df[df["technology"].str.contains(tech)]
        unique = unique._append(x, ignore_index=True)

    techs_to_dump = unique["technology"].unique()

    for thing in techs_to_dump:
        scenario.add_set("cat_tec", ["transport", thing])

    scenario.commit("added cat_tec for emissions")

    tax_emission_df = {
        "node": "World",
        "type_emission": "CO2",
        "type_tec": "transport",
        "type_year": horizon,
        "unit": "USD/tCO2",
    }

    # calculate period correction factor to reflect average carbon price in a period
    length5 = sum(1.05 ** pd.Series([-4, -3, -2, -1, 0])) / 5  # for 5-year periods
    length10 = (
        sum(1.05 ** pd.Series([-9, -8, -7, -6, -5, -4, -3, -2, -1, 0])) / 10
    )  # for 10-year periods
    period_correction = (
        pd.Series([length5] * 9)
        ._append(pd.Series([length10] * 4))
        .reset_index(drop=True)
    )  # combine correction factors for 5- and 10-year periods

    # add exponential growing carbon price of 80 USD2010/tCO2 in 2040
    # add carbon price
    tax_emission = make_df(
        tax_emission_df,
        value=transport_CO2_tax
        * (44 / 12)
        / 1.10774
        * 1.05 ** (pd.Series(horizon) - 2040)
        * period_correction,
    )  # add exponential growing carbon price of 80 USD2010/tCO2 in 2040

    scenario.check_out()
    scenario.add_par("tax_emission", tax_emission)
    scenario.commit("added CO2 emissions_transport")


# %% md
## Add emission bounds
def add_emi_bound():
    emissions_bound_df = {
        "node": "World",
        "type_emission": "CO2",
        "type_tec": "transport",
        "type_year": horizon,
        "unit": "tCO2",
    }
    # %% md
    6e5 * (44 / 12) / 1.10774 / 1.01 ** (pd.Series(horizon) - 2050)
    # %% md
    emission_bound = make_df(
        emissions_bound_df,
        value=6e5 * (44 / 12) / 1.10774 / 1.01 ** (pd.Series(horizon) - 2050),
    )
    # %% md
    emission_bound
    # %% md
    scenario.check_out()
    # %% md
    scenario.add_par("bound_emission", emission_bound)
    # %% md
    scenario.commit("added emission bound")
    # %% md
    scenario.commit("stuff")
