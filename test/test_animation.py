from unittest.mock import sentinel
import datetime as dt
import bokeh.layouts
import forest.state
from forest.components import animate


def test_animate_ui():
    ui = animate.Controls()
    ui.render({
        "animate": {
            "start": "2020-01-01T00:00Z",
            "end": "2020-01-02T00:00Z",
        }
    })
    assert ui.layout.name == "animate"
    assert ui.date_pickers["start"].value == "2020-01-01"
    assert ui.date_pickers["end"].value == "2020-01-02"


def test_animate_reducer():
    # NOTE: Python3.7+ sentinel.attr identity preserved on copy (3.6 failure)
    start, end, mode = "start", "end", "mode"
    action = animate.set_animate(start, end, mode)
    state = animate.reducer({}, action)
    state = forest.state.State.from_dict(state)
    assert state.animate.start == start
    assert state.animate.end == end
    assert state.animate.mode == mode


def test_animate_actions():
    action = animate.set_animate(sentinel.start, sentinel.end, sentinel.mode)
    assert action.payload == {
        "start": sentinel.start,
        "end": sentinel.end,
        "mode": sentinel.mode
    }
