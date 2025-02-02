# -*- coding: utf-8 -*-

import math
from numbers import Real
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import pandas as pd
import scipy.signal as SS
from scipy.io import loadmat

from ...cfg import CFG, DEFAULTS
from ...utils.misc import add_docstring
from ...utils.utils_interval import get_optimal_covering
from ..base import DEFAULT_FIG_SIZE_PER_SEC, CPSCDataBase, DataBaseInfo

__all__ = [
    "CPSC2020",
    "compute_metrics",
]


_CPSC2020_INFO = DataBaseInfo(
    title="""
    The 3rd China Physiological Signal Challenge 2020:
    Searching for Premature Ventricular Contraction (PVC) and Supraventricular Premature Beat (SPB) from Long-term ECGs
    """,
    about="""
    1. training data consists of 10 single-lead ECG recordings collected from arrhythmia patients, each of the recording last for about 24 hours
    2. data and annotations are stored in v5 .mat files
    3. A02, A03, A08 are patient with atrial fibrillation
    4. sampling frequency = 400 Hz
    5. Detailed information:

        +-----+-----+-----------+-----------+-----------+-----------+---------------+
        | rec | ?AF | Length(h) | # N beats | # V beats | # S beats | # Total beats |
        +=====+=====+===========+===========+===========+===========+===============+
        | A01 | No  | 25.89     | 109,062   | 0         | 24        | 109,086       |
        +-----+-----+-----------+-----------+-----------+-----------+---------------+
        | A02 | Yes | 22.83     | 98,936    | 4,554     | 0         | 103,490       |
        +-----+-----+-----------+-----------+-----------+-----------+---------------+
        | A03 | Yes | 24.70     | 137,249   | 382       | 0         | 137,631       |
        +-----+-----+-----------+-----------+-----------+-----------+---------------+
        | A04 | No  | 24.51     | 77,812    | 19,024    | 3,466     | 100,302       |
        +-----+-----+-----------+-----------+-----------+-----------+---------------+
        | A05 | No  | 23.57     | 94,614    | 1         | 25        | 94,640        |
        +-----+-----+-----------+-----------+-----------+-----------+---------------+
        | A06 | No  | 24.59     | 77,621    | 0         | 6         | 77,627        |
        +-----+-----+-----------+-----------+-----------+-----------+---------------+
        | A07 | No  | 23.11     | 73,325    | 15,150    | 3,481     | 91,956        |
        +-----+-----+-----------+-----------+-----------+-----------+---------------+
        | A08 | Yes | 25.46     | 115,518   | 2,793     | 0         | 118,311       |
        +-----+-----+-----------+-----------+-----------+-----------+---------------+
        | A09 | No  | 25.84     | 88,229    | 2         | 1,462     | 89,693        |
        +-----+-----+-----------+-----------+-----------+-----------+---------------+
        | A10 | No  | 23.64     | 72,821    | 169       | 9,071     | 82,061        |
        +-----+-----+-----------+-----------+-----------+-----------+---------------+

    6. challenging factors for accurate detection of SPB and PVC:
       amplitude variation; morphological variation; noise
    7. Challenge official website [1]_.
    """,
    note="""
    1. the records can roughly be classified into 4 groups:

        +----+--------------------+
        | N  | A01, A03, A05, A06 |
        +----+--------------------+
        | V  | A02, A08           |
        +----+--------------------+
        | S  | A09, A10           |
        +----+--------------------+
        | VS | A04, A07           |
        +----+--------------------+

    2. as premature beats and atrial fibrillation can co-exists
       (via the following code, and data from CINC2020),
       the situation becomes more complicated.

       .. code-block:: python

            >>> from utils.scoring_aux_data import dx_cooccurrence_all
            >>> dx_cooccurrence_all.loc["AF", ["PAC","PVC","SVPB","VPB"]]
            PAC     20
            PVC     19
            SVPB     4
            VPB     20
            Name: AF, dtype: int64

       this could also be seen from this dataset, via the following code as an example:

       .. code-block:: python

            >>> from data_reader import CPSC2020Reader as CR
            >>> db_dir = "/media/cfs/wenhao71/data/CPSC2020/TrainingSet/"
            >>> dr = CR(db_dir)
            >>> rec = dr.all_records[1]
            >>> dr.plot(rec, sampfrom=0, sampto=4000, ticks_granularity=2)

    3. PVC and SPB can also co-exist, as illustrated via the following code (from CINC2020):

       .. code-block:: python

            >>> from utils.scoring_aux_data import dx_cooccurrence_all
            >>> dx_cooccurrence_all.loc[["PVC","VPB"], ["PAC","SVPB",]]
            PAC SVPB
            PVC 14 1
            VPB 27 0
            and also from the following code:
            >>> for rec in dr.all_records:
            >>>     ann = dr.load_ann(rec)
            >>>     spb = ann["SPB_indices"]
            >>>     pvc = ann["PVC_indices"]
            >>>     if len(np.diff(spb)) > 0:
            >>>         print(f"{rec}: min dist among SPB = {np.min(np.diff(spb))}")
            >>>     if len(np.diff(pvc)) > 0:
            >>>         print(f"{rec}: min dist among PVC = {np.min(np.diff(pvc))}")
            >>>     diff = [s-p for s,p in product(spb, pvc)]
            >>>     if len(diff) > 0:
            >>>         print(f"{rec}: min dist between SPB and PVC = {np.min(np.abs(diff))}")
            A01: min dist among SPB = 630
            A02: min dist among SPB = 696
            A02: min dist among PVC = 87
            A02: min dist between SPB and PVC = 562
            A03: min dist among SPB = 7044
            A03: min dist among PVC = 151
            A03: min dist between SPB and PVC = 3750
            A04: min dist among SPB = 175
            A04: min dist among PVC = 156
            A04: min dist between SPB and PVC = 178
            A05: min dist among SPB = 182
            A05: min dist between SPB and PVC = 22320
            A06: min dist among SPB = 455158
            A07: min dist among SPB = 603
            A07: min dist among PVC = 153
            A07: min dist between SPB and PVC = 257
            A08: min dist among SPB = 2903029
            A08: min dist among PVC = 106
            A08: min dist between SPB and PVC = 350
            A09: min dist among SPB = 180
            A09: min dist among PVC = 7719290
            A09: min dist between SPB and PVC = 1271
            A10: min dist among SPB = 148
            A10: min dist among PVC = 708
            A10: min dist between SPB and PVC = 177

    """,
    usage=[
        "ECG arrhythmia (PVC, SPB) detection",
    ],
    issues="""
    1. currently, using `xqrs` as qrs detector,
       a lot more (more than 1000) rpeaks would be detected for A02, A07, A08,
       which might be caused by motion artefacts (or AF?);
       a lot less (more than 1000) rpeaks would be detected for A04.
       numeric details are as follows:

            +-----+-----+-----------------+---------------+
            | rec | ?AF | # beats by xqrs | # Total beats |
            +=====+=====+=================+===============+
            | A01 | No  | 109,502         | 109,086       |
            +-----+-----+-----------------+---------------+
            | A02 | Yes | 119,562         | 103,490       |
            +-----+-----+-----------------+---------------+
            | A03 | Yes | 135,912         | 137,631       |
            +-----+-----+-----------------+---------------+
            | A04 | No  | 92,746          | 100,302       |
            +-----+-----+-----------------+---------------+
            | A05 | No  | 94,674          | 94,640        |
            +-----+-----+-----------------+---------------+
            | A06 | No  | 77,955          | 77,627        |
            +-----+-----+-----------------+---------------+
            | A07 | No  | 98,390          | 91,956        |
            +-----+-----+-----------------+---------------+
            | A08 | Yes | 126,908         | 118,311       |
            +-----+-----+-----------------+---------------+
            | A09 | No  | 89,972          | 89,693        |
            +-----+-----+-----------------+---------------+
            | A10 | No  | 83,509          | 82,061        |
            +-----+-----+-----------------+---------------+

    2. (fixed by an official update) A04 has duplicate "PVC_indices" (13534856,27147621,35141190 all appear twice):
       before correction of `load_ann`

       .. code-block:: python

            >>> from collections import Counter
            >>> db_dir = "/mnt/wenhao71/data/CPSC2020/TrainingSet/"
            >>> data_gen = CPSC2020Reader(db_dir=db_dir,working_dir=db_dir)
            >>> rec = 4
            >>> ann = data_gen.load_ann(rec)
            >>> Counter(ann["PVC_indices"]).most_common()[:4]
            [(13534856, 2), (27147621, 2), (35141190, 2), (848, 1)]

    3. when extracting morphological features using augmented rpeaks for A04,

       .. code-block:: python

            RuntimeWarning: invalid value encountered in double_scalars

       would raise for

       .. math::

            R\\_value = (R\\_value - y_min) / (y\\_max - y\\_min)

       and for

       .. math::

            y\\_values[n] = (y\\_values[n] - y\\_min) / (y\\_max - y\\_min).

       This is caused by the 13882273-th sample, which is contained in "PVC_indices",
       however, whether it is a PVC beat, or just motion artefact, is in doubt!

    """,
    references=[
        "http://2020.icbeb.org/CSPC2020",
    ],
    doi="10.1166/jmihi.2020.3289",
)


@add_docstring(_CPSC2020_INFO.format_database_docstring(), mode="prepend")
class CPSC2020(CPSCDataBase):
    """
    Parameters
    ----------
    db_dir : str or pathlib.Path, optional
        Storage path of the database.
        If not specified, data will be fetched from Physionet.
    working_dir : str, optional
        Working directory, to store intermediate files and log files.
    verbose : int, default 1
        Level of logging verbosity.
    kwargs : dict, optional
        Auxilliary key word arguments

    """

    def __init__(
        self,
        db_dir: Optional[Union[str, Path]] = None,
        working_dir: Optional[Union[str, Path]] = None,
        verbose: int = 1,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            db_name="cpsc2020",
            db_dir=db_dir,
            working_dir=working_dir,
            verbose=verbose,
            **kwargs,
        )

        self.fs = 400
        self.spacing = 1000 / self.fs
        self.rec_ext = "mat"
        self.ann_ext = "mat"

        self._df_records = None
        self._all_records = None
        self._all_annotations = None
        self._ls_rec()

        self.subgroups = CFG(
            {
                "N": [
                    "A01",
                    "A03",
                    "A05",
                    "A06",
                ],
                "V": ["A02", "A08"],
                "S": ["A09", "A10"],
                "VS": ["A04", "A07"],
            }
        )

        self.palette = {
            "spb": "yellow",
            "pvc": "red",
        }

    def _ls_rec(self) -> None:
        """Find all records in the database directory
        and store them (path, metadata, etc.) in some private attributes.
        """
        self._df_records = pd.DataFrame()
        n_records = 10
        all_records = [f"A{i:02d}" for i in range(1, 1 + n_records)]
        self._df_records["path"] = [path for path in self.db_dir.rglob(f"*.{self.rec_ext}") if path.stem in all_records]
        self._df_records["record"] = self._df_records["path"].apply(lambda x: x.stem)
        self._df_records.set_index("record", inplace=True)

        all_annotations = [f"R{i:02d}" for i in range(1, 1 + n_records)]
        df_ann = pd.DataFrame()
        df_ann["ann_path"] = [path for path in self.db_dir.rglob(f"*.{self.ann_ext}") if path.stem in all_annotations]
        df_ann["record"] = df_ann["ann_path"].apply(lambda x: x.stem.replace("R", "A"))
        df_ann.set_index("record", inplace=True)
        # take the intersection by the index of `df_ann` and `self._df_records`
        self._df_records = self._df_records.join(df_ann, how="inner")

        if len(self._df_records) > 0:
            if self._subsample is not None:
                size = min(
                    len(self._df_records),
                    max(1, int(round(self._subsample * len(self._df_records)))),
                )
                self._df_records = self._df_records.sample(n=size, random_state=DEFAULTS.SEED, replace=False)

        self._all_records = self._df_records.index.tolist()
        self._all_annotations = self._df_records["ann_path"].apply(lambda x: x.stem).tolist()

    @property
    def all_annotations(self):
        return self._all_annotations

    @property
    def all_references(self):
        return self._all_annotations

    def get_subject_id(self, rec: Union[int, str]) -> int:
        """Attach a unique subject ID to the record.

        Parameters
        ----------
        rec : str or int
            Record name or index of the record in :attr:`all_records`.

        Returns
        -------
        pid : int
            the ``subject_id`` corr. to `rec`.

        """
        if isinstance(rec, int):
            rec = self[rec]
        return int(f"20{int(rec[1:]):08d}")

    def get_absolute_path(
        self,
        rec: Union[str, int],
        extension: Optional[str] = None,
        ann: bool = False,
    ) -> Path:
        """Get the absolute path of the record `rec`.

        Parameters
        ----------
        rec : str or int
            Record name or index of the record in :attr:`all_records`.
        extension : str, optional
            Extension of the file.
        ann : bool, default False
            Whether to get the annotation file path or not.

        Returns
        -------
        abs_path : pathlib.Path
            Absolute path of the file.

        """
        if isinstance(rec, int):
            rec = self[rec]
        if extension is not None and not extension.startswith("."):
            extension = f".{extension}"
        col = "ann_path" if ann else "path"
        abs_path = self._df_records.loc[rec, col].with_suffix(extension)
        return abs_path

    def load_data(
        self,
        rec: Union[int, str],
        sampfrom: Optional[int] = None,
        sampto: Optional[int] = None,
        data_format: str = "channel_first",
        units: str = "mV",
        fs: Optional[Real] = None,
        return_fs: bool = False,
    ) -> Union[np.ndarray, Tuple[np.ndarray, Real]]:
        """Load the ECG data of the record `rec`.

        Parameters
        ----------
        rec : str or int
            Record name or index of the record in :attr:`all_records`.
        sampfrom : int, optional
            Start index of the data to be loaded.
        sampto : int, optional
            End index of the data to be loaded.
        data_format : str, default "channel_first"
            Format of the ECG data,
            "channel_last" (alias "lead_last"), or
            "channel_first" (alias "lead_first"), or
            "flat" (alias "plain").
        units : str or None, default "mV"
            Units of the output signal,
            can also be "μV" (with aliases "uV", "muV").
        fs : numbers.Real, optional
            Frequency of the output signal.
            if not None, the loaded data will be resampled to this frequency;
            if None, the loaded data will be returned as is.
        return_fs : bool, default False
            Whether to return the sampling frequency of the output signal.

        Returns
        -------
        data : numpy.ndarray
            The loaded ECG data.
        data_fs : numbers.Real, optional
            Sampling frequency of the output signal.
            Returned if `return_fs` is True.

        """
        rec_fp = self.get_absolute_path(rec, self.rec_ext)
        data = loadmat(str(rec_fp))["ecg"].astype(DEFAULTS.DTYPE.NP)
        sf, st = (sampfrom or 0), (sampto or len(data))
        data = data[sf:st]
        if fs is not None and fs != self.fs:
            data = SS.resample_poly(data, fs, self.fs, axis=0).astype(data.dtype)
            data_fs = fs
        else:
            data_fs = self.fs
        if data_format.lower() in ["channel_first", "lead_first"]:
            data = data.T
        elif data_format.lower() in ["flat", "plain"]:
            data = data.flatten()
        elif data_format.lower() not in ["channel_last", "lead_last"]:
            raise ValueError(f"Invalid `data_format`: {data_format}")
        if units.lower() in ["uv", "muv", "μv"]:
            data = (1000 * data).astype(int)
        elif units.lower() != "mv":
            raise ValueError(f"Invalid `units`: {units}")

        if return_fs:
            return data, data_fs
        return data

    def load_ann(
        self,
        rec: Union[int, str],
        sampfrom: Optional[int] = None,
        sampto: Optional[int] = None,
    ) -> Dict[str, np.ndarray]:
        """Load the annotations of the record `rec`.

        Parameters
        ----------
        rec : str or int
            Record name or index of the record in :attr:`all_records`.
        sampfrom : int, optional
            Start index of the data to be loaded.
        sampto : int, optional
            End index of the data to be loaded.

        Returns
        -------
        ann : dict
            Annotation dictionary with items (:class:`~numpy.ndarray`)
            "SPB_indices" and "PVC_indices",
            which record the indices of SPBs and PVCs.

        """
        ann_fp = self.get_absolute_path(rec, self.ann_ext, ann=True)
        ann = loadmat(str(ann_fp))["ref"]
        sf, st = (sampfrom or 0), (sampto or np.inf)
        spb_indices = ann["S_ref"][0, 0].flatten().astype(int)
        # drop duplicates
        spb_indices = np.array(sorted(list(set(spb_indices))), dtype=int)
        spb_indices = spb_indices[np.where((spb_indices >= sf) & (spb_indices < st))[0]]
        pvc_indices = ann["V_ref"][0, 0].flatten().astype(int)
        # drop duplicates
        pvc_indices = np.array(sorted(list(set(pvc_indices))), dtype=int)
        pvc_indices = pvc_indices[np.where((pvc_indices >= sf) & (pvc_indices < st))[0]]
        ann = {
            "SPB_indices": spb_indices,
            "PVC_indices": pvc_indices,
        }
        return ann

    def train_test_split_rec(self, test_rec_num: int = 2) -> Dict[str, List[str]]:
        """Split the records into train set and test (val) set.

        Parameters
        ----------
        test_rec_num : int, default 2
            Number of records for the test (val) set.

        Returns
        -------
        split_res : dict
            Split result dictionary,
            with items "train", "test",
            both of which are lists of record names.

        """
        if test_rec_num == 1:
            test_records = DEFAULTS.RNG_sample(self.subgroups.VS, 1).tolist()
        elif test_rec_num == 2:
            test_records = (
                DEFAULTS.RNG_sample(self.subgroups.VS, 1).tolist() + DEFAULTS.RNG_sample(self.subgroups.N, 1).tolist()
            )
        elif test_rec_num == 3:
            test_records = (
                DEFAULTS.RNG_sample(self.subgroups.VS, 1).tolist() + DEFAULTS.RNG_sample(self.subgroups.N, 2).tolist()
            )
        elif test_rec_num == 4:
            test_records = []
            for k in self.subgroups.keys():
                test_records += DEFAULTS.RNG_sample(self.subgroups[k], 1).tolist()
        elif 5 <= test_rec_num <= 10:
            raise ValueError("test data ratio too high")
        else:
            raise ValueError("Invalid `test_rec_num`")
        train_records = [r for r in self.all_records if r not in test_records]

        split_res = CFG(
            {
                "train": train_records,
                "test": test_records,
            }
        )

        return split_res

    def locate_premature_beats(
        self,
        rec: Union[int, str],
        premature_type: Optional[str] = None,
        window: Real = 10,
        sampfrom: Optional[int] = None,
        sampto: Optional[int] = None,
    ) -> List[List[int]]:
        """Locate the sample indices of premature beats in a record.

        The locations are in the form of a list of lists, and
        each list contains the interval of sample indices of premature beats.

        Parameters
        ----------
        rec : str or int
            Record name or index of the record in :attr:`all_records`.
        premature_type : str, optional
            Premature beat type, can be one of "SPB", "PVC".
            If not specified, both SPBs and PVCs will be located.
        window : numbers.Real, default 10
            Window length of each premature beat,
            with units in seconds.
        sampfrom : int, optional
            Start index of the premature beats to locate.
        sampto : int, optional
            End index of the premature beats to locate.

        Returns
        -------
        premature_intervals : list
            List of intervals of premature beats.

        """
        ann = self.load_ann(rec)
        if premature_type:
            premature_inds = ann[f"{premature_type.upper()}_indices"]
        else:
            premature_inds = np.append(ann["SPB_indices"], ann["PVC_indices"])
            premature_inds = np.sort(premature_inds)
        try:  # premature_inds empty?
            sf, st = (sampfrom or 0), (sampto or premature_inds[-1] + 1)
        except Exception:
            premature_intervals = []
            return premature_intervals
        premature_inds = premature_inds[(sf < premature_inds) & (premature_inds < st)]
        tot_interval = [sf, st]
        windown_len = int(window * self.fs)
        premature_intervals = get_optimal_covering(
            total_interval=tot_interval,
            to_cover=premature_inds,
            min_len=windown_len,
            isolated_point_dist_threshold=windown_len // 2,
            split_threshold=windown_len,
            traceback=False,
        )
        return premature_intervals

    def plot(
        self,
        rec: Union[int, str],
        data: Optional[np.ndarray] = None,
        ann: Optional[Dict[str, np.ndarray]] = None,
        ticks_granularity: int = 0,
        sampfrom: Optional[int] = None,
        sampto: Optional[int] = None,
        rpeak_inds: Optional[Union[Sequence[int], np.ndarray]] = None,
    ) -> None:
        """Plot the ECG signal of a record.

        Parameters
        ----------
        rec : str or int
            Record name or index of the record in :attr:`all_records`.
        data : numpy.ndarray, optional
            ECG signal to plot.
            If given, data of `rec` will not be used.
            This is useful when plotting filtered data.
        ann : dict, optional
            Annotations for `data`, covering those from annotation files,
            with items "SPB_indices", "PVC_indices",
            each of which is a :class:`~numpy.ndarray`.
            Ignored if `data` is None.
        ticks_granularity : int, default 0
            Granularity to plot axis ticks, the higher the more ticks.
            0 (no ticks) --> 1 (major ticks) --> 2 (major + minor ticks)
        sampfrom : int, optional
            Start index of the data to plot.
        sampto : int, optional
            End index of the data to plot.
        rpeak_inds : array_like, optional
            Indices of R peaks.
            If `data` is None,
            then indices should be the absolute indices in the record.

        """
        if isinstance(rec, int):
            rec = self[rec]
        if "plt" not in dir():
            import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        patches = {}

        if data is None:
            _data = self.load_data(rec, units="μV", sampfrom=sampfrom, sampto=sampto, data_format="flat")
        else:
            units = self._auto_infer_units(data)
            if units == "mV":
                _data = data * 1000
            elif units == "μV":
                _data = data.copy()

        if ann is None or data is None:
            ann = self.load_ann(rec, sampfrom=sampfrom, sampto=sampto)
        sf, st = (sampfrom or 0), (sampto or len(_data))
        spb_indices = ann["SPB_indices"]
        pvc_indices = ann["PVC_indices"]
        spb_indices = spb_indices - sf
        pvc_indices = pvc_indices - sf

        if rpeak_inds is not None:
            if data is not None:
                rpeak_secs = np.array(rpeak_inds) / self.fs
            else:
                rpeak_secs = np.array(rpeak_inds)
                rpeak_secs = rpeak_secs[np.where((rpeak_secs >= sf) & (rpeak_secs < st))[0]]
                rpeak_secs = (rpeak_secs - sf) / self.fs

        line_len = self.fs * 25  # 25 seconds
        nb_lines = math.ceil(len(_data) / line_len)

        bias_thr = 0.15
        winL = 0.06
        winR = 0.08

        for idx in range(nb_lines):
            seg = _data[idx * line_len : (idx + 1) * line_len]
            secs = (np.arange(len(seg)) + idx * line_len) / self.fs
            fig_sz_w = int(round(DEFAULT_FIG_SIZE_PER_SEC * len(seg) / self.fs))
            y_range = np.max(np.abs(seg)) + 100
            fig_sz_h = 6 * y_range / 1500
            fig, ax = plt.subplots(figsize=(fig_sz_w, fig_sz_h))
            ax.plot(
                secs,
                seg,
                color="black",
                linewidth="2.0",
            )
            ax.axhline(y=0, linestyle="-", linewidth="1.0", color="red")
            if ticks_granularity >= 1:
                ax.xaxis.set_major_locator(plt.MultipleLocator(0.2))
                ax.yaxis.set_major_locator(plt.MultipleLocator(500))
                ax.grid(which="major", linestyle="-", linewidth="0.5", color="red")
            if ticks_granularity >= 2:
                ax.xaxis.set_minor_locator(plt.MultipleLocator(0.04))
                ax.yaxis.set_minor_locator(plt.MultipleLocator(100))
                ax.grid(which="minor", linestyle=":", linewidth="0.5", color="black")
            seg_spb = np.where((spb_indices >= idx * line_len) & (spb_indices < (idx + 1) * line_len))[0]
            # print(f"spb_indices = {spb_indices}, seg_spb = {seg_spb}")
            if len(seg_spb) > 0:
                seg_spb = spb_indices[seg_spb] / self.fs
                patches["SPB"] = mpatches.Patch(color=self.palette["spb"], label="SPB")
            seg_pvc = np.where((pvc_indices >= idx * line_len) & (pvc_indices < (idx + 1) * line_len))[0]
            # print(f"pvc_indices = {pvc_indices}, seg_pvc = {seg_pvc}")
            if len(seg_pvc) > 0:
                seg_pvc = pvc_indices[seg_pvc] / self.fs
                patches["PVC"] = mpatches.Patch(color=self.palette["pvc"], label="PVC")
            for t in seg_spb:
                ax.axvspan(
                    max(secs[0], t - bias_thr),
                    min(secs[-1], t + bias_thr),
                    color=self.palette["spb"],
                    alpha=0.3,
                )
                ax.axvspan(
                    max(secs[0], t - winL),
                    min(secs[-1], t + winR),
                    color=self.palette["spb"],
                    alpha=0.9,
                )
            for t in seg_pvc:
                ax.axvspan(
                    max(secs[0], t - bias_thr),
                    min(secs[-1], t + bias_thr),
                    color=self.palette["pvc"],
                    alpha=0.3,
                )
                ax.axvspan(
                    max(secs[0], t - winL),
                    min(secs[-1], t + winR),
                    color=self.palette["pvc"],
                    alpha=0.9,
                )
            if len(patches) > 0:
                ax.legend(
                    handles=[v for _, v in patches.items()],
                    loc="lower left",
                    prop={"size": 16},
                )
            if rpeak_inds is not None:
                seg_rpeak_secs = rpeak_secs[np.where((rpeak_secs >= secs[0]) & (rpeak_secs < secs[-1]))[0]]
                for r in seg_rpeak_secs:
                    ax.axvspan(r - 0.01, r + 0.01, color="green", alpha=0.7)
            ax.set_xlim(secs[0], secs[-1])
            ax.set_ylim(-y_range, y_range)
            ax.set_xlabel("Time [s]")
            ax.set_ylabel("Voltage [μV]")
            plt.show()

    @property
    def url(self) -> str:
        return "https://opensz.oss-cn-beijing.aliyuncs.com/ICBEB2020/file/TrainingSet.zip"

    @property
    def database_info(self) -> DataBaseInfo:
        return _CPSC2020_INFO

    @property
    def webpage(self) -> str:
        return "http://2020.icbeb.org/CSPC2020"


def compute_metrics(
    sbp_true: List[np.ndarray],
    pvc_true: List[np.ndarray],
    sbp_pred: List[np.ndarray],
    pvc_pred: List[np.ndarray],
    verbose: int = 0,
) -> Union[Tuple[int], dict]:
    """Score Function for all (test) records.

    Parameters
    ----------
    sbp_true, pvc_true, sbp_pred, pvc_pred : List[numpy.ndarray]
        List of numpy arrays of true and predicted SBP and PVC indices.
    verbose : int
        Verbosity level.

    Returns
    -------
    retval : tuple or dict
        Tuple of (negative) scores for each ectopic beat type (SBP, PVC),
        or dict of more scoring details, including

            - total_loss: sum of loss of each ectopic beat type (PVC and SPB)
            - true_positive: number of true positives of each ectopic beat type
            - false_positive: number of false positives of each ectopic beat type
            - false_negative: number of false negatives of each ectopic beat type

    """
    BaseCfg = CFG()
    BaseCfg.fs = 400
    BaseCfg.bias_thr = 0.15 * BaseCfg.fs
    s_score = np.zeros(
        [
            len(sbp_true),
        ],
        dtype=int,
    )
    v_score = np.zeros(
        [
            len(sbp_true),
        ],
        dtype=int,
    )
    # Scoring
    for i, (s_ref, v_ref, s_pos, v_pos) in enumerate(zip(sbp_true, pvc_true, sbp_pred, pvc_pred)):
        s_tp = 0
        s_fp = 0
        s_fn = 0
        v_tp = 0
        v_fp = 0
        v_fn = 0
        # SBP
        if s_ref.size == 0:
            s_fp = len(s_pos)
        else:
            for m, ans in enumerate(s_ref):
                s_pos_cand = np.where(abs(s_pos - ans) <= BaseCfg.bias_thr)[0]
                if s_pos_cand.size == 0:
                    s_fn += 1
                else:
                    s_tp += 1
                    s_fp += len(s_pos_cand) - 1
        # PVC
        if v_ref.size == 0:
            v_fp = len(v_pos)
        else:
            for m, ans in enumerate(v_ref):
                v_pos_cand = np.where(abs(v_pos - ans) <= BaseCfg.bias_thr)[0]
                if v_pos_cand.size == 0:
                    v_fn += 1
                else:
                    v_tp += 1
                    v_fp += len(v_pos_cand) - 1
        # calculate the score
        s_score[i] = s_fp * (-1) + s_fn * (-5)
        v_score[i] = v_fp * (-1) + v_fn * (-5)

        if verbose >= 1:
            print(f"for the {i}-th record")
            print(f"s_tp = {s_tp}, s_fp = {s_fp}, s_fn = {s_fn}")
            print(f"v_tp = {v_tp}, v_fp = {v_fp}, s_fn = {v_fn}")
            print(f"s_score[{i}] = {s_score[i]}, v_score[{i}] = {v_score[i]}")

    Score1 = np.sum(s_score)
    Score2 = np.sum(v_score)

    if verbose >= 1:
        retval = CFG(
            total_loss=-(Score1 + Score2),
            class_loss={"S": -Score1, "V": -Score2},
            true_positive={"S": s_tp, "V": v_tp},
            false_positive={"S": s_fp, "V": v_fp},
            false_negative={"S": s_fn, "V": v_fn},
        )
    else:
        retval = Score1, Score2

    return retval
