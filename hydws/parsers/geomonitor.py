import io
import re

import pandas as pd


def parse_geomonitor_to_dataframe(
        file: io.StringIO,
        samplerate: str = '60S',
        nrows: int = None) -> pd.DataFrame:
    """
    Parses the content of a geomonitor file to a dataframe with the respective
    column names and a datetime index.

    :param file: File buffer of the geomonitor *.dat file.
    :param lines: Number of lines starting from the end should be read.
    :param samplerate: At which rate the file should be sampled.

    :return:    A datetime indexed dataframe. Empty columns are skipped and NaN
                values set to 0.
    """
    data = pd.read_csv(
        file,
        encoding="ISO-8859-1",
        delim_whitespace=True,
        na_values=['-'],
        skiprows=[0, 2, 3, 4],
        nrows=nrows
    )

    # check and convert datetime to index
    data.dropna(subset=['dd/mm/yyyy', 'hh:mm:ss'], inplace=True)
    data['datetime'] = pd.to_datetime(
        data['dd/mm/yyyy'].str.cat(data['hh:mm:ss'], sep=' '),
        format='%d.%m.%Y %H:%M:%S')
    data.set_index(['datetime'], inplace=True)
    data.drop(['dd/mm/yyyy', 'hh:mm:ss'], axis=1, inplace=True)

    # drop rows and columns with only na values
    data.dropna(axis=1, how='all', inplace=True)
    data.dropna(axis=0, how='all', inplace=True)

    # all negative values means sensor not connected
    for col in data:
        # pad gaps in data
        data[col].interpolate(
            limit=86400,
            method='pad',
            inplace=True)
        # gaps which could not be padded are set to 0
        data[col].fillna(0, inplace=True)
        # if all data is negative or 0, drop column
        if data[col].apply(lambda x: x <= 0).all():
            data.drop(col, axis=1, inplace=True)
        # clip rest of data to 0
        else:
            data[col].clip(lower=0, inplace=True)

    # resample data for a given time step
    data = data.resample(
        samplerate,
        label='right',
        origin='end').mean()

    # check for duplicate columns (mangled)
    for col in data.columns:
        # If mangled column found, save/overwrite as unmangled.
        # After data cleaning usually only one version should still be around
        # otherwise the data will get overwritten with the last column of name
        if re.search('\\.\\d', col):
            data[col[:-2]] = data[col].copy()
            data = data.drop(columns=[col])

    return data
