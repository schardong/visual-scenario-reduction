#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from zoomhandler import ZoomHandler
from panhandler import PanHandler
import numpy as np
import matplotlib.pyplot as plt

def main():
    fig = plt.figure()
    axes = fig.add_subplot(111)
    axes.scatter(x=np.arange(0, 10, 0.5), y=np.arange(0, 10, 0.5), color='g', marker='<')
    axes.axhspan(ymin=4, ymax=6, alpha=0.6)
    axes.axvspan(xmin=3, xmax=8, alpha=0.4)
    zhand = ZoomHandler(axes)
    phand = PanHandler(axes, 3)
    fig.canvas.mpl_connect('scroll_event', zhand)
    plt.show()

if __name__ == '__main__':
    main()
