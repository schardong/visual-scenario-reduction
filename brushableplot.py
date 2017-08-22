#!/usr/bin/python3
# -*- coding: utf-8 -*-

'''
This module contains the base class for our plots that support the
brushing & linking technique.
'''


class BrushableCanvas:
    '''
    Class to define the basic interface of a drawable area that supports
    brushing & linking of its data instances.
    '''

    def __init__(self, canvas_name, parent=None):
        '''
        BrushableCanvas default constructor.

        Arguments
        ---------
        canvas_name: str
            The name of this object instance. This is passed as an argument to
            the parent widget when notifying it of changes in the selected
            data.
        parent: object
            The parent widget. Default is None. The parent widget must implement
            the 'set_brushed_data' method. This method receives this objects's
            canvas_name and a list containing the indices of all objects
            highlighted.
        '''
        self._name = canvas_name
        self._parent_canvas = parent
        self._highlighted_data = set()

    def __del__(self):
        del self._highlighted_data
        self._name = None
        self._parent_canvas = None

    @property
    def name(self):
        '''
        Returns the name given to this object.

        Returns
        -------
        out: str
            The name of this object.
        '''
        return self._name

    @property
    def highlighted_data(self):
        '''
        Returns the set of highlighted data indices.

        Returns
        -------
        out: set
            The set of indices of highlighted data.
        '''
        return self._highlighted_data

    @property
    def parent_canvas(self):
        '''
        Returns the parent widget of this object.

        Returns
        -------
        out: object
            The parent widget.
        '''
        return self._parent_canvas

    def notify_parent(self):
        '''
        Notifies the parent widget of changes in the selected data. If there is
        no parent widget, then no action is performed.
        '''
        if self.parent_canvas:
            self.parent_canvas.set_brushed_data(self.name,
                                                list(self.highlighted_data))

    def is_data_instance_highlighted(self, data_idx):
        '''
        Returns if the given data instance is highlighted.

        Returns
        -------
        out: boolean
            True if the instance is highlighted or False otherwise.
        '''
        return data_idx in self.highlighted_data

    def highlight_data(self, data_idx, erase, update_chart=True):
        '''
        Adds a data instance to the highlighted data set, or removes it from
        the set.

        Arguments
        ---------
        data_idx: int or iterable
            Index (or indices) of the data instance(s).
        erase: boolean
            Switch that indicates if the given data instances should be removed
            from the highlighted data set.
        update_chart: boolean
            Switch that indicates if the plot should be updated with the newly
            selected data instances.
        '''
        if isinstance(data_idx, int):
            if erase:
                self._highlighted_data.discard(data_idx)
            else:
                self._highlighted_data.add(data_idx)
        else:
            if isinstance(data_idx, list):
                data_idx = set(data_idx)
            if erase:
                self._highlighted_data = self._highlighted_data - data_idx
            else:
                self._highlighted_data.update(data_idx)
        if update_chart:
            self.update_chart(selected_data=True)

    def update_chart(self, **kwargs):
        '''
        Updates the plot.

        Arguments
        ---------
        kwargs: Keyword argumens
        Supported keyword arguments are:
        * selected_data - Indicates if there are changes in the selected data set.
        '''
        raise NotImplementedError('update_chart method must be overriden')
