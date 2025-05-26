'''
aaa
'''

import os
import numpy as np


class TimeSeries(object):
    '''
    The TimeSeries class is responsible for storing a single time series, be it
    single or multivariate. Objects of this class also provide a simple
    mechanism for loading time series data from a comma-separated values (CSV)
    file.
    '''

    def __init__(self, filename=None):
        if filename and len(filename) != 0:
            self.load_series(filename=filename)
        else:
            self._data = np.ndarray(shape=(0, 0))
            self._names = {}

    def __len__(self):
        '''
        Returns the length of the time series. If no time series is loaded,
        then returns 0.
        '''
        return len(self._data)

    @property
    def names(self):
        '''
        Returns the names of the time series' components. If the series was
        not loaded yet, an empty list is returned.

        Returns:
        A list with the time series' component names. The list is not ordered
        in any way.
        '''
        return list(self._names.keys())

    def col(self, name):
        return self._names[name]

    def get_data(self, names=None):
        '''
        Returns the time series data stored in this object. Optionally, may
        return only some of the series' components.

        Arguments:
        names -- Optional argument indicating which individual components should
        be returned.

        Returns:
        A numpy.ndarray with the selected data
        '''
        if not names or len(names) == 0:
            return self._data
        else:
            idx = []
            for n in names:
                if n not in self.names:
                    print('WARNING: Name {} is invalid. Continuing.'.format(n))
                    continue

                idx.append(self.col(n))

            if len(idx) == 0:
                print('ERROR: No columns were found with the given name(s).')
                return None

            return self._data[:,idx]

    def load_series(self, filename):
        '''
        Loads the time series data from a CSV file. The CSV file must be
        delimited by commas, each component of the series is defined by a single
        column and the first line must contain the names of each component.
        This method raises ValueError exceptions if the filename is empty or the
        specified file does not exist.
        '''
        if len(filename) == 0:
            raise ValueError('Empty filename.')
        if not os.path.exists(filename):
            raise ValueError('Invalid file \"{}\".'.format(filename))
        with open(filename, 'r') as fin:
            well_names = fin.readline().strip().split(',')
            self._names = dict(zip(well_names, range(0, len(well_names))))

        self._data = np.genfromtxt(fname=filename, delimiter=',',
                                   skip_header=True, dtype=float)


def test_TimeSeries():
    BASE_DATA_PATH = '../data/'
    PROPERTY = 'NP'
    FILENAME = 'UNISIM-I-H_001.csv'
    FULL_DATA_PATH = os.path.join(BASE_DATA_PATH, 'ajustado', PROPERTY, FILENAME)

    ts = TimeSeries()
    if len(ts) != 0:
        print('Error: Empty timeseries has length > 0. Length = {}'.format(len(ts)))

    ts = TimeSeries(filename=FULL_DATA_PATH)
    print(ts.names)
    print(len(ts))

    data = ts.get_data()
    print(data.shape)
    print(data.ndim)

    names = ts.names[0:2]
    data = ts.get_data(names=names)
    print(data.shape)
    print(data.ndim)

if __name__ == '__main__':
    test_TimeSeries()
