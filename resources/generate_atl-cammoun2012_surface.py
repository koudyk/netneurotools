# -*- coding: utf-8 -*-
"""
This script was used to generate the FreeSurfer-style surface annotation files
for the Cammoun et al., 2012 parcellation provided via `netneurotools`.

That is, the files returned with:

    >>> netneurotools.datasets.fetch_cammoun2012('surface')

were created with this script.
"""

import glob
import os
import os.path as op
import re
import shutil

from netneurotools import datasets, freesurfer
import nibabel as nib
import numpy as np
import pandas as pd


def combine_cammoun_500(lhannot, rhannot, subject_id, annot=None,
                        subjects_dir=None, use_cache=True, quiet=False):
    """
    Combines finest parcellation from Cammoun et al., 2012 for `subject_id`

    The parcellations from Cammoun et al., 2012 have five distinct scales; the
    highest resolution parcellation (scale 500) is split into three GCS files
    for historical FreeSurfer purposes. This is a bit annoying for calculating
    statistics, plotting, etc., so this function can be run once all the GCS
    files have been used to produce annotations files for `subject_id` (using
    :py:func:`netneurotools.freesurfer.apply_prob_atlas`). This function will
    combine the three .annot files that correspond to the highest resolution
    into a single .annot file for a given subject

    Parameters
    ----------
    {lh,rh}files : (3,) list of str
        List of filepaths to {left, right} hemisphere annotation files for
        Cammoun et al., 2012 scale500 parcellation
    subject_id : str
        FreeSurfer subject ID
    annot : str, optional
        Path to output annotation file to generate. If set to None, the name is
        created from the provided `?hannot` files. If provided as a relative
        path, it is assumed to stem from `subjects_dir`/`subject_id`. Default:
        None
    subjects_dir : str, optional
        Path to FreeSurfer subject directory. If not set, will inherit from
        the environmental variable `$SUBJECTS_DIR`. Default: None
    use_cache : bool, optional
        Whether to check for existence of relevant statistics file in directory
        specified by `{subjects_dir}/{subject_id}/stats' and use, if it exists.
        If False, will create a new stats file. Default: True
    quiet : bool, optional
        Whether to restrict status messages. Default: False

    Returns
    -------
    cammoun500 : list
        List of created annotation files
    """
    from netneurotools.utils import check_fs_subjid, run

    tolabel = 'mri_annotation2label --subject {subject_id} --hemi {hemi} ' \
              '--outdir {label_dir} --annotation {annot} --sd {subjects_dir}'
    toannot = 'mris_label2annot --sd {subjects_dir} --s {subject_id} ' \
              '--ldir {label_dir} --hemi {hemi} --annot-path {annot} ' \
              '--ctab {ctab} {label}'

    subject_id, subjects_dir = check_fs_subjid(subject_id, subjects_dir)

    created = []
    for hemi, annotfiles in zip(['lh', 'rh'], [lhannot, rhannot]):
        # generate output name based on hemisphere
        out = annot.format(hemi[0].upper())
        if not out.startswith(os.path.abspath(os.sep)):
            out = os.path.join(subjects_dir, subject_id, 'label', out)

        if os.path.isfile(out) and use_cache:
            created.append(out)
            continue

        # make directory to temporarily store labels
        label_dir = os.path.join(subjects_dir, subject_id,
                                 '{}.cammoun500.labels'.format(hemi))
        os.makedirs(label_dir, exist_ok=True)

        ctab = pd.DataFrame(columns=range(5))
        for fn in annotfiles:
            run(tolabel.format(subject_id=subject_id, hemi=hemi,
                               label_dir=label_dir, annot=fn,
                               subjects_dir=subjects_dir),
                quiet=quiet)

            # save ctab information from annotation file
            vtx, ct, names = nib.freesurfer.read_annot(fn)
            data = np.column_stack([[f.decode() for f in names], ct[:, :-1]])
            ctab = ctab.append(pd.DataFrame(data), ignore_index=True)

        # get rid of duplicate entries and add back in unknown/corpuscallosum
        ctab = ctab.drop_duplicates(subset=[0], keep=False)
        add_back = pd.DataFrame([['unknown', 25, 5, 25, 0],
                                 ['corpuscallosum', 120, 70, 50, 0]],
                                index=[0, 4])
        ctab = ctab.append(add_back).sort_index().reset_index(drop=True)
        # save ctab to temporary file for creation of annotation file
        ctab_fname = os.path.join(label_dir, '{}.cammoun500.ctab'.format(hemi))
        ctab.to_csv(ctab_fname, header=False, sep='\t', index=True)

        # get all labels EXCEPT FOR UNKNOWN to combine into annotation
        # unknown will be regenerated as all the unmapped vertices
        label = ' '.join(['--l {}'
                         .format(os.path.join(label_dir,
                                              '{hemi}.{lab}.label'
                                              .format(hemi=hemi, lab=lab)))
                          for lab in ctab.iloc[1:, 0]])
        # combine labels into annotation file
        run(toannot.format(subjects_dir=subjects_dir, subject_id=subject_id,
                           label_dir=label_dir, hemi=hemi, ctab=ctab_fname,
                           annot=out, label=label),
            quiet=quiet)
        created.append(out)

        # remove temporary label directory
        shutil.rmtree(label_dir)

    return created


FSUBJ = 'fsaverage'
ANNOT = 'atl-Cammoun2012_space-{}_res-{}_hemi-{}_deterministic.annot'
ANNOT = ANNOT.format(FSUBJ, '{}', '{}')

if __name__ == '__main__':
    #####
    # get the GCS files and apply them onto the fsaverage surface
    gcs = datasets.fetch_cammoun2012('gcs')
    for scale, gcsfiles in gcs.items():
        for fn in gcsfiles:
            hemi = re.search('hemi-([RL])', fn).group(1)
            scale = re.search('res-(.*)_hemi-', fn).group(1)
            out = op.join(op.dirname(fn), ANNOT.format(scale, hemi))
            freesurfer.apply_prob_atlas(FSUBJ, fn, hemi.lower() + 'h',
                                        ctab=fn.replace('.gcs', '.ctab'),
                                        annot=out)

    #####
    # get scale 500 parcellation files and combine
    dirname = op.dirname(fn)
    lh = sorted(glob.glob(op.join(dirname, ANNOT.format('500*', 'L'))))
    rh = sorted(glob.glob(op.join(dirname, ANNOT.format('500*', 'R'))))
    annot500 = op.join(dirname, ANNOT.format('500', '{}'))
    parc500 = combine_cammoun_500(lh, rh, FSUBJ, annot=annot500)
    for fn in lh + rh:
        os.remove(fn)

    #####
    # map all the WRONG .annot files to the correct ordering
    info = pd.read_csv(datasets.fetch_cammoun2012('volume')['info'])
    for scale in ['033', '060', '125', '250', '500']:
        annots = sorted(glob.glob(op.join(dirname, ANNOT.format(scale, '*'))))
        scinfo = info.query(f'scale == "scale{scale}" & structure == "cortex"')
        scinfo = scinfo.groupby('hemisphere')
        scinfo = [scinfo.get_group(m) for m in scinfo.groups]
        for annot, hemi in zip(annots, scinfo):
            labels, ctab, names = nib.freesurfer.read_annot(annot)
            ulab = np.unique(labels)
            idx = [names.index(n) for n in [b'unknown', b'corpuscallosum']]
            names = [n.decode() for n in names]
            ids = list(hemi['id'])
            targets = list(hemi['label'])
            inds = [names.index(x) for x in targets]
            for i in idx:
                inds = np.insert(inds, i, i)
            names = [n.encode() for n in np.array(names)[inds]]
            ctab = ctab[inds]
            src, tar = np.array(inds), np.arange(len(names))
            sidx = src.argsort()
            src, tar = src[sidx], tar[sidx]
            labels = tar[np.searchsorted(src, labels)]
            nib.freesurfer.write_annot(annot, labels, ctab, names)
