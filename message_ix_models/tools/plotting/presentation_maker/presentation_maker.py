import pickle
from typing import TYPE_CHECKING, List, Literal

import matplotlib.pyplot as plt
import matplotlib.transforms
import pyam
from matplotlib.backends.backend_pdf import PdfPages

from message_ix_models.tools.plotting.presentation_maker.constants import (
    EMI_SECTORS,
    FE_SECTORS,
    FE_VARS,
    SECTORS,
)
from message_ix_models.tools.plotting.presentation_maker.reporter_utils import (
    add_co2_industry_aggregate,
    dump_to_pkl,
    get_all_ssp_pyam_df,
)
from message_ix_models.tools.plotting.presentation_maker.ssp_plots import (
    get_filtered_data,
    plot_ssp_layout,
    plot_triplet,
    plot_two_by_two,
)

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure
    from pyam import IamDataFrame


def plot_LED_on_SSP_grid(py_df: "IamDataFrame", reg: str, vars: List[str], ax: "Axes"):
    ax.set_visible(True)
    points = ax.get_position().get_points()
    points[1] *= 0.95
    points[0][0] *= 1.02
    points[0] *= 1.05
    ax.set_position(matplotlib.transforms.Bbox(points))
    py_df.filter(
        model=[i for i in py_df.model if "LED" in i], variable=vars, region=reg
    ).plot.stack(title="LED", legend=False, ax=ax)
    ax.set_xlabel("")


def plot_fe_by_fuel(py_df: "IamDataFrame", reg: str) -> List["Figure"]:
    figs = []
    fig = plot_ssp_layout(py_df, FE_VARS, region=reg)
    ax_led_scenario = fig.axes[-2]
    plot_LED_on_SSP_grid(py_df, reg, FE_VARS, ax_led_scenario)
    figs.append(fig)

    for sector in FE_SECTORS:
        vars_sec = [var.replace("Industry", f"Industry|{sector}") for var in FE_VARS]
        fig = plot_ssp_layout(py_df, vars_sec, region=reg)
        ax_led_scenario = fig.axes[-2]
        plot_LED_on_SSP_grid(py_df, reg, vars_sec, ax_led_scenario)
        figs.append(fig)
    return figs


def plot_fe_triplets(py_df: "IamDataFrame", reg: str) -> List["Figure"]:
    figs = []
    var = "Final Energy|Industry"
    fig = plot_triplet(py_df, var, reg)
    fig.axes[4].set_ylabel("EJ / yr / M$")
    figs.append(fig)

    for sector in FE_SECTORS:
        fig = plot_triplet(py_df, var + "|" + sector)
        fig.axes[4].set_ylabel("EJ / yr / M$")
        figs.append(fig)
    return figs


def plot_fe(py_df: "IamDataFrame", reg: str, title: str) -> "Figure":
    var = "Final Energy|Industry"
    fig, ax = plt.subplots()
    get_filtered_data(py_df, var, "Total", region=reg).plot(ax=ax, title=title)
    ax.set_xlabel("")
    ax.set_ylim(0, 455)
    return fig


def plot_emi(py_df: "IamDataFrame", reg: str = "World") -> List["Figure"]:
    try:
        add_co2_industry_aggregate(py_df, EMI_SECTORS)
    except ValueError:
        print("CO2 Emission aggregate (process+energy) is already present in dataframe")
        pass

    figs = [plot_emi_sectors(py_df, reg), plot_emi_total(py_df, reg)]
    return figs


def plot_emi_sectors(py_df: "IamDataFrame", reg: str) -> "Figure":
    var = "Emissions|CO2|Industry|"
    fig, ax = plt.subplots(3, 2, figsize=(16, 9))
    ax_it = iter(fig.axes)
    for i, sector in enumerate(EMI_SECTORS):
        legend_flag = False
        if i == 0:
            legend_flag = True
        ax = next(ax_it)
        get_filtered_data(py_df, var + sector, region=reg).plot(
            title=sector, ax=ax, legend=legend_flag
        )
        ax.set_xlabel("")
    ax = next(ax_it)
    ax.set_visible(False)
    return fig


def plot_emi_total(py_df: "IamDataFrame", reg: str) -> "Figure":
    fig, axs = plt.subplots(1, 2, figsize=(16, 9))
    ax_it = iter(fig.axes)
    for var in [
        "Emissions|CO2|Energy|Demand|Industry",
        "Emissions|CO2|Industrial Processes",
    ]:
        ax = next(ax_it)
        get_filtered_data(py_df, var, region=reg).plot(title=var, ax=ax)
    return fig


def plot_prod_line(
    py_df: "IamDataFrame", reg: str, var_type: Literal["Total", "GDP", "POP"] = "Total"
) -> List["Figure"]:
    var_prefix = "Production|"
    vars = [var_prefix + i for i in SECTORS[:-1]]
    fig = plot_two_by_two(py_df, vars, region=reg, method=var_type)
    if var_type == "GDP":
        for ax in fig.axes:
            ax.set_ylabel("Mt / yr / M$")
    return [fig]


def print_pptx_plots(version: int, regions: List[str]):
    with open(f"{version}_baseline.p", "rb") as f:
        py_df_base = pickle.load(f)
    with open(f"{version}_1000f.p", "rb") as f:
        py_df_1000f = pickle.load(f)

    for reg in regions:
        figs = []
        figs.extend(plot_prod_line(py_df_base, reg, "Total"))
        figs.extend(plot_prod_line(py_df_base, reg, "GDP"))
        figs.extend(plot_prod_line(py_df_base, reg, "POP"))

        figs.append(plot_fe(py_df_base, reg, "Baseline"))
        figs.append(plot_fe(py_df_1000f, reg, "1000 Gt full century budget"))

        figs.extend(plot_fe_by_fuel(py_df_base, reg))
        figs.extend(plot_fe_by_fuel(py_df_1000f, reg))

        try:
            add_co2_industry_aggregate(py_df_1000f, SECTORS)
        except ValueError:
            pass
        try:
            add_co2_industry_aggregate(py_df_base, SECTORS)
        except ValueError:
            pass
        figs.extend(plot_emi(py_df_base, reg))
        figs.extend(plot_emi(py_df_1000f, reg))
        for i, fig in enumerate(figs):
            fig.savefig(f"pptx_plots/{reg}_plot{i}.svg", bbox_inches="tight")


def main(
    scenario: str,
    version: int,
    cached: bool,
    regions: List[str],
    path: str,
    include_led_scenario: bool = False,
):
    if scenario == "baseline":
        ssp2_fname = f"SSP_dev_SSP2_v1.0_Blv1.{version}_baseline_prep_lu_bkp_solved_materials.xlsx"
    elif scenario == "1000f":
        # path = f"C:/Users/maczek/Desktop/SSP_dev reporting results/SSP_dev_{version}_results/"
        ssp2_fname = f"SSP_dev_SSP2_v1.0_Blv1.{version}_baseline_prep_lu_bkp_solved_materials_2030_macro_1000f.xlsx"
    else:
        print(f"Scenario: {scenario} is not available.")
        return
    if cached:
        with open(f"{version}_{scenario}.p", "rb") as f:
            py_df_all = pickle.load(f)
    else:
        py_df_all = get_all_ssp_pyam_df(path, ssp2_fname, with_LED=include_led_scenario)
        dump_to_pkl(py_df_all, str(version) + "_" + scenario)
    py_df_all.filter(year=[i for i in range(1990, 2020, 5)], keep=False, inplace=True)
    for reg in regions:
        figs = []
        figs.extend(plot_prod_line(py_df_all, reg))
        figs.extend(plot_fe_triplets(py_df_all, reg))
        figs.extend(plot_fe_by_fuel(py_df_all, reg))
        figs.extend(plot_emi(py_df_all, reg))
        with PdfPages(f"ssp_v{version}_{reg}_{scenario}.pdf") as pdf:
            for fig in figs:
                pdf.savefig(fig, bbox_inches="tight")


def create_figure_set(py_df, reg):
    figs = []
    figs.extend(plot_prod_line(py_df, reg))
    figs.extend(plot_fe_triplets(py_df, reg))
    figs.extend(plot_fe_by_fuel(py_df, reg))
    figs.extend(plot_emi(py_df, reg))
    return figs


def read_scenarios(path, files):
    _py_df_list = []
    for file in files:
        if not file.endswith("xlsx"):
            continue
        py_df = pyam.IamDataFrame(data=path + file)
        _py_df_list.append(py_df)
    py_df_all = pyam.concat(_py_df_list)
    py_df_all = pyam.IamDataFrame(py_df_all.timeseries().fillna(0))
    return py_df_all
