#!/usr/bin/python3
# -*- coding: utf-8 -*-

import numpy as np

class ZoomHandler:
    """
    Matplotlib callback to handle zoom events. This class has support for
    undo-like zoom-out operation, which is the default behavior.
    """

    def __init__(self, axes, scale_factor=2, rollback_undo=True):
        """
        ZoomHandler default constructor.

        Arguments
        ---------
        axes: matplotlib.Axes
            The axes object associated to this handler.
        scale_factor: number
            The scaling factor to apply when zooming-in.
            Default value is 2.
        rollback_undo: boolean
            Switch to dictate the behavior of the zoom-out operation. If set to
            True, then it will undo the last zoom-in operation. Else, it will
            apply an inverse scale over of the current zoom. Default value is
            True.
        """
        self._axes = axes
        self._scale_factor = scale_factor
        self._rollback_undo = rollback_undo
        self._xlim_stack = []
        self._ylim_stack = []        

    def __call__(self, event):
        """
        Method called by matplotlib to handle the zoom event.

        Arguments
        ---------
        event: matplotlib.Event
            Data about the event.
        """
        if event.inaxes:
            curr_xlim = self.axes.get_xlim()
            curr_ylim = self.axes.get_ylim()

            xdata = event.xdata
            ydata = event.ydata

            if event.button == 'up': # zoom-in
                self._xlim_stack.append(curr_xlim)
                self._ylim_stack.append(curr_ylim)

                xmin = xdata - curr_xlim[0]
                xmax = curr_xlim[1] - xdata
                ymin = ydata - curr_ylim[0]
                ymax = curr_ylim[1] - ydata

                self.axes.set_xlim([xdata - xmin / self.scale_factor,
                                    xdata + xmax / self.scale_factor])
                self.axes.set_ylim([ydata - ymin / self.scale_factor,
                                    ydata + ymax / self.scale_factor])

            elif event.button == 'down': # zoom-out
                # No more undos.
                if not self._xlim_stack:
                    print(self._xlim_stack, self._ylim_stack)
                    return
                xlim = self._xlim_stack.pop()
                ylim = self._ylim_stack.pop()

                self.axes.set_xlim(xlim)
                self.axes.set_ylim(ylim)

            self.axes.figure.canvas.draw()

    @property
    def axes(self):
        """
        Returns the axes associated to this object.

        Returns
        -------
        out: matplotlib.Axes
            The associated axes.
        """
        return self._axes

    @property
    def scale_factor(self):
        """
        Returns the scaling factor used for zooming.
        """
        return self._scale_factor

    @property
    def rollback_undo(self):
        """
        Returns wheter the zoom-out operation has an undo behavior (True) or a
        scaling behavior (False).
        """
        return self._rollback_undo

    def apply_zoom(self, new_lims=None):
        """
        """
        
        if not new_lims:
            

    def undo_rollback(self, undo):
        """
        Sets the behavior of the zoom-out operation. If set to True, then a
        zoom-out will undo the last zoom-in, else, it will rescale the axes
        limits.

        Arguments
        ---------
        undo: boolean
            The switch to set the zoom-out behavior.
        """
        self._rollback_undo = undo

def zoomhandler_main_test():
    import matplotlib.pyplot as plt

    fig = plt.figure()
    axes = fig.add_subplot(111)
    axes.scatter(x=np.arange(0, 10, 0.5), y=np.arange(0, 10, 0.5), color='g', marker='<')
    hand = ZoomHandler(axes)
    fig.canvas.mpl_connect('scroll_event', hand)
    plt.show()

if __name__ == '__main__':
    zoomhandler_main_test()
