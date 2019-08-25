import re
import datetime as dt
import netCDF4
import numpy as np
import os
import glob
import geo
import locate
from util import coarsify
from exceptions import FileNotFound, IndexNotFound


class EIDA50(object):
    total_seconds = np.vectorize(dt.timedelta.total_seconds)
    def __init__(self, pattern):
        self.locator = Locator(pattern)
        self.paths = sorted(glob.glob(os.path.expanduser(pattern)))
        self.dates = [
            self.parse_date(path) for path in self.paths]
        self.cache = {}
        with netCDF4.Dataset(self.paths[-1]) as dataset:
            self.cache["longitude"] = dataset.variables["longitude"][:]
            self.cache["latitude"] = dataset.variables["latitude"][:]
            var = dataset.variables["time"]
            times = netCDF4.num2date(var[:], units=var.units)
            self.cache[(self.paths[-1], "time")] = times

    @staticmethod
    def parse_date(path):
        groups = re.search(r"_([0-9]{8}).nc", path)
        return dt.datetime.strptime(groups[1], "%Y%m%d")

    @property
    def longitudes(self):
        return self.cache["longitude"]

    @property
    def latitudes(self):
        return self.cache["latitude"]

    def times(self, path):
        key = (path, "time")
        if key not in self.cache:
            with netCDF4.Dataset(path) as dataset:
                var = dataset.variables["time"]
                values = netCDF4.num2date(var[:], units=var.units)
            self.cache[key] = values
        return self.cache[key]

    def image(self, valid_time):
        path = self.find_path(valid_time)
        times = self.times(path)
        itime = self.nearest_index(times, valid_time)
        return self.load_image(path, itime)

    def load_image(self, path, itime):
        lons = self.longitudes
        lats = self.latitudes
        with netCDF4.Dataset(path) as dataset:
            values = dataset.variables["data"][itime]
        fraction = 0.25
        lons, lats, values = coarsify(
                lons, lats, values, fraction)
        return geo.stretch_image(
                lons, lats, values)

    def find_path(self, time):
        date = self.nearest_before(self.dates, time)
        i = self.nearest_index(self.dates, date)
        return self.paths[i]

    def nearest_before(self, times, time):
        if isinstance(times, list):
            times = np.asarray(times)
        diffs = self.total_seconds(times - time)
        pts = diffs <= 0
        before_times = times[pts]
        i = np.argmin(np.abs(diffs[pts]))
        return before_times[i]

    def nearest_index(self, times, time):
        if isinstance(times, list):
            times = np.asarray(times)
        seconds = self.total_seconds(times - time)
        return np.argmin(np.abs(seconds))


class Locator(object):
    """Locate EIDA50 satellite images"""
    def __init__(self, pattern):
        self.pattern = pattern
        self.cache = {}

    def find(self, date):
        if isinstance(date, (dt.datetime, str)):
            date = np.datetime64(date, 's')
        paths = sorted(glob.glob(os.path.expanduser(self.pattern)))
        ipath = self.find_file_index(paths, date)
        path = paths[ipath]
        time_axis = self.load_time_axis(path)
        index = self.find_index(
                time_axis,
                date,
                dt.timedelta(minutes=15))
        return path, index

    def load_time_axis(self, path):
        if path not in self.cache:
            with netCDF4.Dataset(path) as dataset:
                var = dataset.variables["time"]
                values = netCDF4.num2date(
                        var[:], units=var.units)
            self.cache[path] = np.array(
                    values, dtype='datetime64[s]')
        return self.cache[path]

    def find_file_index(self, paths, date):
        dates = np.array([
            self.parse_date(path) for path in paths],
            dtype='datetime64[s]')
        mask = ~(dates <= date)
        if mask.all():
            msg = "No file for {}".format(date)
            raise FileNotFound(msg)
        before_dates = np.ma.array(
                dates, mask=mask, dtype='datetime64[s]')
        return np.ma.argmax(before_dates)

    def find_index(self, times, time, length):
        dtype = 'datetime64[s]'
        if isinstance(times, list):
            times = np.asarray(times, dtype=dtype)
        bounds = locate.bounds(times, length)
        inside = locate.in_bounds(bounds, time)
        valid_times = np.ma.array(times, mask=~inside)
        if valid_times.mask.all():
            msg = "{}: not found".format(time)
            raise IndexNotFound(msg)
        return np.ma.argmax(valid_times)

    @staticmethod
    def parse_date(path):
        groups = re.search(r"([0-9]{8}).nc", path)
        return dt.datetime.strptime(groups[1], "%Y%m%d")
