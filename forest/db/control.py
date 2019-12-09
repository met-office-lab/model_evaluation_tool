"""Control navigation of FOREST data"""
import copy
import datetime as dt
import numpy as np
import bokeh.models
import bokeh.layouts
from . import util
from collections import namedtuple
from forest.redux import middleware
from forest.observe import Observable
from forest.gridded_forecast import _to_datetime
from forest.export import export


__all__ = [
    "State",
]


SET_VALUE = "SET_VALUE"
NEXT_VALUE = "NEXT_VALUE"
PREVIOUS_VALUE = "PREVIOUS_VALUE"

@export
def set_value(key, value):
    return dict(kind=SET_VALUE, payload=locals())

@export
def next_valid_time():
    return next_value("valid_time", "valid_times")


@export
def next_initial_time():
    return next_value("initial_time", "initial_times")


@export
def next_value(item_key, items_key):
    return dict(kind=NEXT_VALUE, payload=locals())


@export
def previous_valid_time():
    return previous_value("valid_time", "valid_times")


@export
def previous_initial_time():
    return previous_value("initial_time", "initial_times")


@export
def previous_value(item_key, items_key):
    return dict(kind=PREVIOUS_VALUE, payload=locals())


State = namedtuple("State", (
    "pattern",
    "patterns",
    "variable",
    "variables",
    "initial_time",
    "initial_times",
    "valid_time",
    "valid_times",
    "pressure",
    "pressures",
    "valid_format"))
State.__new__.__defaults__ = (None,) * len(State._fields)

def statehash(self):
    return hash((self.pattern, str(self.patterns), self.variable, self.initial_time, str(self.initial_times), self.valid_time, str(self.valid_times), self.pressure, str(self.pressures), self.valid_format))

def time_equal(a, b):
    if (a is None) and (b is None):
        return True
    elif (a is None) or (b is None):
        return False
    else:
        return _to_datetime(a) == _to_datetime(b)

_vto_datetime = np.vectorize(_to_datetime)

def time_array_equal(x, y):
    if (x is None) and (y is None):
        return True
    elif (x is None) or (y is None):
        return False
    elif (len(x) == 0) or (len(y) == 0):
        return x == y
    return np.all(_vto_datetime(x) == _vto_datetime(y))

def equal_value(a, b):
    if (a is None) and (b is None):
        return True
    elif (a is None) or (b is None):
        return False
    else:
        return np.allclose(a, b)

def state_ne(self, other):
    return not (self == other)

def state_eq(self, other):
    return (
            (self.pattern == other.pattern) and
            np.all(self.patterns == other.patterns) and
            (self.variable == other.variable) and
            np.all(self.variables == other.variables) and
            time_equal(self.initial_time, other.initial_time) and
            time_array_equal(self.initial_times, other.initial_times) and
            time_equal(self.valid_time, other.valid_time) and
            time_array_equal(self.valid_times, other.valid_times) and
            equal_value(self.pressure, other.pressure) and
            equal_value(self.pressures, other.pressures)
    )

State.__hash__ = statehash
State.__eq__ = state_eq
State.__ne__ = state_ne


@export
def initial_state(navigator, label):
    """Find initial state given navigator"""
    state = {}
    state["label"] = label
    variables = navigator.variables(label)
    state["variables"] = variables
    if len(variables) == 0:
        return state
    variable = variables[0]
    state["variable"] = variable
    # initial_times = navigator.initial_times(label, variable)
    initial_times = navigator.initial_times(label)
    state["initial_times"] = initial_times
    if len(initial_times) == 0:
        return state
    initial_time = max(initial_times)
    state["initial_time"] = initial_time
    valid_times = navigator.valid_times(
            label,
            variable,
            initial_time)
    state["valid_times"] = valid_times
    if len(valid_times) > 0:
        state["valid_time"] = min(valid_times)
    pressures = navigator.pressures(
            label,
            variable,
            initial_time)
    pressures = list(reversed(sorted(pressures)))
    state["pressures"] = pressures
    if len(pressures) > 0:
        state["pressure"] = pressures[0]
    return state


@export
def stamps(times):
    labels = []
    for t in times:
        if isinstance(t, np.datetime64):
            t = t.astype(dt.datetime)
        labels.append(str(t))
    return labels


@export
def reducer(state, action):
    state = copy.copy(state)
    kind = action["kind"]
    if kind == SET_VALUE:
        payload = action["payload"]
        key, value = payload["key"], payload["value"]
        state[key] = value
    return state


@export
class Log(object):
    """Logs actions"""
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.actions = []

    @middleware
    def __call__(self, store, next_dispatch, action):
        value = next_dispatch(action)
        if self.verbose:
            print(action)
        self.actions.append(action)
        return value


@export
class InverseCoordinate(object):
    """Translate actions on inverted coordinates"""
    def __init__(self, name):
        self.name = name

    @middleware
    def __call__(self, store, next_dispatch, action):
        kind = action["kind"]
        if kind in [NEXT_VALUE, PREVIOUS_VALUE]:
            if self.name == action["payload"]["item_key"]:
                return next_dispatch(self.invert(action))
        return next_dispatch(action)

    @staticmethod
    def invert(action):
        kind = action["kind"]
        payload = action["payload"]
        item_key = payload["item_key"]
        items_key = payload["items_key"]
        if kind == NEXT_VALUE:
            return previous_value(item_key, items_key)
        else:
            return next_value(item_key, items_key)


@export
@middleware
def next_previous(store, next_dispatch, action):
    """Translate NEXT/PREVIOUS action(s) into SET action"""
    kind = action["kind"]
    if kind in [NEXT_VALUE, PREVIOUS_VALUE]:
        payload = action["payload"]
        item_key = payload["item_key"]
        items_key = payload["items_key"]
        if items_key not in store.state:
            # No further action to be taken
            return
        items = store.state[items_key]
        if item_key in store.state:
            item = store.state[item_key]
            if kind == NEXT_VALUE:
                value = next_item(items, item)
            else:
                value = previous_item(items, item)
        else:
            if kind == NEXT_VALUE:
                value = max(items)
            else:
                value = min(items)
        return next_dispatch(set_value(item_key, value))
    return next_dispatch(action)


def next_item(items, item):
    items = list(sorted(items))
    i = items.index(item)
    return items[(i + 1) % len(items)]


def previous_item(items, item):
    items = list(sorted(items))
    i = items.index(item)
    return items[i - 1]


@export
class Navigator:
    """Database navigation protocol

    .. note:: :class:`forest.db.Database` does not support search by label

    :param database: instance of forest.db.Database
    :param glob_patterns: dict that maps label to SQL query pattern
    """
    # Note: Explicit keyword args passed to Database methods since
    #       they support arbitrary keyword combinations
    def __init__(self, database, glob_patterns):
        self.database = database
        self.glob_patterns = glob_patterns

    def variables(self, label):
        pattern = self.glob_patterns[label]
        return self.database.variables(pattern=pattern)

    def initial_times(self, label):
        pattern = self.glob_patterns[label]
        return self.database.initial_times(pattern=pattern)

    def valid_times(self, label, variable, initial_time):
        pattern = self.glob_patterns[label]
        return self.database.valid_times(
                pattern=pattern,
                variable=variable,
                initial_time=initial_time)

    def pressures(self, label, variable, initial_time):
        pattern = self.glob_patterns[label]
        return self.database.pressures(
                pattern=pattern,
                variable=variable,
                initial_time=initial_time)


@export
class Converter(object):
    def __init__(self, maps):
        self.maps = maps

    @middleware
    def __call__(self, store, next_dispatch, action):
        if action["kind"] == SET_VALUE:
            key = action["payload"]["key"]
            value = action["payload"]["value"]
            if key in self.maps:
                value = self.maps[key](value)
            return next_dispatch(set_value(key, value))
        return next_dispatch(action)


@export
class Middleware(object):
    """Navigation middleware"""
    def __init__(self, navigator):
        self.navigator = navigator

    @middleware
    def __call__(self, store, next_dispatch, action):
        if action["kind"] == SET_VALUE:
            key = action["payload"]["key"]
            value = action["payload"]["value"]
            if (key == "pressure"):
                try:
                    value = float(value)
                except ValueError:
                    print("{} is not a float".format(value))
                return next_dispatch(set_value(key, value))
            elif key == "label":
                # TODO: Use label only here
                label = action["payload"]["value"]
                variables = self.navigator.variables(label)
                initial_times = self.navigator.initial_times(label)
                initial_times = list(reversed(initial_times))
                next_dispatch(action)
                next_dispatch(set_value("variables", variables))
                next_dispatch(set_value("initial_times", initial_times))
                return
            elif key == "variable":
                for attr in ["label", "initial_time"]:
                    if attr not in store.state:
                        return next_dispatch(action)
                label = store.state["label"]
                variable = value
                initial_time = store.state["initial_time"]
                valid_times = self.navigator.valid_times(
                    label,
                    variable,
                    initial_time)
                valid_times = sorted(set(valid_times))
                pressures = self.navigator.pressures(
                    label,
                    variable,
                    initial_time)
                pressures = list(reversed(pressures))
                next_dispatch(action)
                next_dispatch(set_value("valid_times", valid_times))
                next_dispatch(set_value("pressures", pressures))
                return
            elif key == "initial_time":
                for attr in ["label", "variable"]:
                    if attr not in store.state:
                        return next_dispatch(action)
                label = store.state["label"]
                variable = store.state["variable"]
                initial_time = value
                valid_times = self.navigator.valid_times(
                    label,
                    variable,
                    initial_time)
                valid_times = sorted(set(valid_times))
                next_dispatch(action)
                next_dispatch(set_value("valid_times", valid_times))
                return
        return next_dispatch(action)


@export
class ControlView(Observable):
    def __init__(self):
        dropdown_width = 180
        button_width = 75
        self.dropdowns = {
            "variable": bokeh.models.Dropdown(
                label="Variable"),
            "initial_time": bokeh.models.Dropdown(
                label="Initial time",
                width=dropdown_width),
            "valid_time": bokeh.models.Dropdown(
                label="Valid time",
                width=dropdown_width),
            "pressure": bokeh.models.Dropdown(
                label="Pressure",
                width=dropdown_width)
        }
        for key, dropdown in self.dropdowns.items():
            util.autolabel(dropdown)
            util.autowarn(dropdown)
            dropdown.on_change("value", self.on_change(key))
        self.rows = {}
        self.buttons = {}
        for key, items_key in [
                ('pressure', 'pressures'),
                ('valid_time', 'valid_times'),
                ('initial_time', 'initial_times')]:
            self.buttons[key] = {
                'next': bokeh.models.Button(
                    label="Next",
                    width=button_width),
                'previous': bokeh.models.Button(
                    label="Previous",
                    width=button_width),
            }
            self.buttons[key]['next'].on_click(
                self.on_next(key, items_key))
            self.buttons[key]['previous'].on_click(
                self.on_previous(key, items_key))
            self.rows[key] = bokeh.layouts.row(
                self.buttons[key]["previous"],
                self.dropdowns[key],
                self.buttons[key]["next"])
        self.layout = bokeh.layouts.column(
            self.dropdowns["variable"],
            self.rows["initial_time"],
            self.rows["valid_time"],
            self.rows["pressure"])
        super().__init__()

    def on_change(self, key):
        def callback(attr, old, new):
            self.notify(set_value(key, new))
        return callback

    def on_next(self, item_key, items_key):
        def callback():
            self.notify(next_value(item_key, items_key))
        return callback

    def on_previous(self, item_key, items_key):
        def callback():
            self.notify(previous_value(item_key, items_key))
        return callback

    def render(self, state):
        """Configure dropdown menus"""
        assert isinstance(state, dict), "Only support dict"
        for key, items_key in [
                ("variable", "variables"),
                ("initial_time", "initial_times"),
                ("valid_time", "valid_times"),
                ("pressure", "pressures")]:
            if items_key not in state:
                disabled = True
            else:
                values = state[items_key]
                disabled = len(values) == 0
                if key == "pressure":
                    menu = [(self.hpa(p), str(p)) for p in values]
                else:
                    menu = self.menu(values)
                self.dropdowns[key].menu = menu
            self.dropdowns[key].disabled = disabled
            if key in self.buttons:
                self.buttons[key]["next"].disabled = disabled
                self.buttons[key]["previous"].disabled = disabled

        for key in [
                "variable",
                "initial_time",
                "pressure",
                "valid_time"]:
            if key in state:
                if state[key] is None:
                    continue
                self.dropdowns[key].value = str(state[key])

    @staticmethod
    def menu(values, formatter=str):
        return [(formatter(o), formatter(o)) for o in values]

    @staticmethod
    def hpa(p):
        if p < 1:
            return "{}hPa".format(str(p))
        return "{}hPa".format(int(p))
