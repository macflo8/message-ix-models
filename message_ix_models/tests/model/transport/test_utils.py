import pandas as pd
import pandas.testing as pdt
import xarray as xr

from message_data.model.transport.utils import (
    add_commodity_and_level,
    consumer_groups,
    read_config,
)


def test_add_cl(transport_context):
    """add_commodity_and_level() preserves the content of other columns."""
    # Input data missing 'commodity' and 'level'
    df_in = pd.DataFrame(
        [
            ["R11_AFR", None, None, "ICE_conv"],
            ["R11_WEU", None, None, "ELC_100"],
        ],
        columns=["node", "commodity", "level", "technology"],
    )

    df_out = add_commodity_and_level(df_in, default_level="foo")

    # Output is the same shape
    assert df_out.shape == (2, 4)

    # All NaNs are filled
    assert not df_out.isna().any().any(), df_out

    # Existing columns have the same content
    for col in "node", "technology":
        pdt.assert_series_equal(df_in[col], df_out[col])


def test_read_config(session_context):
    # read_config() returns a reference to the current context
    context = read_config()
    assert context is session_context

    # Data tables are loaded
    assert isinstance(context.data["transport mer-to-ppp"], xr.DataArray)
    assert context.data["transport mer-to-ppp"].dims == ("node", "year")

    # Scalar parameters are loaded
    assert "scaling" in context["transport config"]
    assert context["transport config"]["work hours"] == 200 * 8


def test_consumer_groups(transport_context):
    # Returns a list of codes
    codes = consumer_groups()
    RUEAA = codes[codes.index("RUEAA")]
    assert RUEAA.name == "Rural, or “Outside MSA”, Early Adopter, Average"

    # Returns xarray objects for indexing
    result = consumer_groups(rtype="indexers")
    assert all(isinstance(da, xr.DataArray) for da in result.values())
