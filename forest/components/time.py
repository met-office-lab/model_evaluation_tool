"""Time navigation component"""
import datetime as dt
from forest import rx, util
from forest.observe import Observable
from forest.util import to_datetime as _to_datetime
import forest.db.control
import bokeh.plotting
import pandas as pd
import numpy as np


class _Axis:
    """Helper to find datetimes

    Maps all datetime variants using str(datetime.datetime) as a key
    """
    def __init__(self):
        self._mapping = {}
        self._values = []

    @property
    def datetimes(self):
        return [_to_datetime(t) for t in self.times]

    @property
    def times(self):
        return self._values

    @times.setter
    def times(self, values):
        """Intercept assignment to populate mapping"""
        self._mapping = {self._key(v): i for i, v in enumerate(values)}
        self._values = values

    def index(self, time):
        """Map random datetime object to index"""
        return self._mapping[self._key(time)]

    def value(self, i):
        """Recover original value at index"""
        return self._values[i]

    @staticmethod
    def _key(t):
        return str(_to_datetime(t))


class CompressedView:
    """Support compressed time data"""
    def __init__(self, figure, source=None):
        self.figure = figure
        self.sources = {}
        self.sources["encoded"] = bokeh.models.ColumnDataSource({
            "start": [],
            "frequency": [],
            "length": []
        })
        if source is None:
            source = bokeh.models.ColumnDataSource({
                "x": [],
                "global_index": [],
            })
        self.sources["decoded"] = source
        self.sources["valid"] = bokeh.models.ColumnDataSource({
            "x": [],
            "date": [],
            "global_index": [],
        })
        custom_js = bokeh.models.CustomJS(
                args=dict(
                    encoded=self.sources["encoded"],
                    decoded=self.sources["decoded"]), code="""
            let limits = {start: cb_obj.start, end: cb_obj.end}
            // Convert compressed server-data into client-visualisations
            decoded.data = forest.decodedData({
                encodedData: encoded.data,
                limits: limits,
                maxPoints: 200,
                algorithm: "exponential"
            })
            decoded.change.emit()
        """)
        self.figure.x_range.js_on_change("start", custom_js)

        # React to forest.js state changes
        custom_js = bokeh.models.CustomJS(
                args=dict(
                    source=self.sources["valid"]), code="""
            // Subscribe to forest.STORE state changes
            forest.add_subscriber("unique_key", () => {
                console.log("DEBUG")
                const state = forest.STORE.getState()
                source.data = Object.assign({}, source.data, {
                    global_index: [state.global_index]
                })
                source.change.emit()
            })
        """)
        self.figure.x_range.js_on_change("start", custom_js)

        # Visualise large dataset and selected point
        y = 0
        self.figure.circle(x="x",
                           y=y,
                           fill_alpha=0,
                           line_color="black",
                           line_width=2,
                           size=15,
                           source=self.sources["valid"])
        renderer = self.figure.circle(
                         x="x",
                         y=y,
                         fill_color="red",
                         line_color="red",
                         fill_alpha=0.3,
                         source=self.sources["decoded"])
        glyph = bokeh.models.Circle(
            fill_color="red",
            line_color="red",
            fill_alpha=0.3,
        )
        renderer.selection_glyph = glyph
        renderer.nonselection_glyph = glyph

        # Wire up JS selected to Python
        custom_js = bokeh.models.CustomJS(args=dict(
            source=self.sources["decoded"]), code="""
            let x = source.data['x'];
            let distance = x.map((t) => Math.abs(t - cb_obj.x));
            let minIndex = distance.reduce(function(bestIndex, value, index, values) {
                if (value < values[bestIndex]) {
                    return index;
                } else {
                    return bestIndex;
                }
            }, 0);
            source.selected.indices = [minIndex];
            source.change.emit();
        """)
        self.figure.js_on_event(bokeh.events.Tap, custom_js)

        # Send information to server
        custom_js = bokeh.models.CustomJS(
            args=dict(
                valid_source=self.sources["valid"],
                source=self.sources["decoded"]), code="""
            let i = cb_obj.indices[0]
            if (typeof i !== 'undefined') {
                let x = source.data["x"][i]
                let globalIndex = source.data["global_index"][i]
                valid_source.data = {
                    "x": [x],
                    "date": [new Date(x)],
                    "global_index": [globalIndex]
                }
                valid_source.change.emit()
            }
        """)
        self.sources["decoded"].selected.js_on_change('indices', custom_js)
        self.sources["valid"].on_change("data", self.on_change)

        # Redux.js
        custom_js = bokeh.models.CustomJS(code="""
            let index = cb_obj.data["global_index"][0]
            forest.STORE.dispatch({type: "SET_GLOBAL_INDEX", payload: index})
        """)
        self.sources["valid"].js_on_change("data", custom_js)

    def on_change(self, attr, old, new):
        """Notify store of set valid time action"""
        if len(new["x"]) > 0:
            print(new)

    def render(self, frame):
        """Update compressed source"""
        if not isinstance(frame, pd.DataFrame):
            frame = util.run_length_encode(frame)

        # Initial x-range
        if len(frame["start"]) > 0:
            if self.figure.x_range.start is None:
                self.figure.x_range.start = frame["start"].iloc[0]
            if self.figure.x_range.end is None:
                self.figure.x_range.end = frame["start"].iloc[-1]

        self.sources["encoded"].data = {
            "start": frame["start"],
            "length": frame["length"],
            "frequency": frame["frequency"],
        }


class TitleView:
    """Simple figure title"""
    def __init__(self, figure, source):
        self.figure = figure
        self.source = source
        self.source.on_change("data", self.on_change)
        self.figure.title.text = "Select time"
        self.figure.title.align = "center"

    def on_change(self, attr, old, new):
        if len(new) > 0:
            time = pd.Timestamp(new["date"][0])
            self.figure.title.text = f"{time:%A %d %B %Y %H:%M}"


class AnimationUI:
    """Collection of JS callbacks to trigger animation/navigation"""
    def __init__(self, source):
        self.source = source
        self.buttons = {
            "play": bokeh.models.Button(label="Play",
                                        css_classes=['play'],
                                        width=75),
            "pause": bokeh.models.Button(label="Pause",
                                         css_classes=['pause'],
                                         width=75),
            "next": bokeh.models.Button(label="Next",
                                        width=75),
            "previous": bokeh.models.Button(label="Previous",
                                            width=75)
        }

        # Play JS
        custom_js = bokeh.models.CustomJS(args=dict(source=self.source), code="""
            // Simple JS animation
            console.log('Play');
            window.playing = true;
            var interval = 500;
            let nextFrame = function() {
                if (window.playing) {
                    forest.STORE.dispatch({type: "NEXT"})
                    if (source.selected.indices.length > 0) {
                        let i = source.selected.indices[0];
                        let n = source.data['x'].length;
                        source.selected.indices = [(i + 1) % n];
                        source.change.emit();
                    }
                    setTimeout(nextFrame, interval);
                }
            };
            setTimeout(nextFrame, interval);
        """)
        self.buttons["play"].js_on_click(custom_js)

        # Pause behaviour
        custom_js = bokeh.models.CustomJS(args=dict(source=self.source), code="""
            console.log('Pause');
            window.playing = false;
        """)
        self.buttons["pause"].js_on_click(custom_js)

        # Previous behaviour
        custom_js = bokeh.models.CustomJS(args=dict(source=self.source), code="""
            // Simple JS animation
            // console.log('Previous');
            // if (source.selected.indices.length > 0) {
            //     let i = source.selected.indices[0];
            //     source.selected.indices = [i - 1];
            //     source.change.emit();
            // }

            forest.STORE.dispatch({type: "PREVIOUS"})
        """)
        self.buttons["previous"].js_on_click(custom_js)

        # Next behaviour
        custom_js = bokeh.models.CustomJS(args=dict(source=self.source), code="""
            // Simple JS animation
            // console.log('Next');
            // if (source.selected.indices.length > 0) {
            //     let i = source.selected.indices[0];
            //     let n = source.data['x'].length;
            //     source.selected.indices = [(i + 1) % n];
            //     source.change.emit();
            // }

            forest.STORE.dispatch({type: "NEXT"})
        """)
        self.buttons["next"].js_on_click(custom_js)
        self.layout = bokeh.layouts.row(
                self.buttons["previous"],
                self.buttons["play"],
                self.buttons["pause"],
                self.buttons["next"],
                sizing_mode="stretch_width")


class TimeUI(Observable):
    """Allow navigation through time"""
    def __init__(self):
        self._axis = _Axis()

        self.source = bokeh.models.ColumnDataSource({
            "x": [],
            "global_index": [],
        })

        self.figure = bokeh.plotting.figure(
            plot_height=80,
            plot_width=800,
            border_fill_alpha=0,
            tools='xpan',
            y_range=(-1, 1),
            x_axis_type='datetime')
        self.figure.toolbar.active_drag = 'auto'

        # Representations of time arrays
        self.views = {
            "compressed": CompressedView(self.figure, self.source),
            "raw": RawView(self.figure, self.source)
        }

        self.views["title"] = TitleView(self.figure,
                                        self.views["compressed"].sources["valid"])

        active_scroll = bokeh.models.WheelZoomTool(dimensions='width')
        self.figure.add_tools(active_scroll)
        self.figure.toolbar.active_scroll = active_scroll

        # X-axis formatter breakpoints
        formatter = self.figure.xaxis[0].formatter
        formatter.hourmin = ['%H:%M']
        formatter.hours = ['%H:%M']
        formatter.days = ["%d %B"]
        formatter.months = ["%b %Y"]

        # Customize figure to be a time slider widget
        self.figure.grid.grid_line_color = None
        self.figure.yaxis.visible = False
        self.figure.toolbar_location = None
        self.figure.xaxis.fixed_location = 0

        # Hover interaction
        hover_tool = bokeh.models.HoverTool(tooltips=None)
        self.figure.add_tools(hover_tool)

        selected_span = bokeh.models.Span(
            dimension="height",
            line_color="red",
            location=0)
        self.figure.add_layout(selected_span)
        custom_js = bokeh.models.CustomJS(args=dict(
            span=selected_span,
            source=self.source), code="""
            if (cb_obj.indices.length === 0) {
                return;
            }
            span.location = source.data['x'][cb_obj.indices[0]];
        """)
        self.source.selected.js_on_change('indices', custom_js)

        # Span that follows cursor
        if len(self.source.data["x"]) > 0:
            location = self.source.data["x"][0]
        else:
            location = 0
        span = bokeh.models.Span(
            dimension="height",
            line_color="grey",
            location=location)
        js = bokeh.models.CustomJS(args=dict(span=span), code="""
            span.location = cb_data.geometry.x;
        """)
        self.figure.add_layout(span)
        hover_tool.callback = js

        self.source.selected.on_change('indices', self.on_selected)

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
            fill_color='grey',
            fill_alpha=0.2,
            source=self.band_source
        )
        self.figure.add_layout(band)

        # Animation controls
        self.animation_ui = AnimationUI(self.source)

        self.layout = bokeh.layouts.column(
            bokeh.layouts.row(
                self.figure, sizing_mode="stretch_width"),
            self.animation_ui.layout,
            sizing_mode="stretch_width")

        super().__init__()

    def on_selected(self, attr, old, new):
        """Notify store of set valid time action"""
        if len(new) > 0:
            i = new[0]
            value = self._axis.value(i)
            self.notify(forest.db.control.set_value('valid_time', value))

    def connect(self, store):
        """Connect component to store

        Converts state into stream of unique property changes suitable
        for use with render method
        """
        self.add_subscriber(store.dispatch)
        stream = (rx.Stream()
                    .listen_to(store)
                    .map(self.to_props)
                    .filter(lambda x: x is not None)
                    .distinct())
        stream.map(lambda props: self.render(*props))

        # Represent run-length encoded times
        stream = (rx.Stream()
                    .listen_to(store)
                    .map(lambda state: state.get("encoded"))
                    .filter(lambda x: x is not None)
                    .distinct(pd.DataFrame.equals)
                  )
        stream.map(lambda frame: self.views["compressed"].render(frame))
        return self

    def to_props(self, state):
        """Convert state to properties needed by component"""
        if ('valid_time' not in state) or ('valid_times' not in state):
            return
        return state['valid_time'], sorted(state['valid_times'])

    def render(self, time, times):
        """React to state changes"""
        self._axis.times = times
        # self.views["raw"].render(times)

        try:
            index = self._axis.index(time)
        except KeyError:
            return
        self.source.selected.indices = [index]

        # Band
        if len(times) > 0:
            upper = [max(times), max(times)]
            lower = [min(times), min(times)]
        else:
            upper = [0, 0]
            lower = [0, 0]
        self.band_source.data = dict(
            base=[-1, 1],
            upper=upper,
            lower=lower
        )


class RawView:
    """Represent clickable times"""
    def __init__(self, figure, source):
        self.figure = figure
        self.source = source
        renderer = self.figure.square(x="x", y=0.5, source=self.source,
                      fill_color='black',
                      line_color='black')
        renderer.selection_glyph = bokeh.models.Square(
            fill_color="red",
            line_color="red")
        renderer.nonselection_glyph = bokeh.models.Square(
            fill_color="black",
            line_color="black",
            fill_alpha=0.2,
            line_alpha=0.2,
        )

        # Wire up Tap event
        tap_js = bokeh.models.CustomJS(args=dict(
            source=self.source), code="""
            let x = source.data['x'];
            let distance = x.map((t) => Math.abs(t - cb_obj.x));
            let minIndex = distance.reduce(function(bestIndex, value, index, values) {
                if (value < values[bestIndex]) {
                    return index;
                } else {
                    return bestIndex;
                }
            }, 0);
            source.selected.indices = [minIndex];
            source.change.emit();
        """)
        self.figure.js_on_event(bokeh.events.Tap, tap_js)

    def render(self, times):
        self.source.data = {
            "x": [_to_datetime(t) for t in times],
            "global_index": np.arange(len(times))
        }
