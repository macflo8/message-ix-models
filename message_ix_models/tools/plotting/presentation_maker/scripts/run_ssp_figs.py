import os

from matplotlib.backends.backend_pdf import PdfPages

from message_ix_models.tools.plotting.presentation_maker.presentation_maker import (
    create_figure_set,
    read_scenarios,
)

path = "/Users/florianmaczek/Library/CloudStorage/OneDrive-FreigegebeneBibliotheken–IIASA/ECE.prog - Documents/SharedSocioEconomicPathways2023/Scenario_Vetting/v2.3_v2.4_Submission_Mar01_2025/Scenario_Reporting_Files/"

files = os.listdir(path)
files1 = [i for i in files if i.endswith("baseline.xlsx")]
files2 = [i for i in files if i.endswith("High Emissions.xlsx")]
files = files1 + files2

reg = "World"
# pdf_output_name = "SSP_v2.1_baseline"
pdf_output_name = "SSP_v2.4_baselines"

py_df = read_scenarios(path, files)
figs = create_figure_set(py_df, reg)

with PdfPages(f"{pdf_output_name}_{reg}.pdf") as pdf:
    for fig in figs:
        pdf.savefig(fig, bbox_inches="tight")
