import pytest
import cftime
import datetime as dt
import unittest

import iris
import numpy as np
import pandas as pd
import pandas.testing as pdt

from forest import util

@pytest.mark.parametrize("given,expect", [
    pytest.param('2019-10-10 01:02:34',
                 dt.datetime(2019, 10, 10, 1, 2, 34),
                 id="str with space"),
    pytest.param('2019-10-10T01:02:34',
                 dt.datetime(2019, 10, 10, 1, 2, 34),
                 id="iso8601"),
    pytest.param(np.datetime64('2019-10-10T11:22:33'),
                 dt.datetime(2019, 10, 10, 11, 22, 33),
                 id="datetime64"),
    pytest.param(cftime.DatetimeGregorian(2019, 10, 10, 11, 22, 33),
                 dt.datetime(2019, 10, 10, 11, 22, 33),
                 id="cftime.DatetimeGregorian"),
])
def test__to_datetime(given, expect):
    assert util.to_datetime(given) == expect


class Test_to_datetime(unittest.TestCase):
    def test_datetime(self):
        now = dt.datetime.now()
        result = util.to_datetime(now)
        self.assertEqual(result, now)

    def test_unsupported(self):
        with self.assertRaisesRegex(Exception, 'Unknown value'):
            util.to_datetime(12)


@pytest.mark.parametrize("regex,fmt,path,expect", [
    pytest.param(
        "[0-9]{8}", "%Y%m%d", "some_20200101.nc", dt.datetime(2020, 1, 1)
    ),
    pytest.param(
        "[0-9]{8}", "%Y%m%d", "file.nc", None,
        id="No match"
    ),
    pytest.param(
        "[0-9]{8}T[0-9]{6}Z", "%Y%m%dT%H%M%S%Z",
        "S_NWC_CTTH_MSG4_GuineaCoast-VISIR_20191021T134500Z.nc",
        dt.datetime(2019, 10, 21, 13, 45),
        id="SAF format"
    ),
])
def test_parse_date(regex, fmt, path, expect):
    assert util.parse_date(regex, fmt, path) == expect


@pytest.mark.parametrize("given,expect", [
    pytest.param(
        dt.datetime(2020, 1, 1),
        dt.datetime(2021, 1, 1),
        id="datetime.datetime"),
    pytest.param(
        np.datetime64("2020-01-01 00:00:00", "s"),
        np.datetime64("2021-01-01 00:00:00", "s"),
        id="datetime64[s]"),
    pytest.param(
        "2020-01-01 00:00:00",
        "2021-01-01 00:00:00",
        id="str"),
    pytest.param(
        cftime.DatetimeGregorian(2020, 1, 1),
        cftime.DatetimeGregorian(2021, 1, 1),
        id="cftime.DatetimeGregorian"),
])
def test_replace(given, expect):
    result = util.replace(given, year=2021)
    assert result == expect


@pytest.mark.parametrize("times, start, frequency, length", [
    pytest.param(
        [], [], [], [],
        id="empty"),
    pytest.param(
        ["2020-01-01"],
        ["2020-01-01"],
        [dt.timedelta(0)],
        [0],
        id="single value"),
    pytest.param(
        ["2020-01-01", "2020-01-01"],
        ["2020-01-01"],
        [dt.timedelta(0)],
        [1],
        id="same value twice"),
    pytest.param(
        ["2020-01-01", "2020-01-02"],
        ["2020-01-01"],
        [dt.timedelta(days=1)],
        [1],
        id="two different values"),
    pytest.param(
        ["2020-01-01", "2020-01-02", "2020-01-04"],
        ["2020-01-01", "2020-01-02"],
        [dt.timedelta(days=1), dt.timedelta(days=2)],
        [1, 1],
        id="two short periods"),
    pytest.param(
        ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"],
        ["2020-01-01"],
        [dt.timedelta(days=1)],
        [3],
        id="one long period"),
])
def test_run_length_encode(times, start, frequency, length):
    result = util.run_length_encode(times)
    expect = pd.DataFrame({
        "start": pd.to_datetime(start),
        "frequency": frequency,
        "length": length
    })
    pdt.assert_frame_equal(expect, result, check_dtype=False)


@pytest.mark.parametrize("x,index,value,length", [
    pytest.param([], [], [], []),
    pytest.param([1, 1, 1], [0], [1], [3]),
])
def test_find_runs(x, index, value, length):
    result = util.find_runs(x)
    expect = pd.DataFrame({
        "index": index,
        "value": value,
        "length": length
    })
    pdt.assert_frame_equal(expect, result, check_dtype=False)
