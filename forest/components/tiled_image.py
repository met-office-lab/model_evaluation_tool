"""On the fly image tiling

Image processing libraries in Python are now highly optimised. They
can compute arbitrary images from impressively large arrays in less
than a second.
"""
from functools import partial
from typing import Callable, Iterable, List, Tuple, TypeVar
import bokeh.models
import cartopy
from tornado import gen
import xarray
import datashader
import numpy as np
from forest.old_state import unique
from forest.gridded_forecast import _to_datetime
from forest.geo import web_mercator


# Types
Number = TypeVar('Number', float, int)
Range = Tuple[Number, Number]
Tile = Tuple[Range, Range]
Extent = Tile
TileChecker = Callable[[Tile], bool]


# Constants
WEB_MERCATOR_EXTENT = (cartopy.crs.Mercator.GOOGLE.x_limits,
                       cartopy.crs.Mercator.GOOGLE.y_limits)


def level(projection_width, view_width):
    """Estimate zoom level from projection limits and view settings

    :param projection_width: measure of web mercator projection
    :param view_width: figure.x_range width
    """
    return np.ceil(np.log2(projection_width / view_width)) + 2


class TiledImage:
    """Image capable of supporting tiling
    """
    def __init__(self, loader, color_mapper):
        self._algorithm = Quadtree(WEB_MERCATOR_EXTENT)
        self.loader = loader
        self.color_mapper = color_mapper
        self.source = bokeh.models.ColumnDataSource({
            "x": [],
            "y": [],
            "dw": [],
            "dh": [],
            "image": []
        })

    def add_figure(self, figure):
        return figure.image(x="x",
                     y="y",
                     dw="dw",
                     dh="dh",
                     image="image",
                     source=self.source,
                     color_mapper=self.color_mapper)

    def render(self, state):
        if "valid_time" not in state:
            return
        self._render(state["valid_time"])

    @unique
    def _render(self, valid_time):
        document = bokeh.plotting.curdoc()
        if len(self.source.data["x"]) == 0:
            method = "stream"
        else:
            method = "patch"

        # EIDA50 specific I/O
        path, itime = self.loader.locator.find(_to_datetime(valid_time))
        z = self.loader.values(path, itime)

        # Map from Lon/Lat to WebMercator projection
        x, y = self._xy(self.loader.longitudes, self.loader.latitudes)

        # Tile domain
        for i, data in enumerate(self._images(x, y, z)):
            document.add_next_tick_callback(partial(self._callback, i, data,
                                                    method))

    def _xy(self, lons, lats):
        x, _ = web_mercator(
            lons,
            np.zeros(len(lons), dtype="d"))
        _, y = web_mercator(
            np.zeros(len(lats), dtype="d"),
            lats)
        return x, y

    def _images(self, x, y, data):
        level = 2 # TODO: derive from figure.x_range etc.
        model_domain = (
            (x.min(), x.max()),
            (y.min(), y.max())
        )
        viewport = model_domain # TODO: Use figure.x_range etc.
        xr = xarray.DataArray(data, coords=[("y", y), ("x", x)], name="Z")
        for x_range, y_range in self._algorithm.tiles(viewport,
                                                      model_domain,
                                                      level):
            yield self._shade(xr, x_range, y_range)

    @staticmethod
    def _shade(xr, x_range, y_range):
        """Create a tile"""
        canvas = datashader.Canvas(plot_width=256,
                                   plot_height=256,
                                   x_range=x_range,
                                   y_range=y_range)
        xri = canvas.quadmesh(xr)
        image = np.ma.masked_array(xri.values, np.isnan(xri.values))
        image = image.astype(np.float32)  # Reduce bandwith needed to send values
        return {
            "x": [x_range[0]],
            "y": [y_range[0]],
            "dw": [x_range[1] - x_range[0]],
            "dh": [y_range[1] - y_range[0]],
            "image": [image]
        }

    @gen.coroutine
    def _callback(self, i, data, method="stream"):
        if method == "stream":
            self.source.stream(data)
        else:
            patches = {
                "image": [(i, data["image"][0])]
            }
            self.source.patch(patches)


class Quadtree:
    """Quadtree tile algorithm"""
    def __init__(self, full_domain: Extent):
        self.full_domain = full_domain

    def tiles(self, viewport: Extent, model_domain: Extent, level: int):
        """Convenient method to find tiles given viewport and model domain"""
        checker = self.checker([viewport, model_domain])
        yield from self.search(checker, level)

    def search(self,
               checker: TileChecker,
               level: int) -> Iterable[Tile]:
        """Search algorithm to identify tiles

        :param checker: function to test quadtree branches
        :param level: recursive depth to search
        """
        yield from self._search_recursive(self.full_domain, checker, level, 0)

    def _search_recursive(self, parent, checker, final_level, current_level):
        if current_level == final_level:
            if checker(parent):
                yield parent
        else:
            for tile in self.split(parent):
                if checker(tile):
                    yield from self._search_recursive(tile,
                                                      checker,
                                                      final_level,
                                                      current_level + 1)

    @staticmethod
    def checker(extents: List[Extent]) -> TileChecker:
        """Make a tile checker to check multiple extents"""
        def wrapped(tile):
            if len(extents) == 0:
                return False
            return all(Quadtree.overlap(extent, tile) for extent in extents)
        return wrapped

    @staticmethod
    def overlap(tile_0: Tile, tile_1: Tile) -> bool:
        """Check rectangles overlap"""
        x_range_0, y_range_0 = tile_0
        x_range_1, y_range_1 = tile_1
        if max(x_range_0) <= min(x_range_1):
            return False
        elif min(x_range_0) >= max(x_range_1):
            return False
        elif max(y_range_0) <= min(y_range_1):
            return False
        elif min(y_range_0) >= max(y_range_1):
            return False
        return True

    @staticmethod
    def split(tile: Tile) -> List[Tile]:
        """Decompose a tile into four sub tiles"""
        (x0, x1), (y0, y1) = tile
        xm = int((x0 + x1) / 2)
        ym = int((y0 + y1) / 2)
        return [
            ((x0, xm), (y0, ym)),
            ((xm, x1), (y0, ym)),
            ((xm, x1), (ym, y1)),
            ((x0, xm), (ym, y1)),
        ]
