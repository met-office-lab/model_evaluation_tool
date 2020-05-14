import pytest
import pandas as pd
import pandas.testing as pdt
import datetime as dt
import numpy as np
import glob
import forest.actions
import forest.drivers
from forest.drivers import earth_networks


LINES = [
    "1,20190417T000001.440,+02.7514400,+031.9206400,-000001778,000,15635,007,001",
    "1,20190417T000001.093,+02.6388400,+031.9008800,+000002524,000,14931,007,012"
]


def test_earth_networks(tmpdir):
    path = str(tmpdir / "sample.txt")
    with open(path, "w") as stream:
        stream.writelines(LINES)

    loader = earth_networks.Loader()
    frame = loader.load([path])
    result = frame.iloc[0]
    atol = 0.000001
    if isinstance(result["date"], dt.datetime):
        # Pandas <0.25.x
        assert result["date"] == dt.datetime(2019, 4, 17, 0, 0, 1, 440000)
    else:
        # Pandas 1.0.x
        assert result["date"] == np.datetime64('2019-04-17T00:00:01.440000000')
    assert result["flash_type"] == "IC"
    assert abs(result["latitude"] - 2.75144) < atol
    assert abs(result["longitude"] - 31.92064) < atol


def test_dataset():
    dataset = forest.drivers.get_dataset("earth_networks")
    assert isinstance(dataset, forest.drivers.earth_networks.Dataset)


def get_navigator(settings):
    dataset = forest.drivers.get_dataset("earth_networks", settings)
    return dataset.navigator()


def test_dataset_navigator():
    navigator = get_navigator({"pattern": "*.txt"})
    assert isinstance(navigator, forest.drivers.earth_networks.Navigator)


def test_dataset_navigator_as_middleware():
    """Given set_valid_time should emit set_compressed_times"""
    navigator = get_navigator({})
    store = None
    time = dt.datetime(2020, 1, 1)
    action = forest.actions.set_valid_time(time)
    encoded = pd.DataFrame({
        "start": np.array([], dtype="datetime64[ns]"),
        "frequency": [],
        "length": []
    })
    expect = [
        action,
        forest.actions.set_encoded_times(encoded)
    ]
    actual = list(navigator(store, action))
    assert actual[0] == expect[0]
    assert actual[1]["kind"] == expect[1]["kind"]
    pdt.assert_frame_equal(actual[1]["payload"], expect[1]["payload"])


def test_loader():
    loader = earth_networks.Loader()
