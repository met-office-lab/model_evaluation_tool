import re
import os
import glob
import datetime as dt
import datashader
import pandas as pd
from functools import lru_cache
from forest import geo
from forest.util import to_datetime as _to_datetime
import forest.util
from forest.old_state import old_state, unique
from forest.db.control import is_set, set_valid_times
from forest.actions import set_encoded_times
import bokeh.models
import bokeh.palettes
import bokeh.colors
import numpy as np


class Dataset:
    """High-level class to relate navigators, loaders and views"""
    def __init__(self, pattern=None, **kwargs):
        self.pattern = pattern
        self.loader = Loader()
        self.locator = TimestampLocator(pattern)

    def navigator(self):
        """Construct navigator"""
        return Navigator(self.locator)

    def map_view(self):
        """Construct view"""
        return View(self.loader, self.locator)


class View:
    def __init__(self, loader, locator):
        self.loader = loader
        self.locator = locator
        palette = bokeh.palettes.all_palettes['Spectral'][11][::-1]
        self.color_mapper = bokeh.models.LinearColorMapper(low=-1000, high=0, palette=palette)
        self.empty_image = {
            "x": [],
            "y": [],
            "date": [],
            "longitude": [],
            "latitude": [],
            "flash_type": [],
            "time_since_flash": []
        }
        self.color_mappers = {}
        self.color_mappers["image"] = bokeh.models.LinearColorMapper(
            low=0,
            high=1,
            palette="Inferno256",
            nan_color=bokeh.colors.RGB(0, 0, 0, a=0)
        )
        self.sources = {}
        self.sources["scatter"] = bokeh.models.ColumnDataSource(self.empty_image)
        self.sources["image"] = bokeh.models.ColumnDataSource({
            "x": [],
            "y": [],
            "dw": [],
            "dh": [],
            "image": [],
        })
        self.variable_to_method = {
            "Lightning": self.scatter,
        }

    @old_state
    @unique
    def render(self, state):
        if state.valid_time is None:
            return
        if state.variable is None:
            return
        self.variable_to_method.get(state.variable, self.image)(state)

    def image(self, state):
        """Image colored by time since flash or flash density"""
        date =_to_datetime(state.valid_time)

        # 15 minute/1 hour slice of data?
        frame = self.get_frame(date)
        # frame = self.select_date(frame, date)

        # Filter intra-cloud/cloud-ground rows
        if "intra-cloud" in state.variable.lower():
            frame = frame[frame["flash_type"] == "IC"]
        elif "cloud-ground" in state.variable.lower():
            frame = frame[frame["flash_type"] == "CG"]

        # EarthNetworks validity box (not needed if tiling algorithm)
        longitude_range = (26, 40)
        latitude_range = (-12, 4)
        x_range, y_range = geo.web_mercator(longitude_range,
                                            latitude_range)

        x, y = geo.web_mercator(frame["longitude"], frame["latitude"])
        frame["x"] = x
        frame["y"] = y
        pixels = 256
        canvas = datashader.Canvas(
            plot_width=pixels,
            plot_height=pixels,
            x_range=x_range,
            y_range=y_range
        )

        if "density" in state.variable.lower():
            # N flashes per pixel
            agg = canvas.points(frame, "x", "y", datashader.count())
        else:
            # Min time since flash per pixel
            frame["since_flash"] = self.time_since(frame["date"], date)
            agg = canvas.points(frame, "x", "y", datashader.min("since_flash"))

        # Note: DataArray objects are not JSON serializable, .values is the
        #       same data cast as a numpy array
        x = agg.x.values.min()
        y = agg.y.values.min()
        dw = agg.x.values.max() - x
        dh = agg.y.values.max() - y
        image = np.ma.masked_array(agg.values.astype(np.float),
                                   mask=np.isnan(agg.values))
        if "density" in state.variable.lower():
            image[image == 0] = np.ma.masked # Remove pixels with no data

        # Update color_mapper
        if "density" in state.variable.lower():
            self.color_mappers["image"].low = 0
            self.color_mappers["image"].high = agg.values.max()
        else:
            self.color_mappers["image"].low = -1 * 60 * 60 # 1hr
            self.color_mappers["image"].high = 0

        if "density" in state.variable.lower():
            units = "events"
        else:
            units = "seconds"

        data = {
            "x": [x],
            "y": [y],
            "dw": [dw],
            "dh": [dh],
            "image": [image],
        }
        meta_data = {
            "variable": [state.variable],
            "date": [date],
            "units": [units]
        }
        data.update(meta_data)
        self.sources["image"].data = data

    def scatter(self, state):
        """Scatter plot of flash position colored by time since flash"""
        valid_time = _to_datetime(state.valid_time)
        paths = self.locator.find(valid_time)
        frame = self.loader.load(paths)
        frame = self.select_date(frame, valid_time)
        frame = frame[:400]  # Limit points
        frame['time_since_flash'] = self.time_since(frame['date'], valid_time)
        if len(frame) == 0:
            return self.empty_image
        x, y = geo.web_mercator(
                frame.longitude,
                frame.latitude)
        self.color_mapper.low = np.min(frame.time_since_flash)
        self.color_mapper.high = np.max(frame.time_since_flash)
        self.sources["scatter"].data = {
            "x": x,
            "y": y,
            "date": frame.date,
            "longitude": frame.longitude,
            "latitude": frame.latitude,
            "flash_type": frame.flash_type,
            "time_since_flash": frame.time_since_flash
        }

    def get_frame(self, valid_time):
        paths = self.locator.find(valid_time)
        return self.loader.load(paths)

    def select_date(self, frame, date):
        if len(frame) == 0:
            return frame
        frame = frame.set_index('date')
        start = date
        end = start + dt.timedelta(minutes=60)  # 1 hour window
        s = "{:%Y-%m-%dT%H:%M}".format(start)
        e = "{:%Y-%m-%dT%H:%M}".format(end)
        small_frame = frame[s:e].copy()
        return small_frame.reset_index()

    def time_since(self, date_column, date):
        """Pandas helper to calculate seconds since valid date"""
        return (date - date_column).dt.total_seconds()

    def add_figure(self, figure):
        renderer = figure.cross(
                x="x",
                y="y",
                size=10,
                fill_color={'field': 'time_since_flash', 'transform': self.color_mapper},
                line_color={'field': 'time_since_flash', 'transform': self.color_mapper},
                source=self.sources["scatter"])

        # Add image glyph_renderer
        renderer = figure.image(x="x", y="y", dw="dw", dh="dh", image="image",
                     source=self.sources["image"],
                     color_mapper=self.color_mappers["image"])
        custom_js = bokeh.models.CustomJS(
            args=dict(source=self.sources["image"]), code="""
            let idx = cb_data.index.image_indices[0]
            if (typeof idx !== 'undefined') {
                console.log(idx)
                let number = source.data['image'][0][idx.flat_index]
                if (typeof number === "undefined") {
                    number = source.data['image'][0][idx.dim1][idx.dim2]
                }
                if (isNaN(number)) {
                    cb_obj.tooltips = [
                        ['Variable', '@variable'],
                        ['Time', '@date{%H:%M:%S}']
                    ];
                } else {
                    cb_obj.tooltips = [
                        ['Variable', '@variable'],
                        ['Time', '@date{%H:%M:%S}'],
                        ['Value', '@image @units']
                    ];
                }
            }
        """)
        tool = bokeh.models.HoverTool(
                tooltips=[
                    ('Variable', '@variable'),
                    ('Time', '@date{%F}'),
                    ('Value', '@image @units')],
                formatters={
                    '@date': 'datetime'
                },
                renderers=[renderer],
                callback=custom_js
        )
        figure.add_tools(tool)
        return renderer


class TimestampLocator:
    """Find files by time stamp"""
    def __init__(self, pattern):
        if pattern is None:
            self.paths = []
        else:
            self.paths = glob.glob(pattern)

        self.table = {}
        for path in self.paths:
            self.table[self._parse_date(path)] = path

        times = [
            self._parse_date(path) for path in self.paths
        ]
        times = [t for t in times if t is not None]
        index = pd.DatetimeIndex(times)
        self._valid_times = index.sort_values()

    def find(self, date):
        if date in self.table:
            return [self.table[date]]
        else:
            return []

    @staticmethod
    def _parse_date(path):
        groups = re.search(r"[0-9]{8}T[0-9]{4}", os.path.basename(path))
        if groups is not None:
            return dt.datetime.strptime(groups[0], "%Y%m%dT%H%M")

    def valid_times(self):
        if len(self._valid_times) == 0:
            return []
        return self._valid_times

    def encoded_times(self):
        """Compressed representation of valid times"""
        return forest.util.run_length_encode(self.valid_times())


class Navigator:
    """Meta-data needed to navigate the dataset"""
    def __init__(self, locator):
        self.locator = locator

    def __call__(self, store, action):
        """Middleware"""
        yield action
        if is_set(action, "valid_time"):
            yield set_encoded_times(self.locator.encoded_times())

    def variables(self, pattern):
        return ["Cloud-ground strike density",
                "Intra-cloud strike density",
                "Time since recent flash"]

    def initial_times(self, pattern, variable):
        return [dt.datetime(1970, 1, 1)]

    def valid_times(self, pattern, variable, initial_time):
        # Populates initial_state and used by forest.db.control.Control
        times = self.locator.valid_times()
        spacing = int(np.floor(len(times) / 200))
        return times[::spacing]

    def pressures(self, pattern, variable, initial_time):
        return []


class Loader:
    """Methods to manipulate EarthNetworks data"""
    def load(self, csv_files):
        if isinstance(csv_files, str):
            csv_files = [csv_files]
        frames = []
        for csv_file in csv_files:
            frame = self.load_file(csv_file)
            frames.append(frame)
        if len(frames) == 0:
            return pd.DataFrame({
                "flash_type": [],
                "date": [],
                "latitude": [],
                "longitude": [],
            })
        else:
            return pd.concat(frames, ignore_index=True)

    @lru_cache(maxsize=32)
    def load_file(self, path):
        return pd.read_csv(
            path,
            parse_dates=[1],
            converters={0: self.flash_type},
            usecols=[0, 1, 2, 3],
            names=["flash_type", "date", "latitude", "longitude"],
            header=None)

    @staticmethod
    def flash_type(value):
        return {
            "0": "CG",
            "1": "IC",
            "9": "Keep alive"
        }.get(value, value)
