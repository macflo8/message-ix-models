import itertools
import os
import pathlib
import pickle
from typing import TYPE_CHECKING, List

import pandas as pd
import pyam
from pyam import IamDataFrame

from message_ix_models.model.material.util import read_yaml_file
from message_ix_models.report import Reporter

if TYPE_CHECKING:
    from message_ix import Scenario


def create_var_map_from_yaml_dict(dictionary):
    data = dictionary["vars"]
    all = pd.DataFrame()
    for key in data:
        # Extract relevant information
        filter_data = data[key]["filter"]
        short_name = data[key]["short"]
        # Create a list to hold the modified entries
        modified_entries = []
        # Iterate over the list of technologies
        if isinstance(filter_data["technology"], list):
            for tech in filter_data["technology"]:
                if isinstance(filter_data["mode"], list):
                    for mode in filter_data["mode"]:
                        # Create a new entry for each technology
                        new_entry = {
                            "key": key,
                            "technology": tech,
                            "mode": mode,
                            "commodity": filter_data["commodity"],
                            "level": filter_data["level"],
                            "short": short_name,
                        }
                        modified_entries.append(new_entry)
                else:
                    # Create a new entry for each technology
                    new_entry = {
                        "key": key,
                        "technology": tech,
                        "mode": filter_data["mode"],
                        "commodity": filter_data["commodity"],
                        "level": filter_data["level"],
                        "short": short_name,
                    }
                    modified_entries.append(new_entry)
        else:
            # Create a new entry for the technology
            if isinstance(filter_data["mode"], list):
                for mode in filter_data["mode"]:
                    # Create a new entry for each technology
                    new_entry = {
                        "key": key,
                        "technology": filter_data["technology"],
                        "mode": mode,
                        "commodity": filter_data["commodity"],
                        "level": filter_data["level"],
                        "short": short_name,
                    }
                    modified_entries.append(new_entry)
            else:
                new_entry = {
                    "key": key,
                    "technology": filter_data["technology"],
                    "mode": filter_data["mode"],
                    "commodity": filter_data["commodity"],
                    "level": filter_data["level"],
                    "short": short_name,
                }
                modified_entries.append(new_entry)
        # Convert to DataFrame
        df = pd.DataFrame(modified_entries)
        all = pd.concat([all, df])
    all = all.rename(
        columns={"mode": "m", "technology": "t", "level": "l", "commodity": "c"}
    ).set_index(keys=["t", "m", "c", "l"])
    return all


def create_var_map_from_yaml_dict2(dictionary):
    data = dictionary["vars"]
    all = pd.DataFrame()
    unit = dictionary["common"]["unit"]
    for iamc_key, values in data.items():
        # Extract relevant information
        filter_data = values["filter"]
        short_name = values["short"]

        # Create a list to hold the modified entries
        # Iterate over the list of technologies
        data = {k: [v] if isinstance(v, str) else v for k, v in filter_data.items()}
        combinations = list(itertools.product(*data.values()))

        # Create DataFrame
        df = pd.DataFrame(combinations, columns=data.keys())
        df["iamc_name"] = iamc_key
        df["short_name"] = short_name
        if "unit" in list(values.keys()):
            df["unit"] = values["unit"]
        else:
            df["unit"] = unit

        # append
        all = pd.concat([all, df])

    rename_dict = {"mode": "m", "technology": "t", "level": "l", "commodity": "c"}
    rename_dict = {k: v for k, v in rename_dict.items() if k in all.columns}

    all = all.rename(columns=rename_dict).set_index(list(rename_dict.values()))
    return all


def save_as_svg(var_type, figure_dict):
    cwd = pathlib.Path(f"{os.getcwd()}/{var_type}")
    if not os.path.isdir(cwd):
        print(f"{cwd} did not exist. created new folder.")
        os.mkdir(cwd)

    for name, fig in figure_dict.items():
        fname = name.replace("|", "_")
        fig.savefig(cwd / f"{fname}.svg", bbox_inches="tight")
        print(f"plot saved as {fname}")


def dump_to_pkl(py_df, fname):
    with open(f"{fname}.p", "wb") as f:
        pickle.dump(py_df, f)


def read_reporting_file(path, fname, rename_model=None):
    df = pd.read_excel(path + fname)
    df = df[~df.Region.isna()]
    df = df.fillna(0)
    if rename_model:
        df["Model"] = rename_model
    py_df = pyam.IamDataFrame(df)
    return py_df


def get_all_ssp_fnames(
    fname: str, to_replace="SSP2", include_led_scenario: bool = False
):
    fnames = {
        f"SSP{ssp}": name.replace(to_replace, "SSP" + str(ssp))
        for name, ssp in zip([fname] * 5, range(1, 6))
    }
    if include_led_scenario:
        fnames["LED"] = fname.replace(to_replace, "LED")
    return fnames


def get_all_ssp_pyam_df(path, ssp2_fname, with_LED=False):
    _py_df_list = []
    for ssp, fname in get_all_ssp_fnames(
        ssp2_fname, include_led_scenario=with_LED
    ).items():
        py_df = read_reporting_file(path, fname, ssp)
        _py_df_list.append(py_df)

    py_df_all = pyam.concat(_py_df_list)
    return py_df_all


def add_co2_industry_aggregate(py_df, sectors):
    a = "Emissions|CO2|Energy|Demand|Industry|"
    b = "Emissions|CO2|Industrial Processes|"
    new_var = "Emissions|CO2|Industry|"
    for sector in sectors:
        py_df.aggregate(
            new_var + sector, components=[a + sector, b + sector], append=True
        )


def pyam_df_from_rep(rep: Reporter, rep_var_dict: dict, model: str, scen: str):
    variable = rep_var_dict["par"]
    df_var = pd.DataFrame(rep.get(f"{variable}:nl-t-ya-m-c-l"))

    mapping_df = create_var_map_from_yaml_dict2(rep_var_dict)

    df = (
        df_var.join(mapping_df[["key", "unit"]])
        .dropna()
        .groupby(["nl", "ya", "key"])
        .sum(numeric_only=True)
    )
    unit_map = (
        mapping_df.reset_index()[["key", "unit"]].drop_duplicates().set_index("key")
    )
    df = df.join(unit_map)
    df = df.rename(columns={variable: "value"})
    df = df.reset_index()

    py_df = df.copy(deep=True)
    py_df["Scenario"] = scen
    py_df["Model"] = model
    py_df = py_df.rename(
        columns={"key": "variable", "nl": "region", "ya": "Year", 0: "value"}
    )
    py_df = pyam.IamDataFrame(py_df)
    return py_df


def get_py_df_all_vars(
    filenames: List[str],
    path: str,
    scenario: "Scenario",
    model_name: str,
    scen_name: str,
):
    dfs = []
    for file in filenames:
        rep_var_dict = read_yaml_file(path + file)
        rep = Reporter.from_scenario(scenario)
        # limit scenario queries of Reporter to all filters set in yaml
        # to optimize performance
        set_rep_filters(rep, rep_var_dict)
        py_df = pyam_df_from_rep(rep, rep_var_dict, model_name, scen_name)
        dfs.append(py_df)
        # reset filters for next query
        rep.set_filters()

    py_df = pyam.concat(dfs)
    return py_df


def set_rep_filters(rep: Reporter, rep_var_dict: dict):
    """
    Applies column filters to given message_ix.Reporter for
    columns: "t", "m", "c", "l" based on variable filters
    defined in "rep_var_dict" generated from *_reporting.yaml

    Parameters
    ----------
    rep: message_ix.Reporter
    rep_var_dict: dict
    """
    filters_dict = {"t": set(), "m": set(), "c": set(), "l": set()}
    col_short_dict_inv = {
        "t": "technology",
        "m": "mode",
        "c": "commodity",
        "l": "level",
    }
    # Iterate through the vars and collect the filters
    for item in rep_var_dict["vars"].values():
        filter_item = item["filter"]
        for key in filters_dict:
            if isinstance(filter_item[col_short_dict_inv[key]], str):
                filters_dict[key].add(filter_item[col_short_dict_inv[key]])
            else:
                filters_dict[key].update(filter_item[col_short_dict_inv[key]])
    rep.set_filters(**filters_dict)


def get_filtered_data(
    py_df: "IamDataFrame", var: str, method: str = "Total", region: str = "World"
):
    if method == "Total":
        return py_df.filter(variable=var).filter(region=region)
    if method == "GDP":
        return py_df.divide(
            var, "GDP|PPP", name="FE per GDP", ignore_units=True
        ).filter(region=region)
    if method == "POP":
        return py_df.divide(var, "Population", name="FE per Pop").filter(region=region)


def get_sector_production_by_tec_list(py_df: "IamDataFrame", sector: str):
    var_dict = {}
    py_df_tmp = py_df.filter(variable=f"{sector}|*")
    prods = {i.split("|")[1] for i in py_df_tmp.variable}
    for prod in prods:
        py_df_tmp_prod = py_df_tmp.filter(variable=f"{sector}|{prod}*")
        if prod == "High-Value Chemicals":
            sub_prods = {i.split("|")[2] for i in py_df_tmp_prod.variable}
            for sub in sub_prods:
                var_dict[sub] = (
                    py_df_tmp.filter(variable=f"{sector}|{prod}|{sub}|*")
                    .aggregate_region(variable=f"{sector}|{prod}|{sub}|*")
                    .variable
                )

        if prod == "Methanol":
            py_df_tmp_meth = (
                py_df_tmp.filter(variable=f"{sector}|{prod}*")
                .aggregate_region(variable=f"*{prod}*")
                .variable
            )
            var_dict[prod] = py_df_tmp_meth

        # if prod == "Clinker":
        #     print("alarm")
        #     py_df_tmp_meth =
        #     py_df_tmp.filter(variable=f"{sector}|{prod}*").aggregate_region(
        #         variable=f"*{prod}*CCS*").variable
        #     var_dict[prod] = py_df_tmp_meth

        else:
            var_dict[prod] = (
                py_df_tmp.filter(variable=f"{sector}|{prod}*")
                .aggregate_region(variable=f"*{prod}*")
                .variable
            )

    return var_dict
