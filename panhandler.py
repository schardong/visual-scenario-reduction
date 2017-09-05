#!/usr/bin/env python3
# coding: utf-8

import numpy as np

class PanHandler:
    """
    Class to handle matplotlib pan events.
    """

    def __init__(self, axes, mouse_button=1):
        """
        PanHandler default constructor.

        Parameters
        ----------
        axes: matplotlib.Axes
            The axes object associated to this handler.
        mouse_button: number
            The mouse button used to activate the pan action. Default value is ___, meaning the left mouse button.
        """
        self._axes = axes
        self._mouse_button = mouse_button
        self._curr_xlim = None
        self._curr_ylim = None
        self._press_coords = None

        # Mouse actions callback IDs
        self._cb_mouse_button_id = None
        self._cb_mouse_move_id = None
        self._cb_mouse_release_id = None

        self._connect_cb()

    def __del__(self):
        self._disconnect_cb()
        self._axes = None

    @property
    def axes(self):
        return self._axes

    @property
    def mouse_button(self):
        return self._mouse_button

    def mouse_click(self, event):
        if not event.inaxes:
            return
        if event.button != self._mouse_button:
            return
        self._curr_xlim = self.axes.get_xlim()
        self._curr_ylim = self.axes.get_ylim()
        self._press_coords = (event.xdata, event.ydata)

    def mouse_release(self, _):
        self._press_coords = None
        self.axes.figure.canvas.draw()

    def mouse_move(self, event):
        if not self._press_coords:
            return
        if not event.inaxes:
            return
        x0, y0 = self._press_coords
        dx, dy = event.xdata - x0, event.ydata - y0
        self._curr_xlim -= dx
        self._curr_ylim -= dy
        self.axes.set_xlim(self._curr_xlim)
        self.axes.set_ylim(self._curr_ylim)
        self.axes.figure.canvas.draw()

    def reset_pan(self):
        """
        Resets the pan transform to the original value.
        """
        self._curr_xlim = None
        self._curr_ylim = None

    def apply_pan(self):
        """
        Applies the axes pan. Useful after doing a redraw of the canvas.
        """
        if self._curr_xlim is not None:
            self.axes.set_xlim(self._curr_xlim)
            self.axes.set_ylim(self._curr_ylim)
            self.axes.figure.canvas.draw()

    # Private methods
    def _connect_cb(self):
        fig = self.axes.figure
        self._cb_mouse_button_id = fig.canvas.mpl_connect('button_press_event', self.mouse_click)
        self._cb_mouse_move_id = fig.canvas.mpl_connect('motion_notify_event', self.mouse_move)
        self._cb_mouse_release_id = fig.canvas.mpl_connect('button_release_event', self.mouse_release)

    def _disconnect_cb(self):
        fig = self.axes.figure
        if self._cb_mouse_button_id:
            fig.canvas.mpl_disconnect(self._cb_mouse_button_id)
            self._cb_mouse_button_id = None
        if self._cb_mouse_move_id:
            fig.canvas.mpl_disconnect(self._cb_mouse_move_id)
            self._cb_mouse_move_id = None
        if self._cb_mouse_release_id:
            fig.canvas.mpl_disconnect(self._cb_mouse_release_id)
            self._cb_mouse_release_id = None

def main():
    import matplotlib.pyplot as plt

    fig = plt.figure()
    axes = fig.add_subplot(111)
    axes.scatter(x=np.arange(0, 10, 0.5), y=np.arange(0, 10, 0.5), color='g', marker='<')
    hand = PanHandler(axes, 3)
    plt.show()

if __name__ == '__main__':
    main()
