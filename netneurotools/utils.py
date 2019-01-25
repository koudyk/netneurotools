# -*- coding: utf-8 -*-
"""
Miscellaneous functions of various utility
"""

import glob
import os
import pickle
from pkg_resources import resource_filename
import subprocess

import numpy as np
from sklearn.utils.validation import check_array


def globpath(*args):
    """"
    Joins `args` with :py:func:`os.path.join` and returns sorted glob output

    Parameters
    ----------
    args : str
        Paths / `glob`-compatible regex strings

    Returns
    -------
    files : list
        Sorted list of files
    """

    return sorted(glob.glob(os.path.join(*args)))


def get_triu(data, k=1):
    """
    Returns vectorized version of upper triangle from `data`

    Parameters
    ----------
    data : (N, N) array_like
        Input data
    k : int, optional
        Which diagonal to select from (where primary diagonal is 0). Default: 1

    Returns
    -------
    triu : (N * N-1 / 2) numpy.ndarray
        Upper triangle of `data`

    Examples
    --------
    >>> from netneurotools.utils import get_triu
    >>> X = np.array([[1, 0.5, 0.25], [0.5, 1, 0.33], [0.25, 0.33, 1]])
    >>> tri = get_triu(X)
    >>> tri
    array([0.5 , 0.25, 0.33])
    """

    return data[np.triu_indices(len(data), k=1)].copy()


def add_constant(data):
    """
    Adds a constant (i.e., intercept) term to `data`

    Parameters
    -----------
    data : (N, M) array_like
        Samples by features data array

    Returns
    -------
    data : (N, F) np.ndarray
        Where `F` is `M + 1`

    Examples
    --------
    >>> from netneurotools.utils import add_constant
    >>> A = np.zeros((5, 5))
    >>> Ac = add_constant(A)
    >>> Ac
    array([[0., 0., 0., 0., 0., 1.],
           [0., 0., 0., 0., 0., 1.],
           [0., 0., 0., 0., 0., 1.],
           [0., 0., 0., 0., 0., 1.],
           [0., 0., 0., 0., 0., 1.]])
    """

    data = check_array(data, ensure_2d=False)
    return np.column_stack([data, np.ones(len(data))])


def run(cmd, env=None, return_proc=False, quiet=False):
    """
    Runs `cmd` via shell subprocess with provided environment `env`

    Parameters
    ----------
    cmd : str
        Command to be run as single string
    env : dict, optional
        If provided, dictionary of key-value pairs to be added to base
        environment when running `cmd`. Default: None
    return_proc : bool, optional
        Whether to return CompletedProcess object. Default: false
    quiet : bool, optional
        Whether to suppress stdout/stderr from subprocess. Default: False

    Returns
    -------
    proc : subprocess.CompletedProcess
        Process output

    Raises
    ------
    subprocess.CalledProcessError
        If subprocess does not exit cleanly

    Examples
    --------
    >>> from netneurotools.utils import run
    >>> p = run('echo "hello world"', return_proc=True, quiet=True)
    >>> p.returncode
    0
    >>> p.stdout
    'hello world\\n'
    """

    merged_env = os.environ.copy()
    if env is not None:
        if not isinstance(env, dict):
            raise TypeError('Provided `env` must be a dictionary, not {}'
                            .format(type(env)))
        merged_env.update(env)

    opts = {}
    if quiet:
        opts = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    proc = subprocess.run(cmd, env=merged_env, shell=True, check=True,
                          universal_newlines=True, **opts)

    if return_proc:
        return proc


def check_fs_subjid(subject_id, subjects_dir=None):
    """
    Checks that `subject_id` exists in provided FreeSurfer `subjects_dir`

    Parameters
    ----------
    subject_id : str
        FreeSurfer subject ID
    subjects_dir : str, optional
        Path to FreeSurfer subject directory. If not set, will inherit from
        the environmental variable $SUBJECTS_DIR. Default: None

    Returns
    -------
    subject_id : str
        FreeSurfer subject ID, as provided
    subjects_dir : str
        Full filepath to `subjects_dir`

    Raises
    ------
    FileNotFoundError
    """

    # check inputs for subjects_dir and subject_id
    if subjects_dir is None or not os.path.isdir(subjects_dir):
        subjects_dir = os.environ['SUBJECTS_DIR']
    else:
        subjects_dir = os.path.abspath(subjects_dir)

    subjdir = os.path.join(subjects_dir, subject_id)
    if not os.path.isdir(subjdir):
        raise FileNotFoundError('Cannot find specified subject id {} in '
                                'provided subject directory {}.'
                                .format(subject_id, subjects_dir))

    return subject_id, subjects_dir


def get_cammoun2012_info(scale, surface=True):
    """
    Returns centroids / hemi assignment of parcels from Cammoun et al., 2012

    Centroids are defined on the spherical projection of the fsaverage cortical
    surface reconstruciton (FreeSurfer v6.0.1)

    Parameters
    ----------
    scale : {33, 60, 125, 250, 500}
        Scale of parcellation for which to get centroids / hemisphere
        assignments
    surface : bool, optional
        Whether to return coordinates from surface instead of volume
        reconstruction. Default: True

    Returns
    -------
    centroids : (N, 3) numpy.ndarray
        Centroids of parcels defined by Cammoun et al., 2012 parcellation
    hemiid : (N,) numpy.ndarray
        Hemisphere assignment of `centroids`, where 0 indicates left and 1
        indicates right hemisphere

    References
    ----------
    Cammoun, L., Gigandet, X., Meskaldji, D., Thiran, J. P., Sporns, O., Do, K.
    Q., Maeder, P., and Meuli, R., & Hagmann, P. (2012). Mapping the human
    connectome at multiple scales with diffusion spectrum MRI. Journal of
    Neuroscience Methods, 203(2), 386-397.

    Examples
    --------
    >>> from netneurotools.utils import get_cammoun2012_info
    >>> coords, hemiid = get_cammoun2012_info(scale=33)
    >>> coords.shape, hemiid.shape
    ((68, 3), (68,))

    ``hemiid`` is a vector of 0 and 1 denoting which ``coords`` are in the
    left / right hemisphere, respectively:

    >>> np.sum(hemiid == 0), np.sum(hemiid == 1)
    (34, 34)
    """

    pckl = resource_filename('netneurotools', 'data/cammoun.pckl')

    if not isinstance(scale, int):
        try:
            scale = int(scale)
        except ValueError:
            raise ValueError('Provided `scale` must be integer in [33, 60, '
                             '125, 250, 500], not {}'.format(scale))
    if scale not in [33, 60, 125, 250, 500]:
        raise ValueError('Provided `scale` must be integer in [33, 60, 125, '
                         '250, 500], not {}'.format(scale))

    with open(pckl, 'rb') as src:
        data = pickle.load(src)['cammoun{}'.format(str(scale))]

    return data['centroids'], data['hemiid']
