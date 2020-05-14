import datetime as dt
import bokeh.plotting
import numpy.testing as npt
import forest.components.time
from forest.components import time


def test_time_ui_render():
    time = dt.datetime(2020, 1, 1)
    ui = forest.components.time.TimeUI()
    ui.render(time, [time])


def test_raw_view():
    figure = bokeh.plotting.figure()
    source = bokeh.models.ColumnDataSource()
    times = ["2020-01-01T00:00:00Z", "2020-01-01T00:05:00Z"]
    view = time.RawView(figure, source)
    view.render(times)
    npt.assert_equal(source.data["global_index"], [0, 1])


def test_compressed_view():
    figure = bokeh.plotting.figure()
    source = bokeh.models.ColumnDataSource()
    times = ["2020-01-01T00:00:00Z", "2020-01-01T00:05:00Z"]
    view = time.CompressedView(figure, source)
    view.render(times)


def test_animation_ui():
    source = None
    time.AnimationUI(source)
