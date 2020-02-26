import bokeh.plotting
import bokeh.models
import bokeh.events
import bokeh.colors
import numpy as np
import os
import glob
from forest import (
        satellite,
        screen,
        tools,
        profile,
        series,
        data,
        load,
        view,
        earth_networks,
        rdt,
        nearcast,
        geo,
        colors,
        layers,
        db,
        keys,
        presets,
        redux,
        rx,
        unified_model,
        intake_loader,
        navigate,
        parse_args)
import forest.components
from forest.components import tiles
import forest.config as cfg
import forest.middlewares as mws
from forest.observe import Observable
from forest.db.util import autolabel
import datetime as dt


def main(argv=None):
    args = parse_args.parse_args(argv)
    if len(args.files) > 0:
        if args.config_file is not None:
            raise Exception('--config-file and [FILE [FILE ...]] not compatible')
        config = cfg.from_files(args.files, args.file_type)
    else:
        config = cfg.Config.load(
                args.config_file,
                variables=cfg.combine_variables(
                    os.environ,
                    args.variables))

    # Full screen map
    viewport = config.default_viewport
    x_range, y_range = geo.web_mercator(
        viewport.lon_range,
        viewport.lat_range)
    figure = bokeh.plotting.figure(
        x_range=x_range,
        y_range=y_range,
        x_axis_type="mercator",
        y_axis_type="mercator",
        active_scroll="wheel_zoom")

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

    figure_row = layers.FigureRow(figures)

    # Connect axis change events
    source = bokeh.models.ColumnDataSource(dict(width=[]))
    custom_js = bokeh.models.CustomJS(args=dict(source=source, figure=figure), code="""
        let width = figure.x_range.end - figure.x_range.start;
        source.stream({width: [width]}, rollover=10)
        source.change.emit()
    """)
    figure.x_range.js_on_change("start", custom_js)
    def on_stream(attr, old, new):
        import cartopy
        from forest.components import tiled_image
        view_width = new["width"][-1]
        map_width = (
            max(cartopy.crs.Mercator.GOOGLE.x_limits) -
            min(cartopy.crs.Mercator.GOOGLE.x_limits))
        level = tiled_image.level(map_width, view_width)
        print(level)

    source.on_change("data", on_stream)

    color_mapper = bokeh.models.LinearColorMapper(
            low=0,
            high=1,
            palette=bokeh.palettes.Plasma[256])

    # Colorbar user interface
    colorbar_ui = forest.components.ColorbarUI(color_mapper)

    # Database/File system loader(s)
    for group in config.file_groups:
        if group.label not in data.LOADERS:
            database = None
            if group.locator == "database":
                database = db.get_database(group.database_path)
            loader = load.Loader.group_args(
                    group, args, database=database)
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
            # viewer = view.EIDA50(loader, color_mapper)
            viewer = forest.components.TiledImage(loader, color_mapper)
        elif isinstance(loader, nearcast.NearCast):
            viewer = view.NearCast(loader, color_mapper)
            viewer.set_hover_properties(nearcast.NEARCAST_TOOLTIPS)
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

    image_sources = []
    for name, viewer in viewers.items():
        if isinstance(viewer, (view.UMView, view.GPMView, view.EIDA50,
                               forest.components.TiledImage)):
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

    toggle = bokeh.models.CheckboxGroup(
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

    # Image opacity user interface (client-side)
    slider = bokeh.models.Slider(
        start=0,
        end=1,
        step=0.1,
        value=1.0,
        show_value=False)

    def is_image(renderer):
        return isinstance(getattr(renderer, 'glyph', None), bokeh.models.Image)

    renderers_list = []
    for _, r in renderers.items():
        renderers_list += r
    image_renderers = [r for r in renderers_list if is_image(r)]
    custom_js = bokeh.models.CustomJS(
            args=dict(renderers=image_renderers),
            code="""
            renderers.forEach(function (r) {
                r.glyph.global_alpha = cb_obj.value
            })
            """)
    slider.js_on_change("value", custom_js)

    menu = []
    for k, _ in config.patterns:
        menu.append((k, k))

    layers_ui = layers.LayersUI(menu)

    div = bokeh.models.Div(text="", width=10)
    border_row = bokeh.layouts.row(
        bokeh.layouts.column(toggle),
        bokeh.layouts.column(div),
        bokeh.layouts.column(dropdown))


    navigator = navigate.Navigator(config)

    # Pre-select menu choices (if any)
    initial_state = {}
    for _, pattern in config.patterns:
        initial_state = db.initial_state(navigator, pattern=pattern)
        break

    middlewares = [
        mws.echo,
        keys.navigate,
        db.InverseCoordinate("pressure"),
        db.next_previous,
        db.Controls(navigator),
        colors.palettes,
        presets.Middleware(presets.proxy_storage(config.presets_file)),
        presets.middleware,
        layers.middleware,
    ]
    store = redux.Store(
        redux.combine_reducers(
            db.reducer,
            layers.reducer,
            screen.reducer,
            tools.reducer,
            colors.reducer,
            presets.reducer,
            tiles.reducer),
        initial_state=initial_state,
        middlewares=middlewares)

    # Add time user interface
    time_ui = forest.components.TimeUI()
    time_ui.connect(store)

    # Connect renderer.visible states to store
    artist = layers.Artist(renderers)
    artist.connect(store)

    # Connect layers controls
    layers_ui.add_subscriber(store.dispatch)
    layers_ui.connect(store)

    # Connect tools controls

    display_names = {
            "time_series": "Display Time Series",
            "profile": "Display Profile"
        }
    available_features = {k: display_names[k]
                          for k in display_names.keys() if config.features[k]}

    tools_panel = tools.ToolsPanel(available_features)
    tools_panel.connect(store)

    # Navbar components
    navbar = Navbar(show_diagram_button=len(available_features) > 0)
    navbar.connect(store)

    # Connect tap listener
    tap_listener = screen.TapListener()
    tap_listener.connect(store)

    # Connect figure controls/views
    figure_ui = layers.FigureUI()
    figure_ui.add_subscriber(store.dispatch)
    figure_row.connect(store)

    # Tiling picker
    if config.use_web_map_tiles:
        tile_picker = forest.components.TilePicker()
        for figure in figures:
            tile_picker.add_figure(figure)
        tile_picker.connect(store)

    # Connect color palette controls
    color_palette = colors.ColorPalette(color_mapper).connect(store)

    # Connect limit controllers to store
    source_limits = colors.SourceLimits(image_sources)
    source_limits.add_subscriber(store.dispatch)

    user_limits = colors.UserLimits().connect(store)

    # Preset
    preset_ui = presets.PresetUI().connect(store)

    # Connect navigation controls
    controls = db.ControlView()
    controls.connect(store)

    # Connect views to state changes
    connector = layers.ViewerConnector().connect(store)
    for label, viewer in viewers.items():
        connector.add_label_subscriber(label, viewer.render)

    # Set default time series visibility
    store.dispatch(tools.on_toggle_tool("time_series", False))

    # Set default profile visibility
    store.dispatch(tools.on_toggle_tool("profile", False))

    # Set top-level navigation
    store.dispatch(db.set_value("patterns", config.patterns))

    # Pre-select first layer
    for name, _ in config.patterns:
        row_index = 0
        store.dispatch(layers.set_label(row_index, name))
        store.dispatch(layers.set_active(row_index, [0]))
        break

    # Select web map tiling
    if config.use_web_map_tiles:
        store.dispatch(tiles.set_tile(tiles.STAMEN_TERRAIN))
        store.dispatch(tiles.set_label_visible(True))

    # Organise controls/settings
    layouts = {}
    layouts["controls"] = [
        bokeh.models.Div(text="Layout:"),
        figure_ui.layout,
        bokeh.models.Div(text="Navigate:"),
        controls.layout,
        bokeh.models.Div(text="Compare:"),
        layers_ui.layout
    ]
    layouts["settings"] = [
        border_row,
        bokeh.layouts.row(slider),
        preset_ui.layout,
        color_palette.layout,
        user_limits.layout,
        bokeh.models.Div(text="Tiles:"),
    ]
    if config.use_web_map_tiles:
        layouts["settings"].append(tile_picker.layout)

    tabs = bokeh.models.Tabs(tabs=[
        bokeh.models.Panel(
            child=bokeh.layouts.column(*layouts["controls"]),
            title="Control"
        ),
        bokeh.models.Panel(
            child=bokeh.layouts.column(*layouts["settings"]),
            title="Settings")
        ])

    tool_figures = {}
    if config.features["time_series"]:
        # Series sub-figure widget
        series_figure = bokeh.plotting.figure(
                    plot_width=400,
                    plot_height=200,
                    x_axis_type="datetime",
                    toolbar_location=None,
                    border_fill_alpha=0)
        series_figure.toolbar.logo = None

        series_view = series.SeriesView.from_groups(
                series_figure,
                config.file_groups)
        series_view.add_subscriber(store.dispatch)
        series_args = (rx.Stream()
                    .listen_to(store)
                    .map(series.select_args)
                    .filter(lambda x: x is not None)
                    .distinct())
        series_args.map(lambda a: series_view.render(*a))
        series_args.map(print)  # Note: map(print) creates None stream

        tool_figures["series_figure"] = series_figure

    if config.features["profile"]:
        # Profile sub-figure widget
        profile_figure = bokeh.plotting.figure(
                    plot_width=300,
                    plot_height=450,
                    toolbar_location=None,
                    border_fill_alpha=0)
        profile_figure.toolbar.logo = None
        profile_figure.y_range.flipped = True

        profile_view = profile.ProfileView.from_groups(
                profile_figure,
                config.file_groups)
        profile_view.add_subscriber(store.dispatch)
        profile_args = (rx.Stream()
                    .listen_to(store)
                    .map(profile.select_args)
                    .filter(lambda x: x is not None)
                    .distinct())
        profile_args.map(lambda a: profile_view.render(*a))
        profile_args.map(print)  # Note: map(print) creates None stream

        tool_figures["profile_figure"] = profile_figure

    tool_layout = tools.ToolLayout(**tool_figures)
    tool_layout.connect(store)

    for f in figures:
        f.on_event(bokeh.events.Tap, tap_listener.update_xy)
        marker = screen.MarkDraw(f).connect(store)

    control_root = bokeh.layouts.column(
            tabs,
            name="controls")


    # Add key press support
    key_press = keys.KeyPress()
    key_press.add_subscriber(store.dispatch)

    document = bokeh.plotting.curdoc()
    document.title = "FOREST"
    document.add_root(control_root)
    document.add_root(
        bokeh.layouts.column(
            tools_panel.layout,
            tool_layout.layout,
            width=400,
            name="series"))
    document.add_root(
        bokeh.layouts.row(time_ui.layout, name="time"))
    for root in navbar.roots:
        document.add_root(root)
    document.add_root(
        bokeh.layouts.row(colorbar_ui.layout, name="colorbar"))
    document.add_root(figure_row.layout)
    document.add_root(key_press.hidden_button)


class Navbar:
    """Collection of navbar components"""
    def __init__(self, show_diagram_button=True):
        self.headline = forest.components.Headline()
        self.headline.layout.name = "headline"

        self.buttons = {}
        # Add button to control left drawer
        key = "sidenav_button"
        self.buttons[key] = bokeh.models.Button(
            label="Settings",
            name=key)
        custom_js = bokeh.models.CustomJS(code="""
            openId("sidenav");
        """)
        self.buttons[key].js_on_click(custom_js)

        # Add button to control right drawer
        key = "diagrams_button"
        self.buttons[key] = bokeh.models.Button(
            label="Diagrams",
            css_classes=["float-right"],
            name=key)
        custom_js = bokeh.models.CustomJS(code="""
            openId("diagrams");
        """)
        self.buttons[key].js_on_click(custom_js)

        roots = [
            self.buttons["sidenav_button"],
            self.headline.layout,
        ]
        if show_diagram_button:
            roots.append(self.buttons["diagrams_button"])
        self.roots = roots

    def connect(self, store):
        self.headline.connect(store)


def any_none(obj, attrs):
    return any([getattr(obj, x) is None for x in attrs])


def add_feature(figure, data, color="black"):
    source = bokeh.models.ColumnDataSource(data)
    return figure.multi_line(
        xs="xs",
        ys="ys",
        source=source,
        color=color)


if __name__.startswith("bk"):
    main()
