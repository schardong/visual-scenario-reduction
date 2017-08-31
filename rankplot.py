#!/usr/bin/python3
# -*- coding: utf-8 -*-

"""
"""

import numpy as np
import scipy.spatial.distance
from matplotlib import cm
from matplotlib.backends.backend_qt5agg import \
    FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import QSizePolicy, QToolTip
from PyQt5.QtGui import QFont, QPalette, QColor

from brushableplot import BrushableCanvas
from zoomhandler import ZoomHandler
from panhandler import PanHandler


def rank_series(curves_data,
                baseline_idx,
                window_length=None,
                metric='euclidean'):
    """
    Builds a distance based ranking of the input data compared to the baseline
    data. The closer the a curve is to the baseline, the better (smaller) it's
    ranking.

    This function only supports distance metrics. Support for similatiry
    metrics will be added eventualy.

    Arguments
    ---------
    curves_data: numpy.array
        The input data arranged by row.
    baseline_idx: int
        The baseline curve index in the curves matrix.
    window_length: int
        The number of timesteps to consider when calculating the distance.
        Default value is None, all timesteps before the current one will be
        used.
    metric: str
        The distance metric to use when ranking. Accepted metrics are the same
        as the scipy.spatial.distance.pdist function.

    Returns
    -------
    out: numpy.array
    A matrix with the rankings of the time series at each timestep.
    """

    if baseline_idx >= curves_data.shape[0]:
        raise ValueError(
            'Invalid index for the baseline data {}/{}.'.format(
                baseline_idx. curve_data.shape[0]))
    if window_length and window_length > curves_data.shape[1]:
        raise ValueError('Window length is larger than series length.')

    x, y = curves_data.shape
    R = np.zeros(shape=(x, y))
    for ts in range(1, y + 1):
        sliced_data = curves_data[:, 0:ts]
        D = scipy.spatial.distance.pdist(sliced_data, metric=metric)
        D = scipy.spatial.distance.squareform(D)[baseline_idx, :]

        # Theoretically, only the reference curve is at 0 distance from the
        # reference. However, sometimes, another curve is also 0, especially
        # at the first timestep. The code bellow searches for a 0 distance
        # other than the reference and adds a little jitter to it.
        for idx, dist in enumerate(D):
            if dist == 0 and idx != baseline_idx:
                D[idx] += 1e-6

        R[np.argsort(D), ts - 1] = range(x)

    return R


class RankChart(FigureCanvas, BrushableCanvas):
    """
    This class builds a Rank plot of the input and reference data instances.

    Given a reference curve and a set of input curves, this class builds a
    distance based ranking of said curves compared to the reference. This
    process builds a new set of curves containing the ranks of each input curve
    at each X value. This new set of curves is plotted with the desired
    configurations.

    This class supports marking the desired curves using the brushing & linking
    technique.

    Note that each object of this class handles only one reference curve.
    For multiple references, multiple objects must be created.
    """

    def __init__(self, canvas_name, parent=None, width=5, height=5, dpi=100,
                 **kwargs):
        """
        Parameters
        ----------
        canvas_name: str
            The name of this object. To be used when notifying the parent widget
            of changes.
        parent: Qt5.QWidget
            The parent widget. Default is None. The parent widget must implement
            the 'brush_series' method. This method receives this objects's
            canvas_name and a list containing the indices of all objects
            highlighted.
        width: int
            The width of this plot canvas. Default value is 5.
        height: int
            The height of this plot canvas. Default value is 5.
        dpi: int
            This canvas's resolution. Default value is 100.
        kwargs:
            Other keyword arguments.
        """
        # Initial setup
        fig = Figure(figsize=(width, height), dpi=dpi)
        self._axes = fig.add_subplot(1, 1, 1)
        FigureCanvas.__init__(self, fig)
        FigureCanvas.setSizePolicy(self,
                                   QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
        self.setParent(parent)
        BrushableCanvas.__init__(self, canvas_name, parent)

        self._zoomhandler = ZoomHandler(self.axes)
        self._panhandler = PanHandler(self.axes, 3)

        # Data setup
        self._curves = None
        self._reference_idx = set()
        self._baseline_idx = None
        self._rank_series = None
        self._curvenames = None
        self._plotted_series = None

        # Plot style setup
        self._plot_title = self.base_plot_name()
        self._reference_parameters = {}
        self._cmap_name = 'rainbow'
        self._curves_colors = {}
        self._hthresh_line = None
        self._group_selection = False
        self._tooltip = None
        self._plot_params = kwargs
        if 'picker' not in self._plot_params:
            self._plot_params['picker'] = 2
        if 'linewidth' not in self._plot_params:
            self._plot_params['linewidth'] = 1.5

        # Callback IDs
        self._cb_mouse_move_id = None
        self._cb_mouse_button_id = None
        self._cb_scrollwheel_id = None
        self._cb_axes_leave_id = None
        self._cb_fig_leave_id = None

        # Callbacks
        self._cb_notify_tooltip = None

        self._connect_cb()

    def __del__(self):
        self._disconnect_cb()
        self._axes = None
        self._rank_series = None
        self._curves = None
        self._curves_colors.clear()
        self._reference_idx.clear()
        self._reference_parameters.clear()
        self._baseline_idx = None
        self._cb_notify_tooltip = None
        BrushableCanvas.__del__(self)

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
    def curves(self):
        """
        Returns the data curves used to build this chart.
        Returns
        -------
        out: numpy.array
            A matrix with the curves. The matrix is arranged by row.
        """
        return self._curves

    @property
    def plot_title(self):
        """
        Returns the current plot title.
        """
        return self._plot_title

    @classmethod
    def base_plot_name(self):
        """
        Static method that returns the base name of this plot.
        """
        return 'Bump Chart'

    @property
    def colormap_name(self):
        """
        Returns the name of the colormap being used by this chart.

        Returns
        -------
        out: str
            The colormap's name.
        """
        return self._cmap_name

    @property
    def group_selection_enabled(self):
        """
        Returns the state of the group selection option.
        """
        return self._group_selection

    @property
    def curvenames(self):
        """
        Returns the names of the curves.
        """
        return self._curvenames

    def set_group_selection_enabled(self, enable):
        """
        Enables or disables the group selection option.

        Parameters
        ----------
        enable: boolean
            True to enable group selection, False otherwise.
        """
        self._group_selection = enable

    def set_notify_tooltip_callback(self, func):
        """
        Sets the callback function to call when a tooltip is drawn on this
        plot.
        
        The callback function given here is called right after drawing the
        tooltip on this plot. This can be used to link several plots.

        Parameters
        ----------
        func: function
            The function to be called after a tooltip is drawn. This function
            receives the plot's name and the selected curve index.
        """
        self._cb_notify_tooltip = func

    def set_curves(self, curves_data, update_chart=True):
        """
        Sets the curve data to build the rankings. Note that calling this
        function resets the highlight status, as well as the reference and
        baseline curves.

        Arguments
        ---------
        curves_data: numpy.array
            A matrix containing the curves data.
        update_chart: boolean
            Switch to indicate if the plot should be redrawn after the data
            update. Default value is True.
        """
        self._curves = curves_data

        # Reseting the reference and baseline data
        self._reference_idx.clear()
        self._reference_parameters.clear()
        self._baseline_idx = None

        # Reseting the highlighted data
        self.highlight_data(self._highlighted_data,
                            erase=True, update_chart=False)

        if update_chart:
            self.update_chart(data_changed=True)

    def set_reference_curve(self, curve_idx, is_ref, update_chart=True,
                            **kwargs):
        """
        Marks a curve as reference if 'is_ref' is True. Restores the
        curve status as 'common' if 'is_ref' is False. This disengages the
        highlight of the selected curve and forbids it from happening.

        Arguments
        ---------
        curve_idx: int
            The index of the selected curve.
        is_ref: boolean
            Switch to indicate if the index is being marked as reference (True)
            or marked as a common curve (False).
        update_chart:boolean
            Switch to indicate if the plot should be updated with the new data.
            Default value is True.
        kwargs: Other graphical parameters
            Graphical parameters for the curve marked as reference (color,
            marker, size, and others accepted by axes.plot).
        """
        if curve_idx not in range(self.curves.shape[0]):
            raise ValueError(
                'Index out of range: {}/{}'.format(curve_idx, self.curves.shape[0]))
        if is_ref:
            self._reference_idx.add(curve_idx)
            self._reference_parameters[curve_idx] = kwargs
            if curve_idx in self.highlighted_data:
                self.highlight_data(curve_idx, erase=True, update_chart=False)
        else:
            self._reference_idx.discard(curve_idx)
            del self._reference_parameters[curve_idx]
        if update_chart:
            self.update_chart(data_changed=True)

    def set_baseline_curve(self, curve_idx, update_chart=True):
        """
        Sets the baseline curve to build the rankings. This curve will act
        as the 'zero' of our plot.

        Arguments
        ---------
        curve_idx: int
            The index of the baseline curve inside the curves matrix.
        update_chart: boolean
            Switch to indicate if the plot should be redrawn after the data
            update. Default value is True.
        """
        if curve_idx not in range(self.curves.shape[0]):
            raise ValueError('Index out of range')
        self._baseline_idx = curve_idx
        if update_chart:
            self.update_chart(data_changed=True)

    def set_curve_tooltip(self, curve_idx):
        """
        Draws the tooltip over the selected curve

        Parameters
        ----------
        curve_idx: int
            The index of the curve to draw the tooltip on.
        """
        if self._tooltip:
            self._tooltip.set_visible(False)

        # Restoring the lines' widths.
        if self._plotted_series:
            for art in self._plotted_series:
                if art:
                    art[0].set_linewidth(self._plot_params['linewidth'])

        if not curve_idx or curve_idx not in range(self.curves.shape[0]):
            self.draw()
            return

        # Increasing the width of the selected line.
        if not self._plotted_series[curve_idx]:
            return
        art = self._plotted_series[curve_idx][0]
        art.set_linewidth(self._plot_params['linewidth'] * 2)
        self.draw()

    def set_plot_title(self, title, update_chart=True):
        """
        Sets the title of this plot.

        Parameters
        ----------
        title: str
            This plot's title.
        update_chart: boolean
            Switch to indicate if the chart should be updated at the end of
            the method.
        """
        self._plot_title = title
        if update_chart:
            self.update_chart(data_changed=True)

    def set_colormap(self, cmap_name, update_chart=True):
        """
        Sets the colormap function to use when plotting.

        Parameters
        ----------
        cmap_name: str
        update_chart: boolean
            Switch to indicate if the plot should be updated. Default value
            is True.
        """
        self._cmap_name = cmap_name
        if update_chart:
            self.update_chart(data_changed=True)

    def set_curvenames(self, curvenames):
        """
        Sets the names of the data points. These are shown if the tooltip feature is enabled.

        Parameters
        ----------
        curvenames: list of str
            A list containing the data point's names.
        """
        self._curvenames = curvenames

    def mark_timestep_range(self, start, end):
        """
        Marks the selected timestep range with two vertical lines. Mainly used
        when linked to other plots, the user selects the desired timesteps, and
        these are marked on this plot as well. If the timestep range equals
        the total range of the plot, the marks will be erased.

        Parameters
        ----------
        start: int
            The first timestep.
        end: int
            The final timestep, this range is inclusive
        """
        pass

    # Callback methods
    def cb_mouse_motion(self, event):
        """
        Callback to process a mouse movement event.
        
        If the group selection option is enabled, then any points with
        Y-coordinate less than the cursor's Y-coordinate will be marked in a
        different opacity level, but not highlighted. If the user clicks with
        the mouse, then the points will be highlighted, but this event is
        processed in another method.

        This method also processes tooltip-related events when the group
        selection is disabled. If the user hovers the mouse cursor over a data
        point, then the name associated to that point will be shown in a
        tooltip.

        Parameters
        ----------
        event: matplotlib.backend_bases.MouseEvent
            Data about the event.
        """
        # We remove the horizonal line here (if any), regardless of the mouse
        # cursor position. We also restore the lines colors.
        if self._hthresh_line:
            lsize = len(self.axes.lines)
            del self.axes.lines[lsize - 1]
            self._hthresh_line = None

            for i, line in enumerate(self.axes.lines):
                if self._is_normal_curve_idx(i):
                    line.set_color(self._curves_colors[i])
            self.draw()

        # Erasing the tooltip.
        if self._tooltip:
            self._tooltip.set_visible(False)

        # Restoring the lines' widths.
        if self._plotted_series:
            for art in self._plotted_series:
                if not art:
                    continue
                art[0].set_linewidth(self._plot_params['linewidth'])

        if event.xdata is None or event.ydata is None or self._rank_series is None:
            return True

        if self.group_selection_enabled:
            tstep = int(event.xdata + 0.5)
            for i, series in enumerate(self._rank_series):
                if series[tstep] >= event.ydata and self._is_normal_curve_idx(i):
                    self.axes.lines[i].set_color(cm.gray(200))

            self._hthresh_line = self.axes.axhline(y=event.ydata, c='b',
                                                   linewidth=2)
        else:
            hover_idx = None
            for i, art in enumerate(self._plotted_series):
                if not art:
                    continue
                contains, _ = art[0].contains(event)
                if contains:
                    art[0].set_linewidth(self._plot_params['linewidth'] * 2)
                    if not self.curvenames or i > len(self.curvenames):
                        return False
                    hover_idx = i
                    break

            if hover_idx is not None:
                palette = QPalette()
                palette.setColor(QPalette.ToolTipBase, QColor(252, 243, 207))
                palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
                QToolTip.setPalette(palette)
                QToolTip.setFont(QFont('Arial', 14, QFont.Bold))
                pos = self.mapToGlobal(QPoint(event.x, self.height() - event.y))
                QToolTip.showText(pos,
                                  '{}'.format(self.curvenames[hover_idx]))
            else:
                QToolTip.hideText()
                self.update()

            if self._cb_notify_tooltip:
                self._cb_notify_tooltip(self.name, hover_idx)

        self.draw()

    def cb_mouse_button(self, event):
        """
        Callback to process a mouse button press event.
        Any points with Y-coordinate less than the cursor's Y-coordinate will
        be highlighted if the user clicks with the left mouse-button.

        Parameters
        ----------
        event: matplotlib.backend_bases.MouseEvent
            Data about the event.
        """
        if event.xdata is None or event.ydata is None or event.button is None:
            return True
        if self._rank_series is None:
            return True

        # Left mouse button pressed.
        if event.button == 1:
            to_highlight = []
            # If the group selection option is enabled, we perform a group
            # selection. Else, we just check each plotted line for collisions
            # with the mouse pointer and add them to the list of lines to
            # highlight.
            if self.group_selection_enabled:
                # Checking if there is any selected data. If there is, we pop a
                # confirmation dialog to the user.
                #if self.highlighted_data:
                #    title = 'Override selection'
                #    msg = 'Are you sure you wish to make a new selection?\nThe old selection will be erased.'
                #    ans = self.parent_canvas.popup_question_dialog(title, msg)
                #    if not ans:
                #        return True

                self.highlight_data(self.highlighted_data, erase=True,
                                    update_chart=False)
                ts = int(event.xdata + 0.5)
                for i, l in enumerate(self._rank_series):
                    if l[ts] < event.ydata and self._is_normal_curve_idx(i):
                        to_highlight.append(i)
            else:
                to_erase = []
                for i, line in enumerate(self._plotted_series):
                    if not line:
                        continue
                    contains, _ = line[0].contains(event)
                    if contains:
                        if i in self.highlighted_data:
                            to_erase.append(i)
                        else:
                            to_highlight.append(i)

                self.highlight_data(to_erase, erase=True, update_chart=False)

            self.highlight_data(to_highlight, erase=False, update_chart=True)
            self.notify_parent()

    def cb_axes_leave(self, event):
        """
        Callback to process an event generated when the mouse leaves the plot
        axes.

        This event erases the tooltip, if it exists, calls the
        "cb_notify_tooltip" callback, if set, to remove the tooltip from other
        views and restores the lines' widths to their original value.

        Parameters
        ----------
        event: matplotlib.backend_bases.LocationEvent
            Data about the event.
        """
        if self._tooltip:
            self._tooltip.set_visible(False)

        if self._cb_notify_tooltip:
            self._cb_notify_tooltip(self.name, None)

        # Restoring the lines' widths.
        if self._plotted_series:
            for art in self._plotted_series:
                if not art:
                    continue
                art[0].set_linewidth(self._plot_params['linewidth'])
        self.draw()

    def update_chart(self, **kwargs):
        if self.curves is None or not self._baseline_idx:
            return

        if 'selected_data' in kwargs:
            # If there are no selected series, we restore their alpha to 1.0
            # (totally opaque)
            bg_alpha = 0.1
            if not self.highlighted_data:
                bg_alpha = 1.0
            for i, line in enumerate(self.axes.lines):
                if i in self._reference_idx:
                    continue
                line.set_alpha(bg_alpha)
            for idx in self.highlighted_data:
                self.axes.lines[idx].set_alpha(1.0)

        if 'data_changed' in kwargs:
            self.axes.cla()
            self.axes.set_title(self.plot_title)
            self.axes.set_xlabel('Timestep')
            self.axes.set_ylabel('Rank')
            xmax = self._curves.shape[1] - 1
            ymax = self._curves.shape[0] + 1
            self.axes.set_xlim([0, xmax])
            self.axes.set_ylim([0, ymax])
            self._plotted_series = [None] * self.curves.shape[0]

            self._rank_series = rank_series(self._curves, self._baseline_idx)

            normal_idx = [i for i in range(len(self._rank_series))
                          if self._is_normal_curve_idx(i)]

            colormap = cm.get_cmap(name=self.colormap_name,
                                   lut=len(normal_idx))
            self._curves_colors = dict((i, colormap(i))
                                       for i in normal_idx)

            for i, r in enumerate(self._rank_series):
                if i == self._baseline_idx:
                    continue
                plot_params = self._plot_params
                if i in self._reference_idx:
                    plot_params = self._reference_parameters[i]
                else:
                    plot_params['color'] = self._curves_colors[i]
                self._plotted_series[i] = self.axes.plot(r, **plot_params)

            self.update_chart(selected_data=True)

        self.draw()

    # Private methods
    def _connect_cb(self):
        """
        Connects the callbacks to the matplotlib canvas.
        """
        fig = self.figure
        self._cb_mouse_move_id = fig.canvas.mpl_connect(
            'motion_notify_event', self.cb_mouse_motion)
        self._cb_mouse_button_id = fig.canvas.mpl_connect(
            'button_press_event', self.cb_mouse_button)
        self._cb_scrollwheel_id = fig.canvas.mpl_connect(
            'scroll_event', self._zoomhandler)
        self._cb_axes_leave_id = fig.canvas.mpl_connect(
            'axes_leave_event', self.cb_axes_leave)
        self._cb_fig_leave_id = fig.canvas.mpl_connect(
            'figure_leave_event', self.cb_axes_leave)

    def _disconnect_cb(self):
        """
        Detaches the callbacks from the matplotlib canvas.
        """
        fig = self.figure
        if self._cb_mouse_move_id:
            fig.canvas.mpl_disconnect(self._cb_mouse_move_id)
            self._cb_mouse_move_id = None
        if self._cb_mouse_button_id:
            fig.canvas.mpl_disconnect(self._cb_mouse_button_id)
            self._cb_mouse_button_id = None
        if self._cb_scrollwheel_id:
            fig.canvas.mpl_disconnect(self._cb_scrollwheel_id)
            self._cb_scrollwheel_id = None
        if self._cb_axes_leave_id:
            fig.canvas.mpl_disconnect(self._cb_axes_leave_id)
            self._cb_axes_leave_id = None
        if self._cb_fig_leave_id:
            fig.canvas.mpl_disconnect(self._cb_fig_leave_id)
            self._cb_fig_leave_id = None

    def _is_normal_curve_idx(self, idx):
        """
        Returns True if the given index is not a reference curve nor the
        baseline curve.
        """
        if not self._reference_idx or not self._baseline_idx:
            return True
        return idx not in self._reference_idx and idx != self._baseline_idx


def main():
    from PyQt5 import QtCore
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget,
                                 QHBoxLayout, QVBoxLayout, QPushButton,
                                 QMessageBox, QCheckBox)
    import sys
    """
    Simple feature test function for the TimeLapseLAMPChart class.
    """
    class MyTestWidget(QMainWindow):
        """
        Qt derived class to embed our plot.
        """

        def __init__(self):
            super().__init__()
            self.left = 0
            self.top = 0
            self.title = 'Dummy Qt widget'
            self.width = 600
            self.height = 400
            self.buildUI()
            self.update_data()

        def buildUI(self):
            self.setWindowTitle(self.title)
            self.setGeometry(self.left, self.top, self.width, self.height)
            self.setFocusPolicy(QtCore.Qt.WheelFocus)
            self.setFocus()

            self.rank_chart = RankChart(parent=self, canvas_name='rank1')

            p10_baseline_button = QPushButton('Set P10 as baseline', self)
            p10_baseline_button.clicked.connect(self.set_baseline_p10)
            p50_baseline_button = QPushButton('Set P50 as baseline', self)
            p50_baseline_button.clicked.connect(self.set_baseline_p50)
            p90_baseline_button = QPushButton('Set P90 as baseline', self)
            p90_baseline_button.clicked.connect(self.set_baseline_p90)
            rand_data = QPushButton('Generate new data', self)
            rand_data.clicked.connect(self.update_data)
            group_sel = QCheckBox('Group Selection', self)
            group_sel.setChecked(self.rank_chart.group_selection_enabled)
            group_sel.stateChanged.connect(self.set_group_selection)

            self.main_widget = QWidget(self)
            l = QHBoxLayout(self.main_widget)
            l.addWidget(self.rank_chart)
            button_layout = QVBoxLayout(self.main_widget)
            button_layout.addWidget(p10_baseline_button)
            button_layout.addWidget(p50_baseline_button)
            button_layout.addWidget(p90_baseline_button)
            button_layout.addWidget(rand_data)
            button_layout.addWidget(group_sel)
            l.addLayout(button_layout)

            self.setFocus()
            self.setCentralWidget(self.main_widget)

        def update_data(self):
            curves = np.random.normal(size=(8, 50))
            self.curves = np.vstack(
                (curves, np.percentile(curves, q=[10, 50, 90], axis=0)))

            self.rank_chart.set_curves(self.curves, False)
            self.rank_chart.set_reference_curve(self.curves.shape[0] - 3, True,
                                                False, color='r', marker='v')
            self.rank_chart.set_reference_curve(self.curves.shape[0] - 2, True,
                                                False, color='b', marker='<')
            self.rank_chart.set_reference_curve(self.curves.shape[0] - 1, True,
                                                False, color='g', marker='^')
            self.rank_chart.set_baseline_curve(self.curves.shape[0] - 2, True)

            curvenames = ['Curve-' + str(i) for i in range(curves.shape[0])]
            curvenames.extend(['P10', 'P50', 'P90'])
            self.rank_chart.set_curvenames(curvenames)

        def set_baseline_p10(self):
            self.rank_chart.set_baseline_curve(self.curves.shape[0] - 3, True)

        def set_baseline_p50(self):
            self.rank_chart.set_baseline_curve(self.curves.shape[0] - 2, True)

        def set_baseline_p90(self):
            self.rank_chart.set_baseline_curve(self.curves.shape[0] - 1, True)

        def set_brushed_data(self, child_name, obj_ids):
            print('widget {} brushed some objects.'.format(child_name))
            print('Objects:\n\t', obj_ids)

        def set_group_selection(self, i):
            check = True
            if i == QtCore.Qt.Unchecked:
                check = False
            self.rank_chart.set_group_selection_enabled(check)

        def popup_question_dialog(self, title, question):
            msg = QMessageBox(QMessageBox.Question, title, question,
                              QMessageBox.Yes | QMessageBox.No, self)
            answer = msg.exec()
            return answer == QMessageBox.Yes

    app = QApplication(sys.argv)
    ex = MyTestWidget()
    ex.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
