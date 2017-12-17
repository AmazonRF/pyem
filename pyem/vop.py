#!/usr/bin/env python2.7
# Copyright (C) 2017 Daniel Asarnow
# University of California, San Francisco
#
# Library functions for volume data.
# See README file for more information.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import numpy as np
from scipy.ndimage import label
from scipy.ndimage import labeled_comprehension
from scipy.ndimage import map_coordinates


def ismask(vol):
    """
    Even with a soft edge, a mask will have very few unique values (unless it's already been resampled).
    The 1D slice below treats just the central XY section for speed. Real maps have ~20,000 unique values here.
    """
    return np.unique(vol[vol.shape[2] / 2::vol.shape[2]]).size < 100


def resample_volume(vol, r=None, t=None, ori=None, order=3, compat="mrc2014", indexing="xy"):
    if r is None and t is None:
        return vol.copy()

    if ori is None:
        ori = np.array(vol.shape) / 2

    x, y, z = np.meshgrid(*[np.arange(-o, o) for o in ori], indexing=indexing)
    xyz = np.vstack([x.reshape(-1), y.reshape(-1), z.reshape(-1), np.ones(x.size)])

    th = np.eye(4)
    if t is None and r.shape[1] == 4:
        t = np.squeeze(r[:, 3]) - ori
    elif t is not None:
        th[:3, 3] = t - ori

    rh = np.eye(4)
    if r is not None:
        rh[:3:, :3] = r[:3, :3].T

    xyz = th.dot(rh.dot(xyz))[:3, :] + ori[:, None]
    xyz = np.array([arr.reshape(vol.shape) for arr in xyz])

    if "relion" in compat.lower() or "xmipp" in compat.lower():
        xyz = xyz[::-1]

    newvol = map_coordinates(vol, xyz, order=order)
    return newvol


def grid_correct(vol, pfac=2, order=1):
    n = vol.shape[0]
    nhalf = n / 2
    npad = nhalf * pfac - nhalf
    x, y, z = np.meshgrid(*[np.arange(-nhalf, nhalf)] * 3, indexing="xy")
    r = np.sqrt(x**2 + y**2 + z**2) / (n * pfac)
    sinc = np.sin(np.pi * r) / (np.pi * r)  # Results in 1 NaN in the center.
    sinc[nhalf, nhalf, nhalf] = 1.
    if order == 0:
        cordata = vol / sinc
    elif order == 1:
        cordata = vol / sinc**2
    else:
        raise NotImplementedError("Only nearest-neighbor and trilinear grid corrections are available")
    cordata = np.pad(cordata, npad, "constant", constant_values=0)
    return cordata


def interpolate_slice(f3d, rot, pfac=2, size=None):
    nhalf = f3d.shape[0] / 2
    if size is None:
        phalf = nhalf
    else:
        phalf = size / 2
    qot = rot * pfac  # Scaling!
    px, py, pz = np.meshgrid(np.arange(-phalf, phalf), np.arange(-phalf, phalf), 0)
    pr = np.sqrt(px ** 2 + py ** 2 + pz ** 2)
    pcoords = np.vstack([px.reshape(-1), py.reshape(-1), pz.reshape(-1)])
    mcoords = qot.T.dot(pcoords)
    mcoords = mcoords[:, pr.reshape(-1) < nhalf]
    pvals = map_coordinates(np.real(f3d), mcoords, order=1, mode="wrap") + \
             1j * map_coordinates(np.imag(f3d), mcoords, order=1, mode="wrap")
    pslice = np.zeros(pr.shape, dtype=np.complex)
    pslice[pr < nhalf] = pvals
    return pslice


def binary_sphere(r, le=True):
    rr = np.linspace(-r, r, 2 * r + 1)
    x, y, z = np.meshgrid(rr, rr, rr)
    if le:
        sph = (x ** 2 + y ** 2 + z ** 2) <= r ** 2
    else:
        sph = (x ** 2 + y ** 2 + z ** 2) < r ** 2
    return sph


def binary_volume_opening(vol, minvol):
    lb_vol, num_objs = label(vol)
    lbs = np.arange(1, num_objs + 1)
    v = labeled_comprehension(lb_vol > 0, lb_vol, lbs, np.sum, np.int, 0)
    ix = np.isin(lb_vol, lbs[v >= minvol])
    newvol = np.zeros(vol.shape)
    newvol[ix] = vol[ix]
    return newvol
