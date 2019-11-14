import bokeh.plotting
import bokeh.models
import bokeh.events
import bokeh.colors
import numpy as np
import os
import glob
from forest import (
        satellite,
        data,
        load,
        view,
        images,
        earth_networks,
        rdt,
        geo,
        colors,
        db,
        keys,
        redux,
        unified_model,
        intake_loader,
        navigate,
        parse_args)
import forest.config as cfg
from forest.observe import Observable
from forest.db.util import autolabel
import datetime as dt


def main(argv=None):
    args = parse_args.parse_args(argv)
    if len(args.files) > 0:
        config = cfg.from_files(args.files, args.file_type)
    else:
        config = cfg.load_config(args.config_file)

    print(config.specs)

    database = None
    if args.database is not None:
        if args.database != ':memory:':
            assert os.path.exists(args.database), "{} must exist".format(args.database)
        database = db.Database.connect(args.database)

    # Full screen map
    lon_range = (90, 140)
    lat_range = (-23.5, 23.5)
    x_range, y_range = geo.web_mercator(
        lon_range,
        lat_range)
    figure = bokeh.plotting.figure(
        x_range=x_range,
        y_range=y_range,
        x_axis_type="mercator",
        y_axis_type="mercator",
        active_scroll="wheel_zoom")
    tile = bokeh.models.WMTSTileSource(
        url="https://maps.wikimedia.org/osm-intl/{Z}/{X}/{Y}.png",
        attribution=""
    )

    figures = [figure]
    for _ in range(2):
        f = bokeh.plotting.figure(
            x_range=figure.x_range,
            y_range=figure.y_range,
            x_axis_type="mercator",
            y_axis_type="mercator",
            active_scroll="wheel_zoom")
        figures.append(f)

    for f in figures:
        f.axis.visible = False
        f.toolbar.logo = None
        f.toolbar_location = None
        f.min_border = 0
        f.add_tile(tile)

    figure_row = bokeh.layouts.row(*figures,
            sizing_mode="stretch_both")
    figure_row.children = [figures[0]]  # Trick to keep correct sizing modes

    figure_drop = bokeh.models.Dropdown(
            label="Figure",
            menu=[(str(i), str(i)) for i in [1, 2, 3]])

    def on_change(attr, old, new):
        if int(new) == 1:
            figure_row.children = [
                    figures[0]]
        elif int(new) == 2:
            figure_row.children = [
                    figures[0],
                    figures[1]]
        elif int(new) == 3:
            figure_row.children = [
                    figures[0],
                    figures[1],
                    figures[2]]

    figure_drop.on_change("value", on_change)

    color_mapper = bokeh.models.LinearColorMapper(
            low=0,
            high=1,
            palette=bokeh.palettes.Plasma[256])
    for figure in figures:
        colorbar = bokeh.models.ColorBar(
            color_mapper=color_mapper,
            orientation="horizontal",
            background_fill_alpha=0.,
            location="bottom_center",
            major_tick_line_color="black",
            bar_line_color="black")
        figure.add_layout(colorbar, 'center')

    # Database/File system loader(s)
    for group in config.file_groups:
        if group.label not in data.LOADERS:
            if group.locator == "database":
                loader = load.Loader.group_args(
                        group, args, database=database)
            else:
                loader = load.Loader.group_args(
                        group, args)
            data.add_loader(group.label, loader)

    renderers = {}
    viewers = {}
    for name, loader in data.LOADERS.items():
        if isinstance(loader, rdt.Loader):
            viewer = rdt.View(loader)
        elif isinstance(loader, earth_networks.Loader):
            viewer = earth_networks.View(loader)
        elif isinstance(loader, data.GPM):
            viewer = view.GPMView(loader, color_mapper)
        elif isinstance(loader, satellite.EIDA50):
            viewer = view.EIDA50(loader, color_mapper)
        elif isinstance(loader, intake_loader.IntakeLoader):
            viewer = view.UMView(loader, color_mapper)
            viewer.set_hover_properties(intake_loader.INTAKE_TOOLTIPS,
                                        intake_loader.INTAKE_FORMATTERS)
        else:
            viewer = view.UMView(loader, color_mapper)
        viewers[name] = viewer
        renderers[name] = [
                viewer.add_figure(f)
                for f in figures]

    artist = Artist(viewers, renderers)
    renderers = []
    for _, r in artist.renderers.items():
        renderers += r

    image_sources = []
    for name, viewer in artist.viewers.items():
        if isinstance(viewer, (view.UMView, view.GPMView, view.EIDA50)):
            image_sources.append(viewer.source)

    # Lakes
    for figure in figures:
        add_feature(figure, data.LAKES, color="lightblue")

    features = []
    for figure in figures:
        features += [
            add_feature(figure, data.COASTLINES),
            add_feature(figure, data.BORDERS)]

    # Disputed borders
    for figure in figures:
        add_feature(figure, data.DISPUTED, color="red")

    toggle = bokeh.models.CheckboxButtonGroup(
            labels=["Coastlines"],
            active=[0],
            width=135)

    def on_change(attr, old, new):
        if len(new) == 1:
            for feature in features:
                feature.visible = True
        else:
            for feature in features:
                feature.visible = False

    toggle.on_change("active", on_change)

    dropdown = bokeh.models.Dropdown(
            label="Color",
            menu=[
                ("Black", "black"),
                ("White", "white")],
            width=50)
    autolabel(dropdown)

    def on_change(attr, old, new):
        for feature in features:
            feature.glyph.line_color = new

    dropdown.on_change("value", on_change)

    slider = bokeh.models.Slider(
        start=0,
        end=1,
        step=0.1,
        value=1.0,
        show_value=False)

    def is_image(renderer):
        return isinstance(getattr(renderer, 'glyph', None), bokeh.models.Image)

    image_renderers = [r for r in renderers if is_image(r)]
    custom_js = bokeh.models.CustomJS(
            args=dict(renderers=image_renderers),
            code="""
            renderers.forEach(function (r) {
                r.glyph.global_alpha = cb_obj.value
            })
            """)
    slider.js_on_change("value", custom_js)

    colors_controls = colors.Controls(
            color_mapper, "Plasma", 256)

    mapper_limits = MapperLimits(image_sources, color_mapper)

    menu = []
    for k, _ in config.patterns:
        menu.append((k, k))

    image_controls = images.Controls(menu)

    def on_change(attr, old, new):
        if int(new) == 1:
            image_controls.labels = ["Show"]
        elif int(new) == 2:
            image_controls.labels = ["L", "R"]
        elif int(new) == 3:
            image_controls.labels = ["L", "C", "R"]

    figure_drop.on_change("value", on_change)

    image_controls.subscribe(artist.on_visible)

    div = bokeh.models.Div(text="", width=10)
    border_row = bokeh.layouts.row(
        bokeh.layouts.column(toggle),
        bokeh.layouts.column(div),
        bokeh.layouts.column(dropdown))

    # Pre-select first layer
    for name, _ in config.patterns:
        image_controls.select(name)
        break

    navigator = navigate.Navigator(config, database)

    # Pre-select menu choices (if any)
    initial_state = {}
    for _, pattern in config.patterns:
        initial_state = db.initial_state(navigator, pattern=pattern)
        break
    middlewares = [
        db.Log(verbose=True),
        keys.navigate,
        db.InverseCoordinate("pressure"),
        db.next_previous,
        db.Controls(navigator),
        db.Converter({
            "valid_times": db.stamps,
            "inital_times": db.stamps
        })
    ]
    store = redux.Store(
        db.reducer,
        initial_state=initial_state,
        middlewares=middlewares)
    controls = db.ControlView()
    controls.subscribe(store.dispatch)
    store.subscribe(controls.render)
    old_states = (db.Stream()
                    .listen_to(store)
                    .map(lambda x: db.State(**x)))
    old_states.subscribe(artist.on_state)

    # Ensure all listeners are pointing to the current state
    store.notify(store.state)
    store.dispatch(db.set_value("patterns", config.patterns))

    tabs = bokeh.models.Tabs(tabs=[
        bokeh.models.Panel(
            child=bokeh.layouts.column(
                bokeh.models.Div(text="Navigate:"),
                controls.layout,
                bokeh.models.Div(text="Compare:"),
                bokeh.layouts.row(figure_drop),
                image_controls.column),
            title="Control"
        ),
        bokeh.models.Panel(
            child=bokeh.layouts.column(
                border_row,
                bokeh.layouts.row(slider),
                colors_controls.layout,
                bokeh.layouts.row(mapper_limits.low_input),
                bokeh.layouts.row(mapper_limits.high_input),
                bokeh.layouts.row(mapper_limits.checkbox),
                ),
            title="Settings")
        ])

    # Series sub-figure widget
    series_figure = bokeh.plotting.figure(
                plot_width=400,
                plot_height=200,
                x_axis_type="datetime",
                toolbar_location=None,
                border_fill_alpha=0)
    series_figure.toolbar.logo = None
    series_row = bokeh.layouts.row(
            series_figure,
            name="series")

    def place_marker(figure, source):
        figure.circle(
                x="x",
                y="y",
                color="red",
                source=source)
        def cb(event):
            source.data = {
                    "x": [event.x],
                    "y": [event.y]}
        return cb

    marker_source = bokeh.models.ColumnDataSource({
            "x": [],
            "y": []})
    series = Series.from_groups(
            series_figure,
            config.file_groups,
            directory=args.directory)
    old_states.subscribe(series.on_state)
    for f in figures:
        f.on_event(bokeh.events.Tap, series.on_tap)
        f.on_event(bokeh.events.Tap, place_marker(f, marker_source))


    # Minimise controls to ease navigation
    compact_button = bokeh.models.Button(
            label="Compact")
    compact_minus = bokeh.models.Button(label="-", width=50)
    compact_plus = bokeh.models.Button(label="+", width=50)
    compact_navigation = bokeh.layouts.column(
            compact_button,
            bokeh.layouts.row(
                compact_minus,
                compact_plus,
                width=100))
    control_root = bokeh.layouts.column(
            compact_button,
            tabs,
            name="controls")

    display = "large"
    def on_compact():
        nonlocal display
        if display == "large":
            control_root.height = 100
            control_root.width = 120
            compact_button.width = 100
            compact_button.label = "Expand"
            control_root.children = [
                    compact_navigation]
            display = "compact"
        else:
            control_root.height = 500
            control_root.width = 300
            compact_button.width = 300
            compact_button.label = "Compact"
            control_root.children = [compact_button, tabs]
            display = "large"

    compact_button.on_click(on_compact)

    # Add key press support
    key_press = keys.KeyPress()
    key_press.subscribe(store.dispatch)

    document = bokeh.plotting.curdoc()
    document.title = "FOREST"
    document.add_root(control_root)
    document.add_root(series_row)
    document.add_root(figure_row)
    document.add_root(key_press.hidden_button)


from itertools import cycle


class Series(object):
    def __init__(self, figure, loaders):
        self.figure = figure
        self.loaders = loaders
        self.sources = {}
        circles = []
        items = []
        colors = cycle(bokeh.palettes.Colorblind[6][::-1])
        for name in self.loaders.keys():
            source = bokeh.models.ColumnDataSource({
                "x": [],
                "y": [],
            })
            color = next(colors)
            r = self.figure.line(
                    x="x",
                    y="y",
                    color=color,
                    line_width=1.5,
                    source=source)
            r.nonselection_glyph = bokeh.models.Line(
                    line_width=1.5,
                    line_color=color)
            c = self.figure.circle(
                    x="x",
                    y="y",
                    color=color,
                    source=source)
            c.selection_glyph = bokeh.models.Circle(
                    fill_color="red")
            c.nonselection_glyph = bokeh.models.Circle(
                    fill_color=color,
                    fill_alpha=0.5,
                    line_alpha=0)
            circles.append(c)
            items.append((name, [r]))
            self.sources[name] = source

        legend = bokeh.models.Legend(items=items,
                orientation="horizontal",
                click_policy="hide")
        self.figure.add_layout(legend, "below")

        tool = bokeh.models.HoverTool(
                tooltips=[
                    ('Time', '@x{%F %H:%M}'),
                    ('Value', '@y')
                ],
                formatters={
                    'x': 'datetime'
                })
        self.figure.add_tools(tool)

        tool = bokeh.models.TapTool(
                renderers=circles)
        self.figure.add_tools(tool)

        # Underlying state
        self.state = {}

    @classmethod
    def from_groups(cls, figure, groups, directory=None):
        loaders = {}
        for group in groups:
            if group.file_type == "unified_model":
                if directory is None:
                    pattern = group.full_pattern
                else:
                    pattern = os.path.join(directory, group.full_pattern)
                loaders[group.label] = data.SeriesLoader.from_pattern(pattern)
        return cls(figure, loaders)

    def on_state(self, app_state):
        next_state = dict(self.state)
        attrs = [
                "initial_time",
                "variable",
                "pressure"]
        for attr in attrs:
            if getattr(app_state, attr) is not None:
                next_state[attr] = getattr(app_state, attr)
        state_change = any(
                next_state.get(k, None) != self.state.get(k, None)
                for k in attrs)
        if state_change:
            self.render()
        self.state = next_state

    def on_tap(self, event):
        self.state["x"] = event.x
        self.state["y"] = event.y
        self.render()

    def render(self):
        for attr in ["x", "y", "variable", "initial_time"]:
            if attr not in self.state:
                return
        x = self.state["x"]
        y = self.state["y"]
        variable = self.state["variable"]
        initial_time = dt.datetime.strptime(
                self.state["initial_time"],
                "%Y-%m-%d %H:%M:%S")
        pressure = self.state.get("pressure", None)
        self.figure.title.text = variable
        for name, source in self.sources.items():
            loader = self.loaders[name]
            lon, lat = geo.plate_carree(x, y)
            lon, lat = lon[0], lat[0]  # Map to scalar
            source.data = loader.series(
                    initial_time,
                    variable,
                    lon,
                    lat,
                    pressure)


def any_none(obj, attrs):
    return any([getattr(obj, x) is None for x in attrs])


class Artist(object):
    def __init__(self, viewers, renderers):
        self.viewers = viewers
        self.renderers = renderers
        self.visible_state = None
        self.state = None

    def on_visible(self, visible_state):
        if self.visible_state is not None:
            # Hide deselected states
            lost_items = (
                    set(self.flatten(self.visible_state)) -
                    set(self.flatten(visible_state)))
            for key, i, _ in lost_items:
                self.renderers[key][i].visible = False

        # Sync visible states with menu choices
        states = set(self.flatten(visible_state))
        hidden = [(i, j) for i, j, v in states if not v]
        visible = [(i, j) for i, j, v in states if v]
        for i, j in hidden:
            self.renderers[i][j].visible = False
        for i, j in visible:
            self.renderers[i][j].visible = True

        self.visible_state = dict(visible_state)
        self.render()

    @staticmethod
    def flatten(state):
        items = []
        for key, flags in state.items():
            items += [(key, i, f) for i, f in enumerate(flags)]
        return items

    def on_state(self, state):
        # print("Artist: {}".format(state))
        self.state = state
        self.render()

    def render(self):
        if self.visible_state is None:
            return
        if self.state is None:
            return
        for name in self.visible_state:
            viewer = self.viewers[name]
            viewer.render(self.state)


class TimeControls(Observable):
    def __init__(self, steps):
        self.steps = steps
        self.labels = ["T{:+}".format(int(s))
                for s in self.steps]
        self.plus = bokeh.models.Button(label="+", width=80)
        self.plus.on_click(self.on_plus)
        self.minus = bokeh.models.Button(label="-", width=80)
        self.minus.on_click(self.on_minus)
        self.dropdown = bokeh.models.Dropdown(
                label="Time step",
                menu=list(zip(self.labels, self.labels)),
                width=80)
        autolabel(self.dropdown)
        self.dropdown.on_click(self.on_dropdown)
        sizing_mode = "fixed"
        self.layout = bokeh.layouts.row(
                bokeh.layouts.column(self.minus, width=90,
                    sizing_mode=sizing_mode),
                bokeh.layouts.column(self.dropdown, width=100,
                    sizing_mode=sizing_mode),
                bokeh.layouts.column(self.plus, width=90,
                    sizing_mode=sizing_mode),
                width=300)
        super().__init__()

    def set_times(self, times):
        self.steps = self.as_steps(times)
        self.labels = ["T{:+}".format(int(s))
                for s in self.steps]
        self.dropdown.menu = list(zip(
            self.labels, self.labels))

    @staticmethod
    def as_steps(times):
        t0 = times[0]
        return [(t - t0).total_seconds() / (60 * 60)
                for t in times]

    def on_plus(self):
        if self.dropdown.value is None:
            self.dropdown.value = self.labels[0]
            return
        if self.index == (len(self.labels) - 1):
            return
        else:
            value = self.labels[self.index + 1]
            self.dropdown.value = value

    def on_minus(self):
        if self.dropdown.value is None:
            self.dropdown.value = self.labels[0]
            return
        if self.index == 0:
            return
        else:
            value = self.labels[self.index - 1]
            self.dropdown.value = value

    def on_dropdown(self, value):
        self.announce((self.index, self.step))

    @property
    def index(self):
        if self.dropdown.value is None:
            return
        return self.labels.index(self.dropdown.value)

    @property
    def step(self):
        if self.index is None:
            return
        return self.steps[self.index]


class MapperLimits(object):
    def __init__(self, sources, color_mapper, fixed=False):
        self.fixed = fixed
        self.sources = sources
        for source in self.sources:
            source.on_change("data", self.on_source_change)
        self.color_mapper = color_mapper
        self.low_input = bokeh.models.TextInput(title="Low:")
        self.low_input.on_change("value",
                self.change(color_mapper, "low", float))
        self.color_mapper.on_change("low",
                self.change(self.low_input, "value", str))
        self.high_input = bokeh.models.TextInput(title="High:")
        self.high_input.on_change("value",
                self.change(color_mapper, "high", float))
        self.color_mapper.on_change("high",
                self.change(self.high_input, "value", str))
        self.checkbox = bokeh.models.CheckboxGroup(
                labels=["Fixed"],
                active=[])
        self.checkbox.on_change("active", self.on_checkbox_change)

    def on_checkbox_change(self, attr, old, new):
        if len(new) == 1:
            self.fixed = True
        else:
            self.fixed = False

    def on_source_change(self, attr, old, new):
        if self.fixed:
            return
        images = []
        for source in self.sources:
            if len(source.data["image"]) == 0:
                continue
            images.append(source.data["image"][0])
        if len(images) > 0:
            low = np.min([np.min(x) for x in images])
            high = np.max([np.max(x) for x in images])
            self.color_mapper.low = low
            self.color_mapper.high = high
            self.color_mapper.low_color = bokeh.colors.RGB(0, 0, 0, a=0)
            self.color_mapper.high_color = bokeh.colors.RGB(0, 0, 0, a=0)

    @staticmethod
    def change(widget, prop, dtype):
        def wrapper(attr, old, new):
            if old == new:
                return
            if getattr(widget, prop) == dtype(new):
                return
            setattr(widget, prop, dtype(new))
        return wrapper


def change(widget, prop, dtype):
    def wrapper(attr, old, new):
        if old == new:
            return
        if getattr(widget, prop) == dtype(new):
            return
        setattr(widget, prop, dtype(new))
    return wrapper


def add_feature(figure, data, color="black"):
    source = bokeh.models.ColumnDataSource(data)
    return figure.multi_line(
        xs="xs",
        ys="ys",
        source=source,
        color=color)


if __name__.startswith("bk"):
    main()
