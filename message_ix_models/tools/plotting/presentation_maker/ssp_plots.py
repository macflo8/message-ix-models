from typing import TYPE_CHECKING, List

import matplotlib.pyplot as plt

from message_ix_models.tools.plotting.presentation_maker.reporter_utils import (
    get_filtered_data,
)
from message_ix_models.tools.plotting.presentation_maker.utils import (
    common_starting_substring,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pyam import IamDataFrame


def plot_sector_production_by_tec(
    py_df: "IamDataFrame", sector: str, ax_iter: "Iterator"
):
    py_df_tmp = py_df.filter(variable=f"{sector}|*")
    prods = {i.split("|")[1] for i in py_df_tmp.variable}
    for prod in prods:
        py_df_tmp_prod = py_df_tmp.filter(variable=f"{sector}|{prod}*")
        if prod == "High-Value Chemicals":
            ax = next(ax_iter)
            ax.set_visible(False)
            sub_prods = {i.split("|")[2] for i in py_df_tmp_prod.variable}
            for sub in sub_prods:
                ax = next(ax_iter)
                py_df_tmp.filter(variable=f"{sector}|{prod}|{sub}|*").aggregate_region(
                    variable=f"{sector}|{prod}|{sub}|*"
                ).plot.stack(title=sub, ax=ax)
                ax.legend(
                    ax.get_legend_handles_labels()[0],
                    [
                        i.replace(f"{sector}|{prod}|{sub}|", "")
                        for i in ax.get_legend_handles_labels()[1]
                    ],
                )
        else:
            ax = next(ax_iter)
            py_df_tmp.filter(variable=f"{sector}|{prod}*").aggregate_region(
                variable=f"*{prod}*"
            ).plot.stack(title=prod, ax=ax)
            ax.legend(
                ax.get_legend_handles_labels()[0],
                [
                    i.replace(f"{sector}|{prod}|", "")
                    for i in py_df_tmp.filter(variable=f"{sector}|{prod}|*").variable
                ],
            )


def plot_two_by_two(
    py_df: "IamDataFrame", vars: List[str], region="World", method="Total"
):
    fig, ax = plt.subplots(2, 2, figsize=(14, 8))
    ax_it = iter(fig.axes)

    for i, var in enumerate(vars):
        legend_flag = False
        if i == 0:
            legend_flag = True
        ax = next(ax_it)
        get_filtered_data(py_df, var, method, region=region).plot(
            ax=ax, title=var, legend=legend_flag
        )
        ax.set_xlabel("")
        plt.tight_layout()
    fig.suptitle(vars[0].split("|")[0] + " per " + method, fontsize=20, x=0.5, y=1.05)
    return fig


def plot_triplet(py_df: "IamDataFrame", var: str, region="World"):
    fig, ax = plt.subplots(2, 3, figsize=(16, 9))
    ax_it = iter(fig.axes)
    ax = next(ax_it)
    get_filtered_data(py_df, var, region=region).plot(ax=ax, title="Total")
    ax.set_xlabel("")
    ax = next(ax_it)
    ax.set_visible(False)
    ax = next(ax_it)
    get_filtered_data(py_df, var, "POP", region=region).plot(
        ax=ax, title="Per POP", legend=False
    )
    ax.set_xlabel("")
    ax = next(ax_it)
    ax.set_visible(False)
    ax = next(ax_it)
    get_filtered_data(py_df, var, "GDP", region=region).plot(
        ax=ax, title="Per GDP", legend=False
    )
    ax.set_xlabel("")
    ax = next(ax_it)
    ax.set_visible(False)
    plt.tight_layout()
    fig.suptitle(var, fontsize=20, x=0.5, y=1.05)
    return fig


def plot_ssp_layout(py_df_all: "IamDataFrame", vars: List[str], region="World"):
    fig, ax = plt.subplots(3, 3, figsize=(20, 20 / 1.7777))
    ax_it = iter(fig.axes)
    y_max = 0

    if len(py_df_all.model) > 6:
        raise ValueError("Too many models to plot SSP layout")

    for model in [5, 3, 2, 1, 4]:
        model_str = [i for i in py_df_all.model if f"SSP{model}" in i][0]
        ax = next(ax_it)
        if model != 5:
            ax.set_visible(False)
        if model != 5:
            ax = next(ax_it)
        # special formatting for SSP2
        if model == 2:
            py_df_all.filter(model=model_str, variable=vars, region=region).plot.stack(
                ax=ax, title=f"SSP{model}", legend=True
            )
            ax.set_position([0.36, 0.35, 0.3, 0.3])
            fig.legend(
                ax.get_legend_handles_labels()[0],
                [
                    i.replace(common_starting_substring(vars), "")
                    for i in ax.get_legend_handles_labels()[1]
                ],
                fontsize=13,
                loc=[0.72, 0.34],
            )
            ax.get_legend().set_visible(False)
        else:
            py_df_all.filter(model=model_str, variable=vars, region=region).plot.stack(
                ax=ax, title=f"SSP{model}", legend=False
            )
        if y_max < ax.get_ylim()[1]:
            y_max = ax.get_ylim()[1]

    ax_it = iter(fig.axes)
    for i in range(9):
        ax = next(ax_it)
        ax.set_ylim(0, y_max)
        ax.set_xlabel("")
        ax.set_title(ax.get_title(), fontsize=15)
    fig.suptitle(common_starting_substring(vars)[:-1], fontsize=20, x=0.52, y=0.93)
    return fig
