import forest.drivers
import bokeh.plotting


def test_argo_dataset():
    figure = bokeh.plotting.figure()
    dataset = forest.drivers.get_dataset("argo", {})
    dataset.profile_view(figure)
