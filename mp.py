#!/usr/bin/python3
# -*- coding: utf-8 -*-

import numpy as np
import scipy.spatial.distance
from sklearn import manifold


def MDS(data, n_dim=2):
    '''
    Applies the Multidimensional Scaling algorithm to a dataset.
    Arguments
    ---------
    data: numpy.array
        A numpy matrix arranged by row
    n_dim: int
        The number of dimensions to project the data. Default value is 2

    Returns
    -------
    fit.embedding_: numpy.array
        A numpy array of Nxn_dim dimensions, where N is the number of data
        instances and n_dim is the number of dimensions to project.
    '''
    if n_dim < 2:
        raise ValueError('Invalid number of dimensions %d < 2.' % n_dim)
    if len(data.shape) != 2:
        raise ValueError('Invalid data matrix dimensions len(data.shape) > 2')
    if data.shape[0] < 3:
        raise ValueError(
            'Insufficient data instances to calculate the MDS (< 3).')

    D = scipy.spatial.distance.pdist(data, metric='euclidean')
    D = scipy.spatial.distance.squareform(D)
    mds = manifold.MDS(n_components=n_dim,
                       max_iter=500,
                       eps=1e-9,
                       dissimilarity='precomputed')
    fit = mds.fit(D)
    return fit.embedding_


def LAMP(X, Xs, Ys, tol=1e-9):
    '''
    Local Affine Multidimensional Projection (LAMP) is a multidimensional
    projection technique that uses control points located in the projected
    space to guide the projection of the remaining data instances.

    Parameters
    ----------
    X: numpy.array
        The input matrix of size MxN. M is the number of objects and N is the
        original dimension
    Xs: numpy.array
        A CxN matrix with the control points in the original N space. C is the
        number of control points.
    Ys: numpy.array
        A CxP matrix with the location of the control points in the projected
        space. C is the number of control points and P is the number of
        dimensions to project the data.
    tol: numeric(float or double)
        The numeric tolerance for calculations. Default value is 1e-9

    Returns
    -------
    out: numpy.array
        A MxP matrix, where each row is a single projected point. The control
        points are not included in the results.
    '''

    Y = np.zeros(shape=(X.shape[0], Ys.shape[1]), dtype=np.double)
    alphas = np.zeros(shape=Xs.shape[0], dtype=np.double)
    for cidx in range(X.shape[0]):
        # Calculating the alphas (Eq. 2).
        for i in range(Xs.shape[0]):
            alphas[i] = 1 / max(np.linalg.norm(Xs[i] - X[cidx]), tol)
        sum_alpha = alphas.sum()

        # Calculating x.tilde and y.tilde (Eq. 3).
        x_tilde = np.zeros(X.shape[1])
        y_tilde = np.zeros(Y.shape[1])

        for i in range(Xs.shape[0]):
            x_tilde += alphas[i] * Xs[i]
            y_tilde += alphas[i] * Ys[i]

        x_tilde /= sum_alpha
        y_tilde /= sum_alpha

        # Calculating x.hat and y.hat (Eq. 4).
        x_hat = np.zeros(shape=Xs.shape)
        y_hat = np.zeros(shape=Ys.shape)
        for i in range(Xs.shape[0]):
            x_hat[i] = Xs[i] - x_tilde
            y_hat[i] = Ys[i] - y_tilde

        # Calculating A and B (Eq. 6).
        A = np.zeros(shape=Xs.shape, dtype=np.double)
        B = np.zeros(shape=(Xs.shape[0], Ys.shape[1]), dtype=np.double)
        for i in range(Xs.shape[0]):
            A[i] = np.sqrt(alphas[i]) * x_hat[i]
            B[i] = np.sqrt(alphas[i]) * y_hat[i]

        # SVD decomposition of A.T * B (Eq. 7).
        U, D, V = np.linalg.svd(np.dot(A.T, B))

        # Orthogonal transform matrix (Eq. 8).
        M = np.dot(U[:, 0:Ys.shape[1]], V)

        # Actual projection of the data.
        Y[cidx] = np.dot(X[cidx] - x_tilde, M) + y_tilde

    return Y


def time_lapse_lamp(original_data,
                    control_points_orig_space,
                    control_points_proj,
                    start_time=None,
                    end_time=None):
    '''
    Parameters
    ----------
    original_data: numpy.array
        The data to be projected arranged by row.
    control_points_orig_space: numpy.array
        The control points data in the original space (not projected) arranged by row.
    control_points_proj: numpy.array
        The locations of the control points in the projected space.

    Returns
    -------
    points: list of numpy.array
        A list containing the projections for each timestep in the
        (start_time, end_time) range.
    '''

    if not start_time:
        start_time = 0
    if not end_time:
        end_time = original_data.shape[1]
    if end_time > original_data.shape[1]:
        end_time = original_data.shape[1]
    points = []
    for t in range(start_time + 2, end_time + 1):
        data = original_data[:, start_time:t]
        cp_orig = control_points_orig_space

        if data.shape[1] < cp_orig.shape[1]:
            zeros_pad = np.zeros(
                shape=(data.shape[0], cp_orig.shape[1] - data.shape[1]))
            data = np.hstack((data, zeros_pad))
        elif data.shape[1] > cp_orig.shape[1]:
            zeros_pad = np.zeros(
                shape=(cp_orig.shape[0], data.shape[1] - cp_orig.shape[1]))
            cp_orig = np.hstack((cp_orig, zeros_pad))

        Y = LAMP(X=data, Xs=cp_orig, Ys=control_points_proj)
        points.append(Y)

    return points


def test_lamp():
    import matplotlib.pyplot as plt
    X = np.array([[1, 2, 3],
                  [4, 5, 6],
                  [2, 3, 4],
                  [4, 3, 2],
                  [2, 4, 6],
                  [1, 9, 5],
                  [1, 3, 9]], dtype=np.double)

    Xs = np.array([[3, 2, 1],
                   [6, 8, 9],
                   [9, 8, 7]], dtype=np.double)

    Ys = np.array([[4, 9],
                   [1, 1],
                   [9, 6]], dtype=np.double)

    Y = LAMP(X, Xs, Ys)
    plt.scatter(Y[:, 0], Y[:, 1])
    plt.scatter(Ys[:, 0], Ys[:, 1], color='red')
    plt.show()

if __name__ == '__main__':
    test_lamp()
