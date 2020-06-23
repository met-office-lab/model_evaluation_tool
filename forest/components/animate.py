"""
Animation controls
------------------

Additional user interface to make it easy to craft animations
"""
import datetime as dt
import pandas as pd
import bokeh.layouts
import forest.state
from forest.actions import Action
from forest.observe import Observable


SET_ANIMATE = "ANIMATE_SET_ANIMATE"
ON_PLAY = "ANIMATE_ON_PLAY"
ON_PAUSE = "ANIMATE_ON_PAUSE"


def set_animate(start, end, mode):
    """Action to set animate start, end and mode"""
    return Action(SET_ANIMATE, {"start": start, "end": end, "mode": mode})


def on_play():
    return Action(ON_PLAY)


def on_pause():
    return Action(ON_PAUSE)


def reducer(state, action):
    if isinstance(state, dict):
        state = forest.state.State.from_dict(state)
    if isinstance(action, dict):
        try:
            action = Action.from_dict(action)
        except TypeError as e:
            print(e)
            return state.to_dict()
    if action.kind == SET_ANIMATE:
        state.animate = forest.state.Animate(**action.payload)
    return state.to_dict()


class View:
    def __init__(self, figure, limits):
        self.figure = figure
        self.limits = limits
        self.spans = {
            "start": bokeh.models.Span(
                dimension="height",
                line_color="blue",
                location=0
            ),
            "end": bokeh.models.Span(
                dimension="height",
                line_color="blue",
                location=0
            ),
        }
        for span in self.spans.values():
            self.figure.add_layout(span)

        # Band to highlight valid times
        self.band_source = bokeh.models.ColumnDataSource(dict(
            base=[-1, 1],
            upper=[0, 0],
            lower=[0, 0]
        ))
        band = bokeh.models.Band(
            dimension='width',
            base='base',
            lower='lower',
            upper='upper',
            fill_color='lightskyblue',
            fill_alpha=0.1,
            source=self.band_source
        )
        self.figure.add_layout(band)

    def connect(self, store):
        store.add_subscriber(self.render)

    def render(self, state):
        state = forest.state.State.from_dict(state)
        print(state.animate)
        if state.animate.start:
            self.spans["start"].location = state.animate.start
        if state.animate.end:
            self.spans["end"].location = state.animate.end

        # Band
        if state.animate.start:
            lower = [state.animate.start,
                     state.animate.start]
        else:
            lower = [0, 0]

        if state.animate.end:
            upper = [state.animate.end,
                     state.animate.end]
        else:
            upper = [0, 0]
        self.band_source.data = dict(
            base=[-1, 1],
            upper=upper,
            lower=lower
        )

        # Limits
        self.limits.data = {
            "start": [state.animate.start],
            "end": [state.animate.end],
        }


class Controls(Observable):
    """Animation component"""
    def __init__(self, width=350):
        self.pickers = {
            "start": DateTimePicker(
                title="Start date",
                width=width),
            "end": DateTimePicker(
                title="End date",
                width=width),
        }
        self.date_pickers = {
            "start": self.pickers["start"].picker,
            "end": self.pickers["end"].picker,
        }
        self.buttons = Buttons(width=width)
        self.layout = bokeh.layouts.column(
            bokeh.models.Div(
                text="<h3>Playback settings</h3>",
                width=width - 10),
            self.pickers["start"].layout,
            self.pickers["end"].layout,
            self.buttons.layout,
            name="animate")
        super().__init__()

    def connect(self, store):
        store.add_subscriber(self.render)
        self.buttons.add_subscriber(self.on_play_pause)
        self.add_subscriber(store.dispatch)

    def on_play_pause(self, action):
        start = self.pickers["start"].date
        end = self.pickers["end"].date
        if action.kind == ON_PLAY:
            mode = "play"
        else:
            mode = "pause"
        self.notify(set_animate(start, end, mode).to_dict())

    def render(self, state):
        if isinstance(state, dict):
            state = forest.state.State.from_dict(state)
        self.pickers["start"].date = pd.to_datetime(state.animate.start)
        self.pickers["end"].date = pd.to_datetime(state.animate.end)


class DateTimePicker:
    def __init__(self, title="Date", width=None):
        self.widths = {
            "picker": None,
            "select": None,
        }
        if width is not None:
            self.widths["picker"] = (width // 2) - 10
            self.widths["select"] = (width // 4) - 10

        hours = [f"{i:02}" for i in range(24)]
        minutes = [f"{i:02}" for i in range(60)]
        self.picker =  bokeh.models.DatePicker(
            title=title,
            width=self.widths["picker"]
        )
        self.selects = {
            "hour": bokeh.models.Select(
                title="Hour",
                options=hours,
                width=self.widths["select"],
            ),
            "minute": bokeh.models.Select(
                title="Minute",
                options=minutes,
                width=self.widths["select"],
            ),
        }
        self.layout = bokeh.layouts.row(
            self.picker,
            self.selects["hour"],
            self.selects["minute"],
            width=width)

    @property
    def date(self):
        date = self.picker.value
        hour = self.selects["hour"].value
        minute = self.selects["minute"].value
        if date is not None:
            if hour != "":
                if minute != "":
                    year, month, day = date.split("-")
                    return dt.datetime(int(year),
                                       int(month),
                                       int(day),
                                       int(hour),
                                       int(minute))

    @date.setter
    def date(self, value):
        """Set UI to represent datetime"""
        if pd.isnull(value):
            return
        assert isinstance(value, dt.datetime)
        self.picker.value = dt.date(value.year,
                                    value.month,
                                    value.day)
        self.selects["hour"].value = f"{value:%H}"
        self.selects["minute"].value = f"{value:%M}"


class Buttons(Observable):
    def __init__(self, width=None):
        self.buttons = {
            "play": bokeh.models.Button(label="Apply settings",
                                        width=width - 10),
        }
        self.buttons["play"].on_click(self.on_play)
        self.layout = bokeh.layouts.row(
            self.buttons["play"],
            width=width)
        super().__init__()

    def on_play(self, event):
        self.notify(on_play())
