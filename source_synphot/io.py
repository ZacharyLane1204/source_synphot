# -*- coding: UTF-8 -*-
"""
I/O methods. All the submodules of the source_synphot package use this module
for I/O operations, but they are typically not directly useful themselves.
"""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import sys
import os
import warnings
import argparse
import pkg_resources
import numpy as np
import astropy.table as at
import pysynphot as S


def get_options(args=None):
    """
    Get command line options

    Parameters
    ----------
    args : None or array-like
        list of the input command line arguments, typically from
        :py:data:`sys.argv` (which is used if None)

    Returns
    -------
    args : Namespace
        Parsed command line options

    Raises
    ------
    ValueError
        If any input value is invalid

    """
    from argparse import ArgumentParser
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,\
                    description=__doc__,\
                    epilog="source_synphot always assumes passbands are %\
                    photon transmission. If your passbands are defined as %\
                    energy transmission at each wavelength, convert them.\
                    Redshifts are assumed to be in the CMB frame.")

    source_input = parser.add_argument_group('source input', 'Source Input Options')
    source_input.add_argument('--sourcespec', required=True,\
            help="Specify source spectrum - relative F_lam")
    source_input.add_argument('--sourcez', required=False, type=float, default=0.,\
            help='Specify redshift of source spectrum')
    source_input.add_argument('--sourcepb', required=False, type=str,\
            help="Specify source passband")
    source_input.add_argument('--sourcemag', required=False, type=float, default=0.,\
            help="Specify source magnitude in passband")
    source_input.add_argument('--sourcepbzp', required=False, type=float, default=0.,\
            help="Specify zeropoint of source passband (default uses lookup table)")

    target_output = parser.add_argument_group('target output', 'Target Output Options')
    target_output.add_argument('--targetz', required=False, type=float, default=0.,\
            help='Specify redshift of target')
    target_output.add_argument('--targetpbs', required=False, nargs='+',\
            help="Specify target output passband(s) - default will use all in lookup table")

    if args is None:
        args = sys.argv[1:]
    args = parser.parse_args(args=args)

    if args.sourcez < 0:
        message = 'Source CMB frame redshift cannot be less than 0'
        raise ValueError(message)

    if args.targetz < 0:
        message = 'Target CMB frame redshift cannot be less than 0'
        raise ValueError(message)

    args.sourcepb = str(args.sourcepb)

    return args


def get_pkgfile(infile):
    """
    Returns the full path to a file inside the :py:mod:`source_synphot` package

    Parameters
    ----------
    infile : str
        The name of the file to set the full package filename for

    Returns
    -------
    pkgfile : str
        The path to the file within the package.

    Raises
    ------
    IOError
        If the ``pkgfile`` could not be found inside the :py:mod:`source_synphot` package.

    Notes
    -----
        This allows the package to be installed anywhere, and the code to still
        determine the location to a file included with the package, such as the
        passband definition file
    """
    pkgfile = pkg_resources.resource_filename('source_synphot',infile)
    if not os.path.exists(pkgfile):
        message = 'Could not find package file {}'.format(pkgfile)
        raise IOError(message)
    return pkgfile


def read_passband(pb, pbzp=None):
    """
    Read a passband.


    Parameters
    ----------
    pb : str
        pysynphot obsmode or obsmode listed in `pbzptmag.txt`
    pbzp : float, optional
        AB magnitude zeropoint of the passband

    Returns
    -------
    pb : :py:class:`pysynphot.ArrayBandpass` or :py:class:`pysynphot.obsbandpass.ObsModeBandpass`
        The passband data.
        Has ``dtype=[('wave', '<f8'), ('throughput', '<f8')]``
    pbzp : float
        passband AB zeropoint - potentially NaN if this was not supplied. If NaN
        this can be computed assuming an AB source - i.e. a source with a flux
        density of 3631 jy has magnitude = 0 in the bandpass.

    Notes
    -----
        Note that this is a straight read of a single passband from a file. The
        zeropoint returned is whatever was provided (even if the value is not
        useful) or NaN. To load the passband and get the correct zeropoint, use
        :py:func:`source_synphot.passband.load_pbs`

    See Also
    --------
    :py:func:`astropy.table.Table.read`
    :py:func:`pysynphot.ObsBandpass`
    """
    if pbzp is None:
        pbzp = np.nan

    try:
        out = S.ObsBandpass(pb)
        pbzp = np.nan
    except ValueError as e:
        infile = os.path.join('passbands','pbzptmag.txt')
        pbzptfile = get_pkgfile(infile)
        pbzpt = at.Table.read(pbzptfile, format='ascii')
        ind = (pbzpt['obsmode'] == pb)
        nmatch_pb = len(pbzpt['passband'][ind])
        if nmatch_pb == 1:
            pbname = pb
            pb = pbzpt['passband'][ind][0]
            if not np.isnan(pbzpt['ABzpt'][ind][0]):
                pbzp = pbzpt['ABzpt'][ind][0]
            else:
                pbzp = np.nan
            pb = os.path.join('passbands', pb)
            try:
                #print('file to load: ',pb)
                pb = get_pkgfile(pb)
            except (OSError, IOError) as e:
                out = None
                pbzp = np.nan
                message = 'Passband {} not located in the passbands directory'.format(pb)
                pass
        elif nmatch_pb == 0:
            # we'll just see if this passband is a file and load it as such
            pbname = None
            message = 'Passband {} is not listed in pbzptmag file.'.format(pb)
            pass
        else:
            # pb is not unique
            out = None
            message = 'Passband {} is not uniquely listed in pbzptmag file.'.format(pb)

        if os.path.exists(pb):
            if pbname is None:
                pbname = os.path.basename(pb)
            # we either loaded the passband name from the lookup table or we didn't get a match
            pbdata = at.Table.read(pb, names=('wave','throughput'), format='ascii')
            out = S.ArrayBandpass(pbdata['wave'], pbdata['throughput'], waveunits='Angstrom', name=pbname)
        else:
            out = None
            message = 'Passband {} could not be loaded from any source.'.format(pb)

    if out is None:
        raise ValueError(message)

    try:
        pbzp = float(pbzp)
    except TypeError as e:
        message = 'Supplied zeropoint {} could not be interepreted as a float.'.format(zp)
        warnings.warn(message, RuntimeWarning)
        pbzp = np.nan
    return out, pbzp


def SVO_passband(pb, pbzp=None, List = False):
    """
    Read a SVO passband using https://github.com/hover2pi/svo_filters.


    Parameters
    ----------
    pb : str
        pysynphot obsmode or obsmode listed in `pbzptmag.txt`
    pbzp : float, optional
        AB magnitude zeropoint of the passband
    List : Bool, optional
        List all filters available through SVO

    Returns
    -------
    pb : :py:class:`pysynphot.ArrayBandpass` or :py:class:`pysynphot.obsbandpass.ObsModeBandpass`
        The passband data.
        Has ``dtype=[('wave', '<f8'), ('throughput', '<f8')]``
    pbzp : float
        passband AB zeropoint - potentially NaN if this was not supplied. If NaN
        this can be computed assuming an AB source - i.e. a source with a flux
        density of 3631 jy has magnitude = 0 in the bandpass.

    Notes
    -----
        Note that this is a straight read of a single passband from a file. The
        zeropoint returned is whatever was provided (even if the value is not
        useful) or NaN. To load the passband and get the correct zeropoint, use
        :py:func:`source_synphot.passband.load_pbs`

    See Also
    --------
    :py:func:`astropy.table.Table.read`
    :py:func:`pysynphot.ObsBandpass`
    """

    from svo_filters import svo
    from astropy import units as u

    if List:
        print(list(svo.filters()['Band']))

    if pbzp is None:
        pbzp = np.nan

    try:
        pbdata = svo.Filter(pb)
        wav = pbdata.wave.to(u.Angstrom).flatten().value
        wav, ind = np.unique(wav, return_index=True)
        out = S.ArrayBandpass(wav, pbdata.throughput.flatten()[ind], waveunits='Angstrom', name=pb)
    except (OSError,IOError) as e:
        message = 'No passband called {} in SVO'.format(pb)
        out = None

    if out is None:
        raise ValueError(message)

    return out, pbzp


def read_source(sourcespec):
    """
    Read a spectrum

    Parameters
    ----------
    sourcespec : str
        Source spectrum specification string. Acceptable options are:
         * BB<Temperature>
         * PL<Reference Wave Angstrom>_<PL Index>
         * Flat<AB magnitude>
         * ckmod<Temperature>_<logZ>_<logg>

    Returns
    -------
    source : :py:class:`pysynphot.spectrum.ArraySourceSpectrum`
        The spectrum data.
        Has ``dtype=[('wave', '<f8'), ('flux', '<f8')]``

    Raises
    ------
    ValueError
        If attempting to use this routine to load a file, or if source spectrum
        specification string is invalid

    Notes
    -----
       The source spectrum specification string parsing is basic. Strings are
       checked to see if they start with an acceptable prefix, and then split.
       The individual constituents are converted to float, and passed to
       pysynphot. There is no checking of the values, only that they can be
       properly typecast into float. Making sure the value is accepted is left
       to the user.

    """
    if os.path.exists(sourcespec):
        message = 'File spectrum parsing is complex and requires pre-processing. Use source_synphot.source routines'
        raise ValueError(message)
    else:
        # assume sourcespec is a string and parse it, trying to interpret as:
        # simple blackbody spectrum
        if sourcespec.startswith('BB'):
            temp = sourcespec.lstrip('BB')
            try:
                temp = float(temp)
            except (TypeError, ValueError) as e:
                message = 'Source temperature {} cannot be interpreted as a float'.format(sourcespec)
                raise ValueError(message)
            bb = S.Blackbody(temp)
            bb.convert('flam')
            spec = {'wave':bb.wave, 'flux':bb.flux}

        # power-law spectrum
        elif sourcespec.startswith('PL'):
            refwave, plindex = sourcespec.lstrip('PL').split('_')
            try:
                refwave = float(refwave)
            except (TypeError, ValueError) as e:
                message = 'Reference wavelength {} cannot be interpreted as a float'.format(sourcespec)
                raise ValueError(message)
            try:
                plindex = float(plindex)
            except (TypeError, ValueError) as e:
                message = 'Power law index {} cannot be interpreted as a float'.format(sourcespec)
                raise ValueError(message)
            pl = S.PowerLaw(refwave, plindex)
            pl.convert('flam')
            spec = {'wave':pl.wave, 'flux':pl.flux}

        # flat spectrum (in f_lam, not f_nu) normalized to some ABmag
        elif sourcespec.startswith('Flat'):
            abmag = sourcespec.replace('Flat','')
            try:
                abmag = float(abmag)
            except (TypeError, ValueError) as e:
                message = 'AB mag {} cannot be interpreted as a float'.format(sourcespec)
                raise ValueError(message)
            flat = S.FlatSpectrum(abmag, fluxunits='abmag')
            flat.convert('flam')
            spec = {'wave':flat.wave, 'flux':flat.flux}

        # a Castelli-Kurucz model
        elif sourcespec.startswith('ckmod'):
            teff, logZ, logg = sourcespec.replace('ckmod','').split('_')
            try:
                teff = float(teff)
            except (TypeError, ValueError) as e:
                message = 'Source temperature {} cannot be interpreted as a float'.format(sourcespec)
                raise ValueError(message)
            try:
                logZ = float(logZ)
            except (TypeError, ValueError) as e:
                message = 'Abundance {} cannot be interpreted as a float'.format(sourcespec)
                raise ValueError(message)
            try:
                logg = float(logg)
            except (TypeError, ValueError) as e:
                message = 'Surface gravity {} cannot be interpreted as a float'.format(sourcespec)
                raise ValueError(message)
            ckmod = S.Icat('ck04models',teff, logZ,logg)
            ckmod.convert('flam')
            spec = {'wave':ckmod.wave, 'flux':ckmod.flux}

        # else give up
        else:
            message = 'Source spectrum {} cannot be parsed as input file or pre-defined type (BB, PL, Flat, ckmod)'.format(sourcespec)
            raise ValueError(message)
    spec = S.ArraySpectrum(spec['wave'], spec['flux'], name=sourcespec)
    return spec
