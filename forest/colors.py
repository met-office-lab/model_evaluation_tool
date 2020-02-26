"""
Color palette
-------------

Helpers to choose color palette(s), limits etc.

UI components
~~~~~~~~~~~~~

The following components wire up the various bokeh
widgets and event handlers to actions and react to
changes in state. They are typically used in the
following manner.

>>> component = Component().connect(store)
>>> bokeh.layouts.column(component.layout)

.. autoclass:: ColorPalette
    :members:

.. autoclass:: UserLimits
    :members:

.. autoclass:: SourceLimits
    :members:

Most components are not interested in the full application
state. The :func:`connect` method and :func:`state_to_props`
are provided to only notify UI components when relevant state
updates.

.. autofunction:: connect

.. autofunction:: state_to_props


Reducer
~~~~~~~

A reducer combines the current state with an action
to produce a new state

.. autofunction:: reducer

Middleware
~~~~~~~~~~

Middleware pre-processes actions prior to the reducer

.. autofunction:: palettes

Helpers
~~~~~~~

Convenient functions to simplify color bar settings

.. autofunction:: defaults

.. autofunction:: palette_names

.. autofunction:: palette_numbers

Actions
~~~~~~~

Actions are small pieces of data used to communicate
with other parts of the system. Reducers and
middleware functions can interpret their contents
and either update state or generate new actions

.. autofunction:: set_colorbar

.. autofunction:: set_fixed

.. autofunction:: set_reverse

.. autofunction:: set_palette_name

.. autofunction:: set_palette_names

.. autofunction:: set_palette_number

.. autofunction:: set_palette_numbers

.. autofunction:: set_source_limits

.. autofunction:: set_user_high

.. autofunction:: set_user_low

.. autofunction:: set_invisible_min

.. autofunction:: set_invisible_max

"""
import copy
import bokeh.palettes
import bokeh.colors
import bokeh.layouts
import numpy as np
from forest.observe import Observable
from forest.rx import Stream
from forest.db.util import autolabel


SET_PALETTE = "SET_PALETTE"
SET_LIMITS = "SET_LIMITS"


def set_colorbar(options):
    """Action to set multiple settings at once"""
    return {"kind": SET_PALETTE, "payload": options}


def set_fixed(flag):
    """Action to set fix user-defined limits"""
    return {"kind": SET_PALETTE, "payload": {"fixed": flag}}


def set_reverse(flag):
    """Action to reverse color palette colors"""
    return {"kind": SET_PALETTE, "payload": {"reverse": flag}}


def set_palette_name(name):
    """Action to set color palette name"""
    return {"kind": SET_PALETTE, "payload": {"name": name}}


def set_palette_names(names):
    """Action to set all available palettes"""
    return {"kind": SET_PALETTE, "payload": {"names": names}}


def set_palette_number(number):
    """Action to set color palette size"""
    return {"kind": SET_PALETTE, "payload": {"number": number}}


def set_palette_numbers(numbers):
    """Action to set available levels for color palette"""
    return {"kind": SET_PALETTE, "payload": {"numbers": numbers}}


def set_source_limits(low, high):
    """Action to set colorbar limits from column data sources"""
    return {"kind": SET_LIMITS,
            "payload": {"low": low, "high": high},
            "meta": {"origin": "column_data_source"}}

def is_source_origin(action):
    """Detect origin of set_limits action"""
    origin = action.get("meta", {}).get("origin", "")
    return origin == "column_data_source"


def set_user_high(high):
    """Action to set user defined colorbar higher limit"""
    return {"kind": SET_LIMITS,
            "payload": {"high": high},
            "meta": {"origin": "user"}}


def set_user_low(low):
    """Action to set user defined colorbar lower limit"""
    return {"kind": SET_LIMITS,
            "payload": {"low": low},
            "meta": {"origin": "user"}}


def set_invisible_min(flag):
    """Action to mask out data below colour bar limits"""
    return {"kind": SET_LIMITS, "payload": {"invisible_min": flag}}

def set_invisible_max(flag):
    """Action to mask out data below colour bar limits"""
    return {"kind": SET_LIMITS, "payload": {"invisible_max": flag}}


def reducer(state, action):
    """Reducer for colorbar actions

    Combines current state with an action to
    produce the next state

    :returns: new state
    :rtype: dict
    """
    state = copy.deepcopy(state)
    kind = action["kind"]
    if kind in [SET_PALETTE, SET_LIMITS]:
        state["colorbar"] = state.get("colorbar", {})
        state["colorbar"].update(action["payload"])
    return state


def defaults():
    """Default color palette settings

    .. code-block:: python

        {
            "name": "Viridis",
            "names": palette_names(),
            "number": 256,
            "numbers": palette_numbers("Viridis"),
            "low": 0,
            "high": 1,
            "fixed": False,
            "reverse": False,
            "invisible_min": False,
            "invisible_max": False,
        }

    .. note:: incomplete settings create unintuitive behaviour when restoring
              from a previously saved palette

    :returns: dict representing default colorbar
    """
    return {
        "name": "Viridis",
        "names": palette_names(),
        "number": 256,
        "numbers": palette_numbers("Viridis"),
        "low": 0,
        "high": 1,
        "fixed": False,
        "reverse": False,
        "invisible_min": False,
        "invisible_max": False,
    }


def complete(settings):
    """Check current colorbar state is complete

    :returns: True if every colorbar setting is present
    """
    return all([key in settings for key in defaults().keys()])


def palette_names():
    """All palette names

    :returns: list of valid bokeh palette names
    """
    return list(sorted(bokeh.palettes.all_palettes.keys()))


def palettes(store, action):
    """Color palette middleware

    Encapsulates colorbar user interface logic. For example,
    if a user has chosen to fix their data limits, then
    set_limit actions generated by column data source changes
    are ignored

    .. note:: middleware is an action generator
    """
    kind = action["kind"]
    if (kind == SET_LIMITS) and is_fixed(store.state) and is_source_origin(action):
        # Filter SET_LIMIT actions from ColumnDataSource
        return
    if kind == SET_PALETTE:
        payload = action["payload"]
        if "name" in payload:
            name = payload["name"]
            numbers = palette_numbers(name)
            yield set_palette_numbers(numbers)
            if "colorbar" in store.state:
                if "number" in store.state["colorbar"]:
                    number = store.state["colorbar"]["number"]
                    if number not in numbers:
                        yield set_palette_number(max(numbers))
        yield action
    elif kind == SET_LIMITS:
        yield action
    else:
        # While handling generic action augment with defaults if not already set
        yield action
        settings = store.state.get("colorbar", {})
        if not complete(settings):
            yield set_colorbar({**defaults(), **settings})


def is_fixed(state):
    """Helper to discover if fixed limits have been selected"""
    return state.get("colorbar", {}).get("fixed", False)


def palette_numbers(name):
    """Helper to choose available color palette numbers

    :returns: list of valid bokeh palette numbers
    """
    return list(sorted(bokeh.palettes.all_palettes[name].keys()))


class SourceLimits(Observable):
    """Event stream listening to collection of ColumnDataSources

    Translates column data source on_change events into domain
    specific actions, e.g. :func:`set_source_limits`. Instead
    of connecting to a :class:`forest.redux.Store`, simply
    subscribe ``store.dispatch`` to action events.

    >>> source_limits = SourceLimits(sources)
    >>> source_limits.add_subscriber(store.dispatch)

    .. note:: Unlike a typical component there is no ``layout`` property
              to attach to a bokeh document
    """
    def __init__(self, sources):
        self.sources = sources
        for source in self.sources:
            source.on_change("data", self.on_change)
        super().__init__()

    def on_change(self, attr, old, new):
        images = []
        for source in self.sources:
            if len(source.data["image"]) == 0:
                continue
            images += source.data["image"]
        if len(images) > 0:
            low = np.min([np.min(x) for x in images])
            high = np.max([np.max(x) for x in images])
            self.notify(set_source_limits(low, high))
        else:
            self.notify(set_source_limits(0, 1))


class UserLimits(Observable):
    """User controlled color mapper limits"""
    def __init__(self):
        self.inputs = {
            "low": bokeh.models.TextInput(title="Min:"),
            "high": bokeh.models.TextInput(title="Max:")
        }
        self.inputs["low"].on_change("value", self.on_input_low)
        self.inputs["high"].on_change("value", self.on_input_high)

        self.checkboxes = {}

        # Checkbox fix data limits to user supplied limits
        self.checkboxes["fixed"] = bokeh.models.CheckboxGroup(
                labels=["Fix min/max settings for all frames"],
                active=[])
        self.checkboxes["fixed"].on_change("active", self.on_checkbox_change)

        # Checkbox transparency lower threshold
        self.checkboxes["invisible_min"] = bokeh.models.CheckboxGroup(
            labels=["Set data below Min to transparent"],
            active=[])
        self.checkboxes["invisible_min"].on_change("active", self.on_invisible_min)

        # Checkbox transparency upper threshold
        self.checkboxes["invisible_max"] = bokeh.models.CheckboxGroup(
            labels=["Set data above Max to transparent"],
            active=[])
        self.checkboxes["invisible_max"].on_change("active", self.on_invisible_max)

        self.layout = bokeh.layouts.column(
            self.inputs["low"],
            self.inputs["high"],
            self.checkboxes["fixed"],
            self.checkboxes["invisible_min"],
            self.checkboxes["invisible_max"],
        )
        super().__init__()

    def connect(self, store):
        """Connect component to Store

        Convert state stream to properties used
        by render method.

        :param store: instance to dispatch actions and listen to state changes
        :type store: :class:`forest.redux.Store`
        """
        connect(self, store)
        return self

    def on_checkbox_change(self, attr, old, new):
        self.notify(set_fixed(len(new) == 1))

    def on_input_low(self, attr, old, new):
        self.notify(set_user_low(float(new)))

    def on_input_high(self, attr, old, new):
        self.notify(set_user_high(float(new)))

    def on_invisible_min(self, attr, old, new):
        """Event-handler when invisible_min toggle is changed"""
        self.notify(set_invisible_min(len(new) == 1))

    def on_invisible_max(self, attr, old, new):
        """Event-handler when invisible_max toggle is changed"""
        self.notify(set_invisible_max(len(new) == 1))

    def render(self, props):
        """Update user-defined limits inputs"""
        for key in ["fixed", "invisible_min", "invisible_max"]:
            if props.get(key, False):
                self.checkboxes[key].active = [0]
            else:
                self.checkboxes[key].active = []

        if "high" in props:
            self.inputs["high"].value = str(props["high"])
        if "low" in props:
            self.inputs["low"].value = str(props["low"])


def state_to_props(state):
    """Map state to props relevant to component

    :param state: dict representing full application state
    :returns: ``state["colorbar"]`` or ``None``
    """
    return state.get("colorbar", None)


def connect(view, store):
    """Connect component to Store

    UI components connected to a Store
    only need to be notified when a change occurs that
    is relevant to them, all other state updates can be
    safely ignored.

    To implement component specific updates this helper method
    listens to store dispatch events, converts them
    to a stream of states, maps the states to
    props and filters out duplicates.
    """
    view.add_subscriber(store.dispatch)
    stream = (Stream()
                .listen_to(store)
                .map(state_to_props)
                .filter(lambda x: x is not None)
                .distinct())
    stream.map(lambda props: view.render(props))


class ColorPalette(Observable):
    """Color palette user interface"""
    def __init__(self, color_mapper):
        self.color_mapper = color_mapper
        self.dropdowns = {
            "names": bokeh.models.Dropdown(label="Palettes"),
            "numbers": bokeh.models.Dropdown(label="N")
        }
        self.dropdowns["names"].on_change("value", self.on_name)
        self.dropdowns["numbers"].on_change("value", self.on_number)

        self.checkbox = bokeh.models.CheckboxGroup(
            labels=["Reverse"],
            active=[])
        self.checkbox.on_change("active", self.on_reverse)

        self.layout = bokeh.layouts.column(
                bokeh.models.Div(text="Color palette:"),
                self.dropdowns["names"],
                self.dropdowns["numbers"],
                self.checkbox)
        super().__init__()

    def connect(self, store):
        """Connect component to Store"""
        connect(self, store)
        return self

    def on_name(self, attr, old, new):
        """Event-handler when a palette name is selected"""
        self.notify(set_palette_name(new))

    def on_number(self, attr, old, new):
        """Event-handler when a palette number is selected"""
        self.notify(set_palette_number(int(new)))

    def on_reverse(self, attr, old, new):
        """Event-handler when reverse toggle is changed"""
        self.notify(set_reverse(len(new) == 1))

    def render(self, props):
        """Render component from properties derived from state"""
        assert isinstance(props, dict), "only support dict"
        if "name" in props:
            self.dropdowns["names"].label = props["name"]
        if "number" in props:
            self.dropdowns["numbers"].label = str(props["number"])
        if ("name" in props) and ("number" in props):
            name = props["name"]
            number = props["number"]
            reverse = props.get("reverse", False)
            palette = self.palette(name, number)
            if reverse:
                palette = palette[::-1]
            self.color_mapper.palette = palette
        if "names" in props:
            values = props["names"]
            self.dropdowns["names"].menu = list(zip(values, values))
        if "numbers" in props:
            values = [str(n) for n in props["numbers"]]
            self.dropdowns["numbers"].menu = list(zip(values, values))
        if "low" in props:
            self.color_mapper.low = props["low"]
        if "high" in props:
            self.color_mapper.high = props["high"]
        invisible_min = props.get("invisible_min", False)
        if invisible_min:
            color = bokeh.colors.RGB(0, 0, 0, a=0)
            self.color_mapper.low_color = color
        else:
            self.color_mapper.low_color = None
        invisible_max = props.get("invisible_max", False)
        if invisible_max:
            color = bokeh.colors.RGB(0, 0, 0, a=0)
            self.color_mapper.high_color = color
        else:
            self.color_mapper.high_color = None

        # Render reverse checkbox state
        if props.get("reverse", False):
            self.checkbox.active = [0]
        else:
            self.checkbox.active = []

    @staticmethod
    def palette(name, number):
        return bokeh.palettes.all_palettes[name][number]
