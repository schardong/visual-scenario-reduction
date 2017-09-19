#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
This module contains the main Qt5 widget to plot the data, plus its unit tests.
'''

import numpy as np
from PyQt5 import QtCore
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QMessageBox, QWidget

from distplot import DistanceChart
from fanchart import Fanchart
from rankplot import RankChart
from tlplot import TimeLapseChart


class PlotWidget(QWidget):
    '''
    This Qt widget inherited class handles the matplotlib canvases
    instantiations and the brushing events coordination between them.
    '''

    def __init__(self, parent=None):
        super(PlotWidget, self).__init__(parent)

        self._num_dim = 2
        self._curves = None
        self._time_range = ()
        self._max_time_range = ()
        self._cmap_name = 'rainbow'
        self._property_name = ''
        self._curvenames = None
        self._baseline_id = 'p50'

        self._child_plots = {}
        f = Fanchart(canvas_name='fan', parent=self)
        l = TimeLapseChart(canvas_name='tl', parent=self)
        l.set_plot_title(
            'Time-lapsed Local Affine Multidimensional Projection Chart')
        r = RankChart(canvas_name='rank', parent=self)
        d = DistanceChart(canvas_name='dist', parent=self)

        l.set_notify_timestep_callback(self.set_highlighted_timestep)

        l.set_notify_tooltip_callback(self.set_curve_tooltip)
        d.set_notify_tooltip_callback(self.set_curve_tooltip)
        r.set_notify_tooltip_callback(self.set_curve_tooltip)

        self._child_plots['fan'] = f
        self._child_plots['tl'] = l
        self._child_plots['rank'] = r
        self._child_plots['dist'] = d

        for canvas in self._child_plots.values():
            canvas.setFocusPolicy(QtCore.Qt.WheelFocus)
            # canvas.set_notify_tooltip_callback(self.set_curve_tooltip)

        lt = QGridLayout(self)
        lt.addWidget(l, 0, 0)
        lt.addWidget(f, 0, 1)
        lt.addWidget(r, 1, 0)
        lt.addWidget(d, 1, 1)
        self.setLayout(lt)
        self._plot_params = None

    @property
    def curves(self):
        '''
        Returns the curves being used in the plots.
        '''
        return self._curves

    @property
    def num_dim(self):
        '''
        Returns the number of dimensions used for projection.
        '''
        return self._num_dim

    @property
    def property_name(self):
        """
        Returns the current time-series property name.
        """
        return self._property_name

    @property
    def baseline_id(self):
        """
        Returns the current ID of the current baseline curve.
        """
        return self._baseline_id

    @property
    def timerange(self):
        """
        Returns the timestep range used by the time-based plots (Fan, bump and
        Distance charts).

        Returns
        -------
        A tuple with the start and end timesteps.
        """
        return self._time_range

    @property
    def max_timerange(self):
        """
        Returns the maximum time range allowed by the plots. This time range
        is calculated based on the data's dimensions.

        Returns
        -------
        A tuple with the maximum start and end timesteps.
        """
        return self._max_time_range

    def set_property_name(self, name, update_charts=True):
        """
        Sets the current time-series property name.

        Parameters
        ----------
        name: str
            The new property name. If equal to None, will remove the property
            name from the plot titles.
        """
        self._property_name = name
        for plt in self._child_plots.values():
            base_name = plt.base_plot_name()
            base_name += ' of ' + name
            plt.set_plot_title(base_name, update_chart=update_charts)

    def set_brushed_data(self, widget_name, highlighted_series):
        '''
        Sets the selected series as highlighted and notifies the child widgets.

        Parameters
        ----------
        widget_name: str
            The name of the child widget that triggered the event.
        highlighted: list of ints
            The index or indices of the newly selected series.
        '''
#        print('caller: {}'.format(widget_name))
#        print(highlighted_series)
#        print('-----------------------')
        if isinstance(highlighted_series, int):
            highlighted_series = [highlighted_series]

        for i in highlighted_series:
            if i not in range(self._curves.shape[0]):
                raise ValueError(
                    'One of the selected indices is out of range.')

        for k, widget in self._child_plots.items():
            if k == widget_name:
                continue
            fhigh = widget.highlighted_data

            widget.highlight_data(fhigh,
                                  erase=True,
                                  update_chart=False)

            widget.highlight_data(highlighted_series,
                                  erase=False,
                                  update_chart=True)

    def set_highlighted_timestep(self, name, timestep):
        """
        Callback given to the time-lapsed plot to notify the fanchart of about
        a selected timestep.

        Parameters
        ----------
        name: str
            The signal emitter name.
        timestep: int
            The timestep selected.
        """
        self._child_plots['fan'].set_highlighted_timestep(timestep)

    def set_curve_tooltip(self, widget_name, curve_idx):
        """
        Notifies the children widgets that a tooltip was drawn in one of them.
        The widgets can then opt to draw the tooltip over the corresponding
        curve.

        Parameters
        ----------
        widget_name: str
            The name of the child widget that triggered the event.
        curve_idx:
            The index of the selected curve.
        """
#        print('caller: {}'.format(widget_name))
#        print('curve idx: {}'.format(curve_idx))

        for k, widget in self._child_plots.items():
            if k == widget_name:
                continue
            widget.set_curve_tooltip(curve_idx)

    def popup_question_dialog(self, title, question):
        """
        Pops a question dialog for the user and returns the answer to the
        caller.

        This method is meant to be called by the children widgets in order
        to ask for confirmation for a given action. It pops a Qt Yes/No dialog
        and returns the user's selection.

        Parameters
        ----------
        title: str
            The popup title
        question: str
            The popup question
        Returns
        -------
        True if the user clicked 'Yes', False otherwise.
        """
        msg = QMessageBox(QMessageBox.Question, title, question,
                          QMessageBox.Yes | QMessageBox.No, self)
        answer = msg.exec()
        return answer == QMessageBox.Yes

    def set_curves(self, curve_data):
        '''
        Sets the current set of curves to be plotted. For the distance and rank
        charts, since the reference curve will be removed by the set_curves
        call, the p50 curve will be set as the baseline. The percentile curves
        are calculated automatically within the method.

        The current and maximum time ranges are also reset to the default
        values of [0, curve_data.shape[1]].

        Parameters
        ----------
        curve_data: numpy.array
            A matrix of curves arranged by row.
        '''
        self._curves = np.vstack((curve_data,
                                  np.percentile(curve_data,
                                                q=[10, 50, 90], axis=0)))

        self._max_time_range = (0, curve_data.shape[1])
        self._time_range = self._max_time_range

        for plot in self._child_plots.values():
            plot.set_curves(self.curves, update_chart=False)

        color_list = ['m', 'c', 'g']
        marker_list = ['v', '<', '^']
        curve_idx = range(self.curves.shape[0] - 3, self.curves.shape[0])
        for i, idx in enumerate(curve_idx):
            for _, plot_v in self._child_plots.items():
                plot_v.set_reference_curve(idx, is_ref=True,
                                           update_chart=False,
                                           color=color_list[i],
                                           marker=marker_list[i])

        if not self.baseline_id:
            self.set_baseline_curve('p50')
        else:
            self.set_baseline_curve(self.baseline_id)

    def set_curvenames(self, curvenames):
        """
        Sets the names for the curves given to this plot. These names may
        be shown in the plot's tooltips.

        Parameters
        ----------
        curvenames: list of str
            A list with the curvenames. No length checks are done in this method.
        """
        self._curvenames = curvenames
        self._curvenames.extend(['P10', 'P50', 'P90'])
        for plot in self._child_plots.values():
            plot.set_curvenames(self._curvenames)

    def set_baseline_curve(self, baseline_id):
        '''
        Sets the baseline curve for the Rank and Distance charts. Since this
        call erases those plots and removes the highlights, we reset the
        highlight status on the TLchart and the Fanchart instances as well.

        Parameters
        ----------
        baseline_id: str
           The ID of the baseline curve. Possible values are: p10, p50 and p90.
        '''
        if not (baseline_id == 'p10' or baseline_id == 'p50' or
                baseline_id == 'p90'):
            fmt = r'Invalid baseline given: {}. Possible values are: \'p10\', \'p50\, \'p90\'.'
            raise ValueError(fmt.format(baseline_id))

        id_to_idx = {'p10': self.curves.shape[0] - 3,
                     'p50': self.curves.shape[0] - 2,
                     'p90': self.curves.shape[0] - 1}

        self._child_plots['rank'].set_baseline_curve(id_to_idx[baseline_id],
                                                     update_chart=True)
        self._child_plots['dist'].set_baseline_curve(id_to_idx[baseline_id],
                                                     update_chart=True)

        self._baseline_id = baseline_id

    def set_num_dimensions(self, n):
        '''
        Sets the number of dimensions for projection
.
        Parameters
        ----------
        n: int
            The number of dimensions for projection.
        '''
        if n <= 1 or n > 3:
            raise ValueError(
                'Invalid number of dimensions. n must be in [2, 3]')

        self._num_dim = n

    def set_colormap(self, cmap_name):
        """
        Sets the colormap to use in the plots.

        Parameters
        ----------
        cmap_name: str
            The colormap name. Accepted values are the same as those accepted
            by matplotlib.
        """
        pass

    def clear_selected_data(self):
        '''
        Clears the highlight status of all data instances of all charts.
        '''
        for p in self._child_plots.values():
            p.highlight_data(p.highlighted_data, erase=True,
                             update_chart=True)

    def update_charts(self, **kwargs):
        for chart in self._child_plots.values():
            chart.update_chart(**kwargs)

    def set_plot_points_tlchart(self, plot_points):
        """
        Sets wheter the time-lapsed projection chart should plot the projected
        points.

        Parameters
        ----------
        plot_points: boolean
            True to enable point plotting, False to disable it.
        """
        self._child_plots['tl'].set_plot_points(plot_points)

    def get_plot_points_tlchart(self):
        """
        Returns if the time-lapsed projection chart is plotting the projection
        points.

        Returns
        -------
        True if point plotting is enabled.
        """
        return self._child_plots['tl'].plot_points

    def set_plot_lines_tlchart(self, plot_lines):
        """
        Sets wheter the time-lapsed projection chart should plot lines
        connecting the projected points.

        Parameters
        ----------
        plot_lines: boolean
            True to enable line plotting, False to disable it.
        """
        self._child_plots['tl'].set_plot_lines(plot_lines)

    def get_plot_lines_tlchart(self):
        """
        Returns if the time-lapsed projection chart is plotting the lines
        connecting the projection points.

        Returns
        -------
        True if line plotting is enabled.
        """
        return self._child_plots['tl'].plot_lines

    def set_log_scale_distchart(self, log_scale):
        """
        Sets wheter the distances should be converted to log_10 scale.

        Parameters
        ----------
        log_scale: boolean
            True to convert the distances to log scale, False to use the
            normal scale.
        """
        self._child_plots['dist'].set_log_scale(log_scale)

    def get_log_scale_distchart(self):
        """
        Returns wheter the distance values were converted to log scale in the
        distance chart.

        Returns
        -------
        True if the distances are in log_10 scale.
        """
        return self._child_plots['dist'].log_scale

    def set_fan_color_pallete(self, cmap_name):
        """
        Sets the current colormap to be used by the fanchart.

        Parameters
        ----------
        cmap_name: str
            The name of the colormap. Any colormaps accepted by matplotlib are
            valid.
        """
        self._child_plots['fan'].set_fan_colormap(cmap_name)

    def get_fan_color_pallete(self):
        """
        Returns the name of the current colormap used by the fanchart.

        Returns
        -------
        The colormap name.
        """
        return self._child_plots['fan'].fan_colormap_name

    def set_data_color_pallete(self, cmap_name):
        """
        Sets the colormap of the data. For the projection and distance data,
        this sets the points' colors. For the rank and fan charts, this sets
        the lines' colors.

        Parameters
        ----------
        cmap_name: str
            The name of the colormap. Any colormaps accepted by matplotlib are
            valid.
        """
        self._cmap_name = cmap_name
        self._child_plots['fan'].set_lines_colormap(cmap_name,
                                                    update_chart=False)
        self._child_plots['tl'].set_colormap(cmap_name, update_chart=False)
        self._child_plots['rank'].set_colormap(cmap_name, update_chart=False)
        self._child_plots['dist'].set_colormap(cmap_name, update_chart=False)
        self.update_charts(data_changed=True)

    def get_data_color_pallete(self):
        """
        Returns the name of the colormap used for the data. For the projection
        and distance data, this means the points' colors. For the rank and fan
        charts, this means the lines' colors.
        """
        return self._cmap_name

    def fan_show_p10(self):
        fan = self._child_plots['fan']
        c = fan.curves.shape[0]
        erase = not fan.is_reference_curve(c - 3)
        fan.set_reference_curve(c - 3, erase, True,
                                color='m', marker='v')

    def fan_is_showing_p10(self):
        fan = self._child_plots['fan']
        c = fan.curves.shape[0]
        return fan.is_reference_curve(c - 3)

    def fan_show_p50(self):
        fan = self._child_plots['fan']
        c = fan.curves.shape[0]
        erase = not fan.is_reference_curve(c - 2)
        fan.set_reference_curve(c - 2, erase, True,
                                color='c', marker='<')

    def fan_is_showing_p50(self):
        fan = self._child_plots['fan']
        c = fan.curves.shape[0]
        return fan.is_reference_curve(c - 2)

    def fan_show_p90(self):
        fan = self._child_plots['fan']
        c = fan.curves.shape[0]
        erase = not fan.is_reference_curve(c - 1)
        fan.set_reference_curve(c - 1, erase, True,
                                color='g', marker='^')

    def fan_is_showing_p90(self):
        fan = self._child_plots['fan']
        c = fan.curves.shape[0]
        return fan.is_reference_curve(c - 1)

    def save_plots(self):
        for name, pl in self._child_plots.items():
            f = pl.figure
            f.savefig(name + '.pdf', dpi=300, bbox_inches='tight')

    def get_group_selection_distchart(self):
        return self._child_plots['dist'].group_selection_enabled

    def set_group_selection_distchart(self, enabled):
        self._child_plots['dist'].set_group_selection_enabled(enabled)

    def get_group_selection_rankchart(self):
        return self._child_plots['rank'].group_selection_enabled

    def set_group_selection_rankchart(self, enabled):
        self._child_plots['rank'].set_group_selection_enabled(enabled)

    def set_timestep_range(self, ts_start, ts_end):
        self._time_range = (ts_start, ts_end)
        dist_plot = self._child_plots['dist']
        highlighted_data = dist_plot.highlighted_data

        # Reseting the distance chart's curves.
        dist_plot.set_curves(
            self._curves[:, ts_start:ts_end], update_chart=False)
        color_list = ['m', 'c', 'g']
        marker_list = ['v', '<', '^']
        curve_idx = range(self.curves.shape[0] - 3, self.curves.shape[0])
        for i, idx in enumerate(curve_idx):
            dist_plot.set_reference_curve(idx, is_ref=True,
                                          update_chart=False,
                                          color=color_list[i],
                                          marker=marker_list[i])

        # Setting the distance charts' baseline and highlighted data
        # (both erased by the previous 'set_curves' call).
        if not self.baseline_id:
            self.set_baseline_curve('p50')
        else:
            self.set_baseline_curve(self.baseline_id)

        dist_plot.highlight_data(highlighted_data,
                                 erase=False,
                                 update_chart=True)

        # Setting the time range on the fanchart and bump chart.
        self._child_plots['fan'].mark_timestep_range(ts_start, ts_end)
        self._child_plots['rank'].mark_timestep_range(ts_start, ts_end)


def plot_widget_main_test():
    from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget,
                                 QPushButton, QVBoxLayout)
    import sys
    '''
    Simple feature test function for the PlotWidget class.
    '''
    class MyTestWidget(QMainWindow):
        '''
        Qt derived class to embed our plot.
        '''

        def __init__(self):
            super().__init__()
            self.left = 0
            self.top = 0
            self.title = 'PlotWidget test'
            self.width = 1600
            self.height = 1000
            self.buildUI()
            self.update_data()

        def buildUI(self):
            self.setWindowTitle(self.title)
            self.setGeometry(self.left, self.top, self.width, self.height)

            self.plotwidget = PlotWidget()

            p10_baseline_button = QPushButton('Set P10 as baseline', self)
            p10_baseline_button.clicked.connect(self.set_baseline_p10)
            p50_baseline_button = QPushButton('Set P50 as baseline', self)
            p50_baseline_button.clicked.connect(self.set_baseline_p50)
            p90_baseline_button = QPushButton('Set P90 as baseline', self)
            p90_baseline_button.clicked.connect(self.set_baseline_p90)
            rand_data = QPushButton('Generate new data', self)
            rand_data.clicked.connect(self.update_data)
            save_plots_button = QPushButton('Save plots to PDF files', self)
            save_plots_button.clicked.connect(self.save_plots)

            self.main_widget = QWidget(self)
            l = QHBoxLayout(self.main_widget)
            l.addWidget(self.plotwidget)
            button_layout = QVBoxLayout(self.main_widget)
            button_layout.addWidget(p10_baseline_button)
            button_layout.addWidget(p50_baseline_button)
            button_layout.addWidget(p90_baseline_button)
            button_layout.addWidget(rand_data)
            button_layout.addWidget(save_plots_button)
            l.addLayout(button_layout)

            self.setFocus()
            self.setCentralWidget(self.main_widget)

        def update_data(self):
            self.curves = np.random.normal(size=(15, 30))
            self.plotwidget.set_property_name('Random Data')
            self.plotwidget.set_curves(self.curves)
            self.plotwidget.set_baseline_curve('p50')
            self.plotwidget.update_charts(data_changed=True)

        def set_baseline_p10(self):
            self.plotwidget.set_baseline_curve('p10')

        def set_baseline_p50(self):
            self.plotwidget.set_baseline_curve('p50')

        def set_baseline_p90(self):
            self.plotwidget.set_baseline_curve('p90')

        def save_plots(self):
            self.plotwidget.save_plots()

        def set_brushed_data(self, child_name, obj_ids):
            print('widget {} brushed some objects.'.format(child_name))
            print('Objects:\n\t', obj_ids)

    app = QApplication(sys.argv)
    ex = MyTestWidget()
    ex.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    plot_widget_main_test()
