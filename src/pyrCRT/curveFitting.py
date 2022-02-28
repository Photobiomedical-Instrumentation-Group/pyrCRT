"""
Functions related to curve fitting (pyrCRT.curveFitting)

This module implements the operations necessary to calculate the rCRT from the average
intensities array and the frame times array, namely fitting a polynomial and two
exponential curves on the data.
"""

from typing import List, Optional, Tuple, Union, overload
from warnings import filterwarnings

import numpy as np
from scipy.optimize import OptimizeWarning, curve_fit
from scipy.signal import find_peaks

# This is for catching OptimizeWarnig as if it were an exception
filterwarnings("error")

# Type aliases for commonly used types
# {{{
# Used just as a shorthand
Array = np.ndarray

# Tuples of two numpy arrays, typically an array of the timestamp for each frame and an
# array of average intensities within a given ROI
ArrayTuple = Tuple[Array, Array]

# Tuple of two lists, the first being the fitted parameters and the second their
# standard deviations
FitParametersTuple = Tuple[Array, Array]

Real = Union[float, int, np.float_, np.int_]

# This accounts for the fact that np.int_ doesn't inherit from int
Integer = Union[int, np.int_]
# }}}


def exponential(x: Array, a: Real, b: Real, c: Real) -> Array:
    # {{{
    """Exponential function of the form a*exp(b*x)+c. Refer to np.exp from the Numpy
    documentation for more information."""
    return a * np.exp(b * x) + c


# }}}


def polynomial(x: Array, *coefs: Real) -> Array:
    # {{{
    """Polynomial of the form coefs[0] + coefs[0]*x + coefs[1]*x**2 + ... Refer to the
    Numpy documentation for more information."""
    return np.polynomial.Polynomial(list(coefs))(x)


# }}}


def covToStdDev(cov: Array) -> Array:
    # {{{
    """Converts the covariance matrix returned by SciPy parameter optimization functions
    into an array with the standard deviation of each parameter. Refer to the
    documentation of scipy.optimize.curve_fit for more information"""

    return np.sqrt(np.diag(cov))


# }}}


def fitExponential(
    x: Array,
    y: Array,
    p0: Optional[List[Real]] = None,
) -> FitParametersTuple:
    # {{{
    # {{{
    """
    Fits an exponential function of the form a*exp(b*x)+c on the data, and returns a
    tuple of two arrays, one with the optimized parameters and another with their
    standard deviations. Refer to the documentation of scipy.optimize.curve_fit for more
    information.

    Parameters
    ----------
    x, y : np.ndarray
        Self-explanatory.
    p0 : list of 3 real numbers or None, default=None
        The initial guesses for each parameter, in order of a, b and c (see summary
        above). If None, will use p0=[0, 0, 0].

    Returns
    -------
    expParams
        The optimized parameters
    expStdDev
        The optimized parameters' respective standard deviations

    Raises
    ------
    RuntimeError
        If the curve fit failed.
    """
    # }}}

    if p0 is None:
        p0 = [1.0, -0.3, 0.0]

    try:
        expParams, expCov = curve_fit(
            f=exponential,
            xdata=x,
            ydata=y,
            p0=p0,
            bounds=([0.0, -np.inf, -np.inf], [np.inf, 0.0, np.inf]),
        )
        expStdDev = covToStdDev(expCov)
        return expParams, expStdDev
    except (RuntimeError, OptimizeWarning) as err:
        raise RuntimeError(f"Exponential fit failed with p0={p0}.") from err


# }}}


def fitPolynomial(
    x: Array,
    y: Array,
    p0: Optional[List[Real]] = None,
) -> FitParametersTuple:
    # {{{
    # {{{
    """
    Fits a polynomial function of the form coefs[0] + coefs[0]*x + coefs[1]*x**2 + ...
    on the data, and returns a tuple of two arrays, one with the optimized parameters
    and another with their standard deviations. Refer to the documentation of
    scipy.optimize.curve_fit for more information.

    Parameters
    ----------
    x, y : np.ndarray
        Self-explanatory.
    p0 : list of 3 real numbers or None, default=None
        The initial guesses for each parameter in increasing polynomial order (see
        summary above). Note that this determines the order of the polynomial, for
        example, a list of length 7 specifies a polynomial of sixth order.

    Returns
    -------
    polyParams
        The optimized parameters
    polyStdDev
        The optimized parameters' respective standard deviations

    Raises
    ------
    RuntimeError
        If the curve fit failed.
    """
    # }}}

    if p0 is None:
        p0 = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    try:
        polyParams, polyCov = curve_fit(
            f=polynomial,
            xdata=x,
            ydata=y,
            p0=p0,
            bounds=(-np.inf, np.inf),
        )
        polyStdDev = covToStdDev(polyCov)
        return polyParams, polyStdDev
    except (RuntimeError, OptimizeWarning) as err:
        raise RuntimeError(f"Polynomial fit failed with p0={p0}.") from err


# }}}


def diffExpPoly(
    x: Array, expParams: Array, polyParams: Array
) -> Array:
    # {{{
    """
    Evaluates the function |exponential(expParams) - polynomial(polyParams)| over x
    """
    return np.abs(exponential(x, *expParams) - polynomial(x, *polyParams))


# }}}


def fitRCRT(
    x: Array,
    y: Array,
    p0: Optional[List[Real]] = None,
    maxDiv: Optional[Union[List[int], int]] = None,
) -> Tuple[FitParametersTuple, int]:
    # {{{
    # {{{
    """
    Slices the x and y arrays from start to maxDiv and fit an exponential function on
    the data, and returns a tuple, the first element of which is the optimized
    parameters and their standard deviations, and the other is the maxDiv used. If
    maxDiv is a list of integers, it will try to fit on each value and return on the
    first successful fit.

    Parameters
    ----------
    x, y : np.ndarray
        Self-explanatory. The arrays over which the curve fit will be tried.
    p0 : list of real numbers, default=None
        The initial guesses for each parameter of the exponential function. Refer to the
        documentation of pyrCRT.curveFitting.exponential for more information.
    maxDiv : list of ints, or int, or None, default=None
        Maximum divergence index between the exponential and polynomial functions fitted
        on the entire data set. Refer to pyrCRT.curveFitting.findMaxDivergencePeaks for
        more information.

    Returns
    -------
    (rCRTParams, rCRTStdDev) : tuple of np.ndarrays
        The optimized parameters for the exponential function and their standard
        deviations.
    maxDiv : int
        The maximum divergence index used. This is useful if a list of maxDivs was
        or None was passed.

    Raises
    ------
    TypeError
        If maxDiv isn't a list, an int, or None.
    RuntimeError
        If the exponential fit failed on the single maxDiv passed, or if a list was
        passed and it failed on all the maxDivs in the list.
    """
    # }}}

    if p0 is None:
        p0 = [1.0, -0.3, 0.0]

    if maxDiv is not None:
        if isinstance(maxDiv, list):
            maxDivList = maxDiv

            for maxDivIndex in maxDivList:
                # Will try fitting with each maxDiv in the list, returning as soon as a
                # fit is successful
                try:
                    return fitRCRT(x, y, maxDiv=maxDivIndex, p0=p0)
                except RuntimeError:
                    pass

            raise RuntimeError(
                f"rCRT fit failed on all maxDivIndexes ({maxDivList})," " with p0={p0}."
            )
        if isinstance(maxDiv, int):
            maxDivIndex = maxDiv

            try:
                return (
                    fitExponential(x[: int(maxDivIndex)], y[: int(maxDivIndex)], p0=p0),
                    maxDivIndex,
                )
            except RuntimeError as err:
                raise RuntimeError(
                    f"rCRT fit failed on maxDivIndex={maxDivIndex} and p0={p0}"
                ) from err
        raise TypeError(
            f"Invalid type of {type(maxDiv)} for maxDiv. Valid types: int, list of "
            "ints or None. Please refer to the documentation for usage instructions."
        )

    # maxDiv wasn't passed as a kwarg, so this function will try to find the maxDiv
    # itself.
    maxDiv = findMaxDivergencePeaks(x, y)
    return fitRCRT(x, y, maxDiv=maxDiv)


# }}}


def rCRTFromParameters(rCRTTuple: FitParametersTuple) -> Tuple[np.float_, np.float_]:
    # {{{
    # {{{
    """
    Calculate the rCRT and its uncertainty with a 95% confidence interval from the rCRT
    exponential's optimized parameters.

    Parameters
    ----------
    rCRTTuple : tuple of np.ndarray
        A tuple with the fitted parameters and their standard deviations, respectively.
        See fitRCRT.

    Returns
    -------
    rCRT : np.float_
        The calculated rCRT, which is the negative inverse of the "b" parameter of the
        exponential function defined in this module (see exponential).

    rCRTUncertainty : np.float_
        The rCRT's uncertainty with a 95% confidence interval, calculated from the
        standard deviation of the "b" parameter of the exponential function.
    """
    # }}}

    rCRTParams, rCRTStdDev = rCRTTuple

    inverseRCRT: np.float_ = rCRTParams[1]
    inverseRCRTStdDev: np.float_ = rCRTStdDev[1]

    rCRT = -1 / inverseRCRT
    rCRTUncertainty = -2 * rCRT * (inverseRCRTStdDev / inverseRCRT)

    return (rCRT, rCRTUncertainty)


# }}}


def calculateRelativeUncertainty(rCRTTuple: FitParametersTuple) -> np.float_:
# {{{
    """
    Calculates the rCRT's relative uncertainty (with a 95% confidence interval) given a
    tuple with the optimized rCRT exponential parameters and their respective standard
    deviations.
    """

    rCRTParams, rCRTStdDev = rCRTTuple
    return 2 * abs(rCRTStdDev[1] / rCRTParams[1])
# }}}


@overload
def findMaxDivergencePeaks(x: Array, y: Array) -> List[int]:
    ...


@overload
def findMaxDivergencePeaks(
    x: Array, expTuple: FitParametersTuple, polyTuple: FitParametersTuple
) -> List[int]:
    ...


def findMaxDivergencePeaks(
    x: Array,
    *args: Union[Array, FitParametersTuple],
    **kwargs: Union[Array, FitParametersTuple],
) -> List[int]:
    # {{{
    # {{{
    """
    Find the indices of the peaks of maxDiv(expParams, polyParams) and returns them in
    descending order of diffExpPoly[i].
    Usage:
        findMaxDivergencePeaks(x, expParams=expParams, polyParams=polyParams)
    to directly compute the peaks, or
        findMaxDivergencePeaks(x, y)
    to fit the polynomial and exponential functions on the data, and then compute the
    peaks.

    Parameters
    ----------
    x : np.ndarray
        Tipically the array of frame timestamps.
    *args : np.ndarray
        Another array, y, that tipically is the array of average intensities for a
        channel.
    **kwargs : tuple of 2 arrays
        The parameters and standard deviations to the exponential and polynomial
        functions, if they have already been calculated.

    Returns
    -------
    maxIndexesSorted
        List of indexes of x where the peaks of maximum absolute divergence between the
        polynomial and exponential functions have been found, sorted by the peak
        magnitude.
    """
    # }}}

    if "expTuple" in kwargs and "polyTuple" in kwargs:
        expParams, polyParams = kwargs["expTuple"][0], kwargs["polyTuple"][0]
        assert isinstance(expParams, Array) and isinstance(polyParams, Array)

        diffArray = diffExpPoly(x, expParams, polyParams)
        maxIndexes = find_peaks(diffArray)[0]
        maxIndexes = [int(x) for x in maxIndexes]
        maxIndexesSorted = sorted(maxIndexes, key=lambda x: diffArray[x], reverse=True)
        return maxIndexesSorted

    if len(args) == 1 and isinstance(args[0], Array):
        y: Array = args[0]
        expTuple = fitExponential(x, y)
        polyTuple = fitPolynomial(x, y)
        return findMaxDivergencePeaks(x, expTuple=expTuple, polyTuple=polyTuple)

    raise ValueError(
        "Usage: findMaxDivergencePeaks(x: array, expTuple=expTuple,"
        "polyTuple=polyTuple) or findMaxDivergencePeaks(x: array, y: array)."
        "Please refer to the documentation for more information."
    )


# }}}
