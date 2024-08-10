import matplotlib.pyplot as plt
from data_batteries import COMMENTS, MOD
from ixmp.report import configure
from message_ix import Reporter


def notebook_visualization(scenario):
    fig, ax = plt.subplots()
    scenario.var("CAP_NEW")[scenario.var("CAP_NEW")["technology"] == "ELC_100"].groupby(
        ["technology", "year_vtg"]
    ).sum()["lvl"].swaplevel(0, 1).sort_index(axis=0, level=0).unstack().sum(
        axis=1
    ).plot()
    ax.set_xlim(2025, 2100)
    plt.savefig("NEW_BEVS.jpg")

    fig, ax = plt.subplots()
    scenario.var("ACT")[
        scenario.var("ACT")["technology"] == "NMC811_LIBmanufacturing"
    ].groupby(["technology", "year_act"]).sum()["lvl"].swaplevel(0, 1).sort_index(
        axis=0, level=0
    ).unstack().sum(axis=1).plot()
    ax.set_xlim(2025, 2100)
    plt.savefig("ACT_NMC811.jpg")

    fig, ax = plt.subplots()
    scenario.var("ACT")[
        scenario.var("ACT")["technology"] == "NMC622_LIBmanufacturing"
    ].groupby(["technology", "year_act"]).sum()["lvl"].swaplevel(0, 1).sort_index(
        axis=0, level=0
    ).unstack().sum(axis=1).plot()
    ax.set_xlim(2025, 2100)
    plt.savefig("ACT_NMC622.jpg")

    fig, ax = plt.subplots()
    scenario.var("ACT")[
        scenario.var("ACT")["technology"] == "NCA_LIBmanufacturing"
    ].groupby(["technology", "year_act"]).sum()["lvl"].swaplevel(0, 1).sort_index(
        axis=0, level=0
    ).unstack().sum(axis=1).plot()
    ax.set_xlim(2025, 2100)
    plt.savefig("ACT_NCA.jpg")

    fig, ax = plt.subplots()
    scenario.var("ACT")[
        scenario.var("ACT")["technology"] == "LFP_LIBmanufacturing"
    ].groupby(["technology", "year_act"]).sum()["lvl"].swaplevel(0, 1).sort_index(
        axis=0, level=0
    ).unstack().sum(axis=1).plot()
    ax.set_xlim(2025, 2100)
    plt.savefig("ACT_LFP.jpg")

    fig, ax = plt.subplots()
    scenario.var("CAP")[scenario.var("CAP")["technology"] == "ELC_100"].groupby(
        ["technology", "year_act"]
    ).sum()["lvl"].swaplevel(0, 1).sort_index(axis=0, level=0).unstack().sum(
        axis=1
    ).plot()
    ax.set_xlim(2025, 2100)
    plt.savefig("CAP_ELC100.jpg")


def notebook_reporting_and_plotting(mp, scenario, regions):
    rep = Reporter.from_scenario(scenario)
    configure(units={"replace": {"-": ""}})
    df = rep.get("message::default")

    # To dump the reporting data to an Excel file if not already done
    # This is not directly saved as xlsx,
    # one should go to the generated file and save again.

    name = MOD + "_" + COMMENTS + "_message_ix.xlsx"
    df.to_excel(name)

    df.filter(variable="CAP|capacity|PHEV_ptrp", region=regions).plot()

    df.filter(variable="CAP_NEW|new capacity|ELC_100", region=regions).plot()

    df.filter(variable="CAP|capacity|ELC_100", region=regions).plot()

    df.filter(variable="CAP|capacity|ICE_conv", region=regions).plot()

    df.filter(variable="CAP|capacity|HFC_ptrp", region=regions).plot()

    LIBs = [
        "CAP|capacity|NMC811_LIBmanufacturing",
        "CAP|capacity|NMC622_LIBmanufacturing",
        "CAP|capacity|NCA_LIBmanufacturing",
        "CAP|capacity|LFP_LIBmanufacturing",
    ]

    df.filter(variable=LIBs, region=regions).plot()

    import message_data.tools.post_processing.iamc_report_hackathon

    message_data.tools.post_processing.iamc_report_hackathon.report(
        mp,
        scenario,
        # NB(PNK) this is not an error; .iamc_report_hackathon.report() expects a
        #         string containing "True" or "False" instead of an actual bool.
        "False",
        scenario.model,
        scenario.scenario,  # .replace("_test_calib_macro", ""),
        merge_hist=False,  # merge_hist=True,
        merge_ts=True,
        run_config="materials_run_config.yaml",
    )
