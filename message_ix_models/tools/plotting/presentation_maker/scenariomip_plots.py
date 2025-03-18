from typing import TYPE_CHECKING, List, Literal

import matplotlib.pyplot as plt
import pyam

from message_ix_models.tools.plotting.presentation_maker.constants import (
    FE_SECTORS,
    FE_VARS,
)
from message_ix_models.tools.plotting.presentation_maker.presentation_maker import (
    plot_emi,
    plot_fe_triplets,
    plot_prod_line,
)
from message_ix_models.tools.plotting.presentation_maker.utils import (
    common_starting_substring,
)

if TYPE_CHECKING:
    from matplotlib.figure import Figure
    from pyam import IamDataFrame

version_paths = {
    "1.0": "v1.0_Submission3_Nov11_2024/",
    "1.1": "v1.1_Internal_version_Nov25_2024/",
    "2.1": "v2.1_Internal_version_Dec13_2024/Reporting_output/",
    "2.4": "v2.3_v2.4_Submission_Mar01_2025/Scenario_Reporting_Files/",
}
data_path = "/Users/florianmaczek/Library/CloudStorage/OneDrive-FreigegebeneBibliotheken–IIASA/ECE.prog - Documents/SharedSocioEconomicPathways2023/Scenario_Vetting/"


def plot_fe_by_fuel_MIP(py_df: "IamDataFrame", reg: str) -> List["Figure"]:
    figs = []
    slide1 = [
        "SSP1 - Very Low Emissions",
        "SSP1 - Low Emissions",
        "SSP2 - Medium-Low Emissions",
        "SSP2 - Very Low Emissions",
        "SSP2 - Low Emissions",
        "SSP2 - Medium Emissions",
    ]
    slide2 = [
        "SSP2 - Low Overshoot",
        "SSP4 - Low Overshoot",
        "SSP3 - High Emissions",
        None,
        "SSP5 - Low Overshoot",
        "SSP5 - High Emissions",
    ]
    for scens in [slide1, slide2]:
        fig = plot_mip_layout(py_df, FE_VARS, scens, region=reg)
        figs.append(fig)

        for sector in FE_SECTORS:
            vars_sec = [
                var.replace("Industry", f"Industry|{sector}") for var in FE_VARS
            ]
            fig = plot_mip_layout(py_df, vars_sec, scens, region=reg)
            figs.append(fig)
    return figs


def plot_mip_layout(
    py_df_all: "IamDataFrame", vars: List[str], scenario_order, region="World"
):
    fig, ax = plt.subplots(2, 3, figsize=(20, 20 / 1.7777))
    ax_it = iter(fig.axes)
    y_max = 0

    for scen in scenario_order:
        ax = next(ax_it)
        if scen not in py_df_all.scenario:
            continue
        if not scen:
            ax.set_visible(False)
            continue
        py_df_all.filter(scenario=scen, variable=vars, region=region).plot.stack(
            ax=ax, title=f"{scen}", legend=True
        )
        if y_max < ax.get_ylim()[1]:
            y_max = ax.get_ylim()[1]

    ax_it = iter(fig.axes)
    for i in range(6):
        ax = next(ax_it)
        ax.set_ylim(0, y_max)
        ax.set_xlabel("")
        ax.set_title(ax.get_title(), fontsize=15)
    fig.suptitle(common_starting_substring(vars)[:-1], fontsize=20, x=0.52, y=0.93)
    return fig


def read_mip_scenarios(version: Literal["1.0", "1.1"]):
    _py_df_list = []
    path = data_path + version_paths[version]
    import os

    for file in sorted(os.listdir(path)):
        if not file.endswith(".xlsx"):
            continue
        if file.endswith("baseline.xlsx"):
            continue
        if file.endswith("1000f.xlsx"):
            continue
        py_df = pyam.IamDataFrame(data=path + file)
        _py_df_list.append(py_df)
    py_df_all = pyam.concat(_py_df_list)
    py_df_all = pyam.IamDataFrame(py_df_all.timeseries().fillna(0))
    return py_df_all


def create_mip_figs(py_df, regions):
    for reg in regions:
        figs = []
        figs.extend(plot_prod_line(py_df, reg))
        figs.extend(plot_fe_triplets(py_df, reg))
        figs.extend(plot_emi(py_df, reg))
        figs.extend(plot_fe_by_fuel_MIP(py_df, reg))

        for fig in figs:
            # Move the legend from the axis to the figure
            # Step 1: Remove the legend from the axis
            for ax in fig.get_axes():
                if not ax.get_legend():
                    continue
                ax.get_legend().set_visible(False)
                handles, labels = ax.get_legend_handles_labels()

            fig.subplots_adjust(
                bottom=0.17, hspace=0.25
            )  # Values range from 0 (bottom) to 1 (top)
            # Step 2: Collect handles and labels from the axis legend
            # Step 3: Create a figure-level legend with those handles and labels
            fig.legend(
                handles,
                [i.replace("Final Energy|Industry|", "") for i in labels],
                loc=(0.15, 0.02),
                ncol=3,
            )
            # fig.tight_layout()
    return figs
