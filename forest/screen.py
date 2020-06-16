"""
Split tapping or clicking places on the screen from triggering events.

First pass the bokeh tap event state into the the forest state using TapListener.

On any update of position, place a mark with MarkDraw.place_marker.

This split allows other parts of forest (such as the time series) to listen for
an update of the position of the marker and update themselves accordingly.

Reducer
~~~~~~~

A reducer is a pure function that combines a
state and an action to return a new state. Reducers
can be combined so that individual reducers are
responsible only for a limited set of actions

.. autofunction:: reducer

"""

import copy
import bokeh.events
import bokeh.models
from forest import rx
from forest.redux import Action
from forest.observe import Observable

SET_POSITION = "SET_POSITION"


def reducer(state, action):
    """Screen specific reducer

    Given :func:`screen.set_position` action adds "position" data
    to state

    :param state: data structure representing current state
    :type state: dict
    :param action: data structure representing action
    :type action: dict
    """
    state = copy.deepcopy(state)
    if action["kind"] == SET_POSITION:
        state["position"] = action["payload"]
    return state

def set_position(x, y) -> Action:
    """Action that stores a selected position

    .. code-block:: python

        {
            "kind": "SET_POSITION",
            "payload": {
                "x": x,
                "y": y
            }
        }

    :returns: data representing action
    :rtype: dict
    """
    return {"kind": SET_POSITION, "payload": {"x": x, "y": y}}


class TapListener(Observable):
    """ Listen for bokeh.events.Tap and update the store. Wired up in main.py"""

    def __init__(self):
        super().__init__()

    def connect(self, store):
        self.add_subscriber(store.dispatch)

    def update_xy(self, event):
        self.notify(set_position(event.x, event.y))


class MarkDraw:
    """
    Subscribe to forest state, update marker position when position state
    updates
    """

    def __init__(self, figure):
        self.figure = figure
        self.source = bokeh.models.ColumnDataSource({"x": [], "y": []})
        self.figure.circle(
          x="x",
          y="y",
          color="red",
          source=self.source)

    def connect(self, store):
        """
        Add function from this object as a subscriber of changes in the
        position state.
        """

        stream = (rx.Stream()
            .listen_to(store)
            .map(self.to_props)
            .distinct()
        )
        stream.map(lambda props: self.place_marker(*props))

    def to_props(self, state):
        return (state.get('position'),)

    def place_marker(self, pos):
        """ Update the marker position based on position state. """
        if pos is None:
            # Position not yet specified
            return
        self.source.data = {"x": [pos["x"]],
                            "y": [pos["y"]]}
