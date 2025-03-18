import pickle
from typing import List

from matplotlib.backends.backend_pdf import PdfPages

from ..presentation_maker import (
    plot_emi,
    plot_fe_by_fuel,
    plot_fe_triplets,
    plot_prod_line,
)
from ..reporter_utils import (
    dump_to_pkl,
    get_all_ssp_pyam_df,
)


def main_ecemp(
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
