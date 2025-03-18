from matplotlib.backends.backend_pdf import PdfPages

from ..scenariomip_plots import create_mip_figs, read_mip_scenarios

py_df = read_mip_scenarios("2.4")
figs = create_mip_figs(py_df, ["World"])

with PdfPages("test_v2-4.pdf") as pdf:
    for fig in figs:
        pdf.savefig(fig, bbox_inches="tight")
