import re
import datetime as dt
import netCDF4
import numpy as np
import os
import glob
from functools import lru_cache
from forest import (
        geo,
        locate)
from forest.util import coarsify
from forest.exceptions import FileNotFound, IndexNotFound


MIN_DATETIME64 = np.datetime64('0001-01-01T00:00:00.000000')


def _natargmax(arr):
    """ Find the arg max when an array contains NaT's"""
    no_nats = np.where(np.isnat(arr), MIN_DATETIME64, arr)
    return np.argmax(no_nats)


class EIDA50(object):
    def __init__(self, pattern):
        self.locator = Locator(pattern)
        self.cache = {}
        paths = self.locator.paths()
        if len(paths) > 0:
            with netCDF4.Dataset(paths[-1]) as dataset:
                self.cache["longitude"] = dataset.variables["longitude"][:]
                self.cache["latitude"] = dataset.variables["latitude"][:]

    @property
    def longitudes(self):
        return self.cache["longitude"]

    @property
    def latitudes(self):
        return self.cache["latitude"]

    def values(self, path, itime):
        with netCDF4.Dataset(path) as dataset:
            values = dataset.variables["data"][itime]
        return values

    def image(self, valid_time):
        path, itime = self.locator.find(valid_time)
        values = self.values(path, itime)
        return self.load_image(values)

    def load_image(self, values):
        lons = self.longitudes
        lats = self.latitudes
        fraction = 0.25
        lons, lats, values = coarsify(
                lons, lats, values, fraction)
        return geo.stretch_image(
                lons, lats, values)


class Locator(object):
    """Locate EIDA50 satellite images"""
    def __init__(self, pattern):
        self.pattern = pattern

    def find(self, date):
        if isinstance(date, (dt.datetime, str)):
            date = np.datetime64(date, 's')
        paths = self.paths()
        ipath = self.find_file_index(paths, date)
        path = paths[ipath]
        time_axis = self.load_time_axis(path)
        index = self.find_index(
                time_axis,
                date,
                dt.timedelta(minutes=15))
        return path, index

    def paths(self):
        return sorted(glob.glob(os.path.expanduser(self.pattern)))

    @staticmethod
    @lru_cache()
    def load_time_axis(path):
        with netCDF4.Dataset(path) as dataset:
            var = dataset.variables["time"]
            values = netCDF4.num2date(
                    var[:], units=var.units)
        return np.array(values, dtype='datetime64[s]')

    def find_file_index(self, paths, user_date):
        dates = np.array([
            self.parse_date(path) for path in paths],
            dtype='datetime64[s]')
        mask = ~(dates <= user_date)
        if mask.all():
            msg = "No file for {}".format(user_date)
            raise FileNotFound(msg)
        before_dates = np.ma.array(
                dates, mask=mask, dtype='datetime64[s]')
        return _natargmax(before_dates.filled())

    @staticmethod
    def find_index(times, time, length):
        dtype = 'datetime64[s]'
        if isinstance(times, list):
            times = np.asarray(times, dtype=dtype)
        bounds = locate.bounds(times, length)
        inside = locate.in_bounds(bounds, time)
        valid_times = np.ma.array(times, mask=~inside)
        if valid_times.mask.all():
            msg = "{}: not found".format(time)
            raise IndexNotFound(msg)
        return _natargmax(valid_times.filled())

    @staticmethod
    def parse_date(path):
        # reg-ex to support file names like *20191211.nc
        groups = re.search(r"([0-9]{8})\.nc", path)
        if groups is None:
            # reg-ex to support file names like *20191211T0000Z.nc
            groups = re.search(r"([0-9]{8}T[0-9]{4}Z)\.nc", path)
            return dt.datetime.strptime(groups[1], "%Y%m%dT%H%MZ")
        else:
            return dt.datetime.strptime(groups[1], "%Y%m%d")
