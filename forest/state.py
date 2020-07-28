"""
Application state
-----------------

Although the state in a redux store is defined by reducer functions,
engineers need documentation to extend and understand :class:`State`. Python
dataclasses are a natural fit to make state self-describing.

Expressing data structure as a nested hierarchy of types allows readers
of the code to understand how state is organised. It also allows for
type-checking to simplify functions that manipulate state.

State can be generated programmatically, converted to/from dict
to be compatible with reducers and to make it easier to serialize.

>>> state = forest.state.State()
>>> state.colorbar.name
'Viridis'

Converting to/from dict can be achieved
using :meth:`State.to_dict` and :meth:`State.from_dict`

>>> s1 = forest.state.State()
>>> d = s1.to_dict()
>>> type(d)
<class 'dict'>
>>> s2 = forest.state.State.from_dict(d)
>>> s1 == s2
True

The only caveat to be aware of while mapping to/from dict is that
:class:`State` implements default values for missing entries. A
default State is not equal to an empty dict.

>>> forest.state.State().to_dict() == {}
False

.. note:: State structure may change in future releases, backwards
          compatibility is not guaranteed

"""
import datetime as dt
import bokeh.palettes
from dataclasses import dataclass, field, asdict


@dataclass
class Bokeh:
    """Additional bokeh state

    Image streaming behaves inconsistently when data is streamed before
    the DOM is ready, ``image_shape[t] is undefined`` errors are triggered
    in the compiled JS

    .. note:: HTML loaded is merely convenience and may be unnecessary in
              future bokeh releases
    """
    html_loaded: bool = False


@dataclass
class Limits:
    """
    Color map extent, high and low represent upper and lower limits
    respectively

    :param low: lower limit
    :type low: float
    :param high: upper limit
    :type high: float
    """
    low: float = 0.
    high: float = 1.


@dataclass
class ColorbarLimits:
    """Define user and column data source limits

    :param origin: either 'user' or 'column_data_source'
    :type origin: str
    :param column_data_source: column_data_source limits
    :type column_data_source: Limits
    :param user: user limits
    :type user: Limits
    """
    origin: str = "column_data_source"
    column_data_source: Limits = field(default_factory=Limits)
    user: Limits = field(default_factory=Limits)

    def __post_init__(self):
        if isinstance(self.column_data_source, dict):
            self.column_data_source = Limits(**self.column_data_source)
        if isinstance(self.user, dict):
            self.user = Limits(**self.user)


def _names_factory():
    return list(sorted(bokeh.palettes.all_palettes.keys()))


def _numbers_factory():
    return list(sorted(bokeh.palettes.all_palettes["Viridis"].keys()))


@dataclass
class Colorbar:
    """
    Colorbar settings allow users to change palettes and limits
    based on data or user-specified limits

    :param name: bokeh palette name
    :param number: bokeh palette number
    :param limits: user and column_data_source limits
    :type limits: ColorbarLimits
    :param reverse: reverse color palette order
    :param invisible_min: hide/show values below minimum
    :param invisible_max: hide/show values above maximum
    """
    name: str = "Viridis"
    names: list = field(default_factory=_names_factory)
    number: int = 256
    numbers: list = field(default_factory=_numbers_factory)
    limits: ColorbarLimits = field(default_factory=ColorbarLimits)
    low: float = 0.
    high: float = 1.
    reverse: bool = False
    invisible_min: bool = False
    invisible_max: bool = False

    def __post_init__(self):
        if isinstance(self.limits, dict):
            self.limits = ColorbarLimits(**self.limits)

    def to_dict(self):
        return asdict(self)


@dataclass
class LayerMode:
    """Data to control UI presented to user

    Contains meta-data to indicate whether a layer is being edited or added. If
    the layer is being edited an index can be used to specify settings to
    overwrite.

    :param state: Edit mode, either 'edit' or 'add'
    :param index: Index of layer being edited
    """
    state: str = "add"
    index: int = 0


@dataclass
class Layers:
    """Layer settings

    :param figures: Number of figures to display
    :param index: Map layer index to settings
    :param active: List of active layers
    :param mode: Edit/new mode to define UI
    :type mode: LayerMode
    """
    figures: int = 1
    index: dict = field(default_factory=dict)
    active: list = field(default_factory=list)
    mode: LayerMode = field(default_factory=LayerMode)

    def __post_init__(self):
        if isinstance(self.mode, dict):
            self.mode = LayerMode(**self.mode)

    def to_dict(self):
        return asdict(self)


@dataclass
class Borders:
    """Cartopy border overlay settings

    :param line_color: Color of coastlines and country borders
    :type line_color: str
    :param visible: Turn all lines on/off
    :type visible: bool
    """
    line_color: str = "black"
    visible: bool = False


@dataclass
class Tile:
    """Web map tiling user-settings

    :param name: Keyword to specify WMTS source
    :type name: str
    :param labels: Turn overlay labels on/off
    :type labels: bool
    """
    name: str = "Open street map"
    labels: bool = False


@dataclass
class Position:
    """X/Y position in WebMercator coordinates related to user interaction

    :param x: coordinate of tap event
    :param y: coordinate of tap event
    """
    x: float = 0.
    y: float = -1e9  # South pole


@dataclass
class Tools:
    """Flags to specify active tools

    :param time_series: Turn time series widget on/off
    :type time_series: bool
    :param profile: Turn profile widget on/off
    :type time_series: bool
    """
    time_series: bool = False
    profile: bool = False


@dataclass
class Presets:
    """Re-usable layer settings

    Presets are cooked up once and re-used anywhere, they can also
    be tweaked on the fly and instantly made available to all layers
    using them. They can also be serialised to disk to store/re-load
    them as needed

    :param active: currently chosen preset
    :type active: int
    :param labels: map index to label
    :type active: dict
    :param meta: data used by user interface
    :type active: dict
    """
    active: int = 0
    labels: dict = field(default_factory=dict)
    meta: dict = field(default_factory=dict)


@dataclass
class State:
    """Application State container

    Nested data structure to define components, views
    and behaviour.

    :param pattern: User-selected value
    :param patterns: Dataset-specific values
    :param variable: User-selected value
    :param variables: Dataset-specific values
    :param initial_time: User-selected value
    :param initial_times: Dataset-specific values
    :param valid_time: User-selected value
    :param valid_times: Dataset-specific values
    :param pressure: User-selected value
    :param pressures: Dataset-specific values
    :param layers: Layer-specific settings
    :type layers: Layers
    :param colorbar: Color mapper controls
    :type colorbar: Colorbar
    :param tile: Web map tiling configuration
    :type tile: Tile
    :param tools: Turn profile/time_series on/off
    :type tools: Tools
    :param position: Used by tools to determine geographic position
    :type position: Position
    :param presets: Save colorbar settings for later re-use
    :type presets: Presets
    :param borders: Cartopy coastline, lakes and border settings
    :type borders: Borders
    :param bokeh: Additional bokeh state
    :type bokeh: Bokeh
    """

    pattern: str = None  # TODO: Support empty str as default
    patterns: list = field(default_factory=list)
    variable: str = None  # TODO: Support empty str as default
    variables: list = field(default_factory=list)
    initial_time: dt.datetime = dt.datetime(1970, 1, 1)
    initial_times: list = field(default_factory=list)
    valid_time: dt.datetime = dt.datetime(1970, 1, 1)
    valid_times: list = field(default_factory=list)
    pressure: float = 0.
    pressures: list = field(default_factory=list)
    colorbar: Colorbar = field(default_factory=Colorbar)
    layers: Layers = field(default_factory=Layers)
    dimension: dict = field(default_factory=dict)  # TODO: Find code using it
    tile: Tile = field(default_factory=Tile)
    tools: Tools = field(default_factory=Tools)
    position: Position = field(default_factory=Position)
    presets: Presets = field(default_factory=Presets)
    borders: Borders = field(default_factory=Borders)
    bokeh: Bokeh = field(default_factory=Bokeh)
    startup_complete: bool =  False

    def __post_init__(self):
        """Type-checking"""
        if isinstance(self.bokeh, dict):
            self.bokeh = Bokeh(**self.bokeh)
        if isinstance(self.borders, dict):
            self.borders = Borders(**self.borders)
        if isinstance(self.colorbar, dict):
            self.colorbar = Colorbar(**self.colorbar)
        if isinstance(self.tile, dict):
            self.tile = Tile(**self.tile)
        if isinstance(self.tools, dict):
            self.tools = Tools(**self.tools)
        if isinstance(self.position, dict):
            self.position = Position(**self.position)
        if isinstance(self.layers, dict):
            self.layers = Layers(**self.layers)
        if isinstance(self.presets, dict):
            self.presets = Presets(**self.presets)

    @classmethod
    def from_dict(cls, data: dict):
        """Factory method to convert from dict to State

        :returns: State instance
        :rtype: State
        """
        return cls(**data)

    def to_dict(self):
        """Map to dict representation of State

        :returns: dictionary containing nested state data
        :rtype: dict
        """
        return asdict(self)
