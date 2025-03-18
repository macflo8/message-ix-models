import pyam
from matplotlib.backends.backend_pdf import PdfPages

from message_ix_models.tools.plotting.presentation_maker.constants import FE_VARS
from message_ix_models.tools.plotting.presentation_maker.presentation_maker import (
    plot_emi,
    plot_fe_by_fuel,
    plot_fe_triplets,
    plot_prod_line,
)

if __name__ == "__main__":
    data_path = "/Users/florianmaczek/PycharmProjects/"
    dfs = []
    for i in range(1, 5):
        dfs.append(pyam.IamDataFrame(data_path + f"SSP{i}_baseline.xlsx"))
    py_df_all = pyam.concat(dfs)
    py_df_all.aggregate("Final Energy|Industry", components=FE_VARS, append=True)

    for reg in ["World"]:
        figs = []
        figs.extend(plot_prod_line(py_df_all, reg))
        figs.extend(plot_fe_triplets(py_df_all, reg))
        figs.extend(plot_fe_by_fuel(py_df_all, reg))
        figs.extend(plot_emi(py_df_all, reg))
        with PdfPages("test.pdf") as pdf:
            for fig in figs:
                pdf.savefig(fig, bbox_inches="tight")
