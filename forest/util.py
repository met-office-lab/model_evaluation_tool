import glob
import os
import re
import datetime as dt
import cftime
from functools import partial
import scipy.ndimage
import numpy as np
import pandas as pd
try:
    import cf_units
except ImportError:
    # ReadTheDocs unable to pip install cf-units
    pass


def timeout_cache(interval):
    def decorator(f):
        cache = {}
        call_time = {}
        def wrapped(x):
            nonlocal cache
            nonlocal call_time
            now = dt.datetime.now()
            if x not in cache:
                cache[x] = f(x)
                call_time[x] = now
                return cache[x]
            else:
                if (now - call_time[x]) > interval:
                    cache[x] = f(x)
                    call_time[x] = now
                    return cache[x]
                else:
                    return cache[x]
        return wrapped
    return decorator


_timeout_globs = {}


def cached_glob(interval):
    """Glob file system at most once every interval"""
    global _timeout_globs
    if interval not in _timeout_globs:
        _timeout_globs[interval] = timeout_cache(interval)(_glob)
    return _timeout_globs[interval]


def _glob(pattern):
    return sorted(glob.glob(os.path.expanduser(pattern)))


def coarsify(lons, lats, values, fraction):
    values = scipy.ndimage.zoom(values, fraction)
    data = np.ma.masked_array(values, np.isnan(values))
    ny, nx = values.shape
    lons = np.linspace(lons.min(), lons.max(), nx)
    lats = np.linspace(lats.min(), lats.max(), ny)
    return lons, lats, data


# TODO: Delete this function in a future PR
def initial_time(path):
    name = os.path.basename(path)
    groups = re.search(r"[0-9]{8}T[0-9]{4}Z", path)
    if groups:
        return dt.datetime.strptime(groups[0], "%Y%m%dT%H%MZ")


def to_datetime(d):

    if isinstance(d, dt.datetime):
        return d
    if isinstance(d, cftime.DatetimeNoLeap):
        return dt.datetime(d.year, d.month, d.day, d.hour, d.minute, d.second)
    elif isinstance(d, cftime.DatetimeGregorian):
        return dt.datetime(d.year, d.month, d.day, d.hour, d.minute, d.second)
    elif isinstance(d, str):
        errors = []
        for fmt in (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return dt.datetime.strptime(d, fmt)
            except ValueError as e:
                errors.append(e)
                continue
        raise Exception(errors)
    elif isinstance(d, np.datetime64):
        return d.astype(dt.datetime)
    else:
        raise Exception("Unknown value: {} type: {}".format(d, type(d)))


def parse_date(regex, fmt, path):
    '''Parses a date from a pathname

    :param path: string representation of a path
    :returns: python Datetime object
    '''
    groups = re.search(regex, os.path.basename(path))
    if groups is not None:
        return dt.datetime.strptime(groups[0].replace('Z','UTC'),
                                    fmt) # always UTC


def convert_units(values, old_unit, new_unit):
    """Helper to convert units"""
    if isinstance(values, list):
        values = np.asarray(values)
    return cf_units.Unit(old_unit).convert(values, new_unit)


def replace(time, **kwargs):
    """Swap out year, month, day, hour, minute or second"""
    if isinstance(time, np.datetime64):
        return (pd.Timestamp(time).replace(**kwargs)
                                  .to_datetime64()
                                  .astype(time.dtype))
    elif isinstance(time, str):
        fmt = find_fmt(time)
        return (pd.Timestamp(time).replace(**kwargs)
                                  .strftime(fmt))
    return time.replace(**kwargs)


def find_fmt(text):
    """Determine datetime format from str"""
    fmts = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in fmts:
        try:
            dt.datetime.strptime(text, fmt)
            return fmt
        except ValueError:
            continue


def run_length_encode(times, sort=True):
    """Compression algorithm to reduce volume of datetimes"""
    if len(times) == 0:
        return pd.DataFrame({
            "start": np.array([], dtype='datetime64[ns]'),
            "frequency": [],
            "length": [],
        })
    elif len(times) == 1:
        return pd.DataFrame({
            "start": np.asarray(times, dtype='datetime64[ns]'),
            "frequency": np.array([0], dtype='timedelta64[ns]'),
            "length": [0]
        })
    else:
        if isinstance(times, list):
            times = pd.DatetimeIndex(times)

        if sort:
            times = times.sort_values()
        gaps = np.diff(times)
        runs = find_runs(gaps)

        start = times[runs['index']]
        frequency = runs['value']
        length = runs['length']
        return pd.DataFrame({
            "start": start,
            "frequency": frequency,
            "length": length
        })


def find_runs(array_1d):
    """Find repeated sequences of values"""
    if isinstance(array_1d, list):
        array_1d = np.asarray(array_1d)
    if len(array_1d) == 0:
        return pd.DataFrame({
            "index": np.array([], dtype=np.int),
            "value": np.array([], dtype=array_1d.dtype),
            "length": np.array([], dtype=np.int),
        })

    # Bit map of unequal values
    bitmap = np.zeros(len(array_1d), dtype=np.bool)
    bitmap[0] = True  # Boundary condition
    bitmap[1:] = array_1d[1:] != array_1d[:-1]

    # Convert boundaries of runs to array index
    index = np.flatnonzero(bitmap)

    # Return values, repeat length and index
    value = array_1d[bitmap]
    length = np.diff(np.append(index, len(array_1d)))
    return pd.DataFrame({
        "index": index,
        "value": value,
        "length": length,
    })
