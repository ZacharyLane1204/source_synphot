# -*- coding: UTF-8 -*-
"""
Instrumental throughput models and calibration and synthetic photometry
routines
"""

from __future__ import absolute_import
from __future__ import unicode_literals
from . import io
import numpy as np
import pysynphot as S
from collections import OrderedDict

def synflux(spec, pb):
    """
    Compute the synthetic flux of spectrum ``spec`` through passband ``pb``

    Parameters
    ----------
    spec : :py:class:`pysynphot.ArraySpectrum`
        The spectrum. Must have ``dtype=[('wave', '<f8'), ('flux', '<f8')]``
    pb : :py:class:`pysynphot.ArrayBandpass` or :py:class:`pysynphot.obsbandpass.ObsModeBandpass`
        The passband data.
        Must have ``dtype=[('wave', '<f8'), ('throughput', '<f8')]``

    Returns
    -------
    flux : float
        The normalized flux of the spectrum through the passband

    Notes
    -----
        The passband is assumed to be dimensionless photon transmission
        efficiency.

        Routine is intended to be a mch faster implementation of
        :py:meth:`pysynphot.observation.Observation.effstim`, since it is called over and
        over by the samplers as a function of model parameters.

        Uses :py:func:`numpy.trapz` for interpolation.
    """
    flux = spec.sample(pb.wave)
    n = np.trapz(flux*pb.wave*pb.throughput, pb.wave)
    d = np.trapz(pb.wave*pb.throughput, pb.wave)
    out = n/d
    return out


def synphot(spec, pb, zp=0.):
    """
    Compute the synthetic magnitude of spectrum ``spec`` through passband ``pb``

    Parameters
    ----------
    spec : :py:class:`pysynphot.ArraySpectrum`
        The spectrum. Must have ``dtype=[('wave', '<f8'), ('flux', '<f8')]``
    pb : array-like
        The passband transmission.
        Must satisfy ``pb.shape == spec[ind].flux.shape``
    zp : float, optional
        The zeropoint to apply to the synthetic flux

    Returns
    -------
    mag : float
        The synthetic magnitude of the spectrum through the passband

    See Also
    --------
    :py:func:`source_synphot.passband.synflux`
    """
    flux = synflux(spec, pb)
    m = -2.5*np.log10(flux) + zp
    return m


def get_pb_zpt(pb, reference='AB', model_mag=None):
    """
    Determines a passband zeropoint for synthetic photometry, given a reference
    standard and its model magnitude in the passband

    Parameters
    ----------
    pb : :py:class:`pysynphot.ArrayBandpass` or :py:class:`pysynphot.obsbandpass.ObsModeBandpass`
        The passband data.
        Must have ``dtype=[('wave', '<f8'), ('throughput', '<f8')]``
    reference : str, optional
        The name of the reference spectrophotometric standard to use to determine the passband zeropoint.
        'AB' or 'Vega' (default: 'AB')
    model_mag : float, optional 
        The magnitude of the reference spectrophotometric standard in the passband.
        default = None

    Returns
    -------
    pbzp : float
        passband AB zeropoint 
        
    Raises
    ------
    RuntimeError
        If the passband and reference standard do not overlap
    ValueError
        If the reference model_mag is invalid
    """

    # setup the photometric system by defining the standard and corresponding magnitude system
    if reference.lower() not in ('vega', 'ab'):
        message = 'Do not understand mag system reference standard {}. Must be AB or Vega'.format(reference)
        raise RuntimeError(message)
    if reference.lower() == 'ab':
        refspec = S.FlatSpectrum(3631, fluxunits='jy')
        mag_type= 'abmag'
    else:
        refspec    = S.Vega
        mag_type= 'vegamag'

    refspec.convert('flam')

    if model_mag is None:
        ob = S.Observation(refspec, pb)
        model_mag = ob.effstim(mag_type)
    
    synphot_mag = synphot(refspec, pb, zp=0.)
    outzp = model_mag - synphot_mag
    return outzp


def get_pbs(pbnames, model_mags, model='AB'):

    pbs = OrderedDict()
    if np.isscalar(pbnames):
        pbnames = np.array(pbnames, ndmin=1)
    else:
        pbnames = np.array(pbnames).flatten()
    npb = len(pbnames)

    if np.isscalar(model_mags):
        model_mags = np.repeat(model_mags, npb)
    else:
        model_mags = np.array(model_mags).flatten()

    if len(model_mags) != npb:
        message = 'Model mags and pbnames must be 1-D arrays with the same shape'
        raise ValueError(message)

    for i, pbmag in enumerate(zip(pbnames, model_mags)):
        pb, mag = pbmag
        thispb, _ = io.get_passband(pb)
        thispbzp = get_pb_zpt(thispb, model_mag=mag, reference=model)
        pbs[pb] = thispb, thispbzp

    return pbs
