#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np


class ZoomPanHandler:
    """
    Matplotlib callback class to handle pan and zoom events.
    """

    def __init__(self, axes, scale_factor=2, mouse_button=2):
        """
        Default constructor for the ZoomPanHandler class.

        Parameters
        axes: matplotlib.backend_bases.Axes
            The axes to attach this handler to.
        scale_factor: number
            The scale factor to apply when zooming.
        mouse_button: number or string
            The mouse button used to activate the pan action. Default value is
            2, meaning the middle mouse button.
        """
        self._axes = axes
        self._scale_factor = scale_factor
        self._mouse_button = mouse_button

        self._press_coords = None
        self._curr_xlim = self.axes.get_xlim()
        self._curr_ylim = self.axes.get_ylim()

        # Mouse action callback IDs
        self._cb_mouse_wheel_id = None
        self._cb_mouse_button_id = None
        self._cb_mouse_release_id = None
        self._cb_mouse_motion_id = None

        self._connect_cb()

    def __del__(self):
        self._disconnect_cb()
        self._axes = None

    @property
    def axes(self):
        return self._axes

    @property
    def scale_factor(self):
        return self._scale_factor

    @property
    def mouse_button(self):
        return self._mouse_button

    def apply_transforms(self):
        """
        Applies the zoom and pan transforms to the axes. Useful after reseting
        the plot.
        """
        self.axes.set_xlim(self._curr_xlim)
        self.axes.set_ylim(self._curr_ylim)

    def set_base_transforms(self):
        """
        Queries the current axis limits and stores them.
        """
        self._curr_xlim = self.axes.get_xlim()
        self._curr_ylim = self.axes.get_ylim()

    # Private methods
    def _cb_mouse_wheel(self, event):
        if event.inaxes:
            curr_xlim = self.axes.get_xlim()
            curr_ylim = self.axes.get_ylim()

            xdata = event.xdata
            ydata = event.ydata

            xmin = xdata - curr_xlim[0]
            ymin = ydata - curr_ylim[0]

            xmax = curr_xlim[1] - xdata
            ymax = curr_ylim[1] - ydata

            xlim = ylim = []

            if event.button == 'up':  # zoom-in
                xlim = [xdata - xmin / self.scale_factor,
                        xdata + xmax / self.scale_factor]
                ylim = [ydata - ymin / self.scale_factor,
                        ydata + ymax / self.scale_factor]
            elif event.button == 'down':  # zoom-out
                xlim = [xdata - xmin * self.scale_factor,
                        xdata + xmax * self.scale_factor]
                ylim = [ydata - ymin * self.scale_factor,
                        ydata + ymax * self.scale_factor]

            self._curr_xlim = xlim
            self._curr_ylim = ylim

            self.axes.set_xlim(xlim)
            self.axes.set_ylim(ylim)

            self.axes.figure.canvas.draw()

    def _cb_mouse_button(self, event):
        if not event.inaxes or event.button != self.mouse_button:
            return
        self._press_coords = (event.xdata, event.ydata)

    def _cb_mouse_release(self, event):
        self._press_coords = None
        self.axes.figure.canvas.draw()

    def _cb_mouse_motion(self, event):
        if not event.inaxes or not self._press_coords:
            return
        xlim = self.axes.get_xlim()
        ylim = self.axes.get_ylim()
        xlim -= (event.xdata - self._press_coords[0])
        ylim -= (event.ydata - self._press_coords[1])
        self._curr_xlim = xlim
        self._curr_ylim = ylim
        self.axes.set_xlim(xlim)
        self.axes.set_ylim(ylim)
        self.axes.figure.canvas.draw()

    def _connect_cb(self):
        fig = self.axes.figure
        self._cb_mouse_wheel_id = fig.canvas.mpl_connect(
            'scroll_event', self._cb_mouse_wheel)
        self._cb_mouse_button_id = fig.canvas.mpl_connect(
            'button_press_event', self._cb_mouse_button)
        self._cb_mouse_release_id = fig.canvas.mpl_connect(
            'button_release_event', self._cb_mouse_release)
        self._cb_mouse_motion_id = fig.canvas.mpl_connect(
            'motion_notify_event', self._cb_mouse_motion)

    def _disconnect_cb(self):
        fig = self.axes.figure
        if self._cb_mouse_wheel_id:
            fig.canvas.mpl_disconnect(self._cb_mouse_wheel_id)
            self._cb_mouse_wheel_id = None
        if self._cb_mouse_button_id:
            fig.canvas.mpl_disconnect(self._cb_mouse_button_id)
            self._cb_mouse_button_id = None
        if self._cb_mouse_release_id:
            fig.canvas.mpl_disconnect(self._cb_mouse_release_id)
            self._cb_mouse_release_id = None
        if self._cb_mouse_motion_id:
            fig.canvas.mpl_disconnect(self._cb_mouse_motion_id)
            self._cb_mouse_motion_id = None


def main():
    import matplotlib.pyplot as plt
    fig = plt.figure()
    axes = fig.add_subplot(111)
    axes.scatter(x=np.arange(0, 10, 0.5), y=np.arange(
        0, 20, 1), color='r', marker='o')
    hand = ZoomPanHandler(axes, scale_factor=1.5)
    plt.show()


if __name__ == '__main__':
    main()
