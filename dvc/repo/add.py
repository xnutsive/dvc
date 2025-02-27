import logging
import os

import colorama

from . import locked
from ..exceptions import (
    RecursiveAddingWhileUsingFilename,
    OverlappingOutputPathsError,
)
from ..output.base import OutputDoesNotExistError
from ..progress import Tqdm
from ..repo.scm_context import scm_context
from ..stage import Stage
from ..utils import LARGE_DIR_SIZE

logger = logging.getLogger(__name__)


@locked
@scm_context
def add(repo, targets, recursive=False, no_commit=False, fname=None):
    if recursive and fname:
        raise RecursiveAddingWhileUsingFilename()

    if isinstance(targets, str):
        targets = [targets]

    stages_list = []
    num_targets = len(targets)
    with Tqdm(total=num_targets, desc="Add", unit="file", leave=True) as pbar:
        if num_targets == 1:
            # clear unneeded top-level progress bar for single target
            pbar.bar_format = "Adding..."
            pbar.refresh()
        for target in targets:
            sub_targets = _find_all_targets(repo, target, recursive)
            pbar.total += len(sub_targets) - 1

            if os.path.isdir(target) and len(sub_targets) > LARGE_DIR_SIZE:
                logger.warning(
                    "You are adding a large directory '{target}' recursively,"
                    " consider tracking it as a whole instead.\n"
                    "{purple}HINT:{nc} Remove the generated DVC-file and then"
                    " run `{cyan}dvc add {target}{nc}`".format(
                        purple=colorama.Fore.MAGENTA,
                        cyan=colorama.Fore.CYAN,
                        nc=colorama.Style.RESET_ALL,
                        target=target,
                    )
                )

            stages = _create_stages(repo, sub_targets, fname, pbar=pbar)

            try:
                repo.check_modified_graph(stages)
            except OverlappingOutputPathsError as exc:
                msg = (
                    "Cannot add '{out}', because it is overlapping with other "
                    "DVC tracked output: '{parent}'.\n"
                    "To include '{out}' in '{parent}', run "
                    "'dvc commit {parent_stage}'"
                ).format(
                    out=exc.overlapping_out.path_info,
                    parent=exc.parent.path_info,
                    parent_stage=exc.parent.stage.relpath,
                )
                raise OverlappingOutputPathsError(
                    exc.parent, exc.overlapping_out, msg
                )

            with Tqdm(
                total=len(stages),
                desc="Processing",
                unit="file",
                disable=len(stages) == 1,
            ) as pbar_stages:
                for stage in stages:
                    try:
                        stage.save()
                    except OutputDoesNotExistError:
                        pbar.n -= 1
                        raise

                    if not no_commit:
                        stage.commit()

                    stage.dump()
                    pbar_stages.update()

            stages_list += stages

        if num_targets == 1:  # restore bar format for stats
            pbar.bar_format = pbar.BAR_FMT_DEFAULT

    return stages_list


def _find_all_targets(repo, target, recursive):
    if os.path.isdir(target) and recursive:
        return [
            fname
            for fname in Tqdm(
                repo.tree.walk_files(target),
                desc="Searching " + target,
                bar_format=Tqdm.BAR_FMT_NOTOTAL,
                unit="file",
            )
            if not repo.is_dvc_internal(fname)
            if not Stage.is_stage_file(fname)
            if not repo.scm.belongs_to_scm(fname)
            if not repo.scm.is_tracked(fname)
        ]
    return [target]


def _create_stages(repo, targets, fname, pbar=None):
    stages = []

    for out in Tqdm(
        targets,
        desc="Creating DVC-files",
        disable=len(targets) < LARGE_DIR_SIZE,
        unit="file",
    ):
        stage = Stage.create(
            repo, outs=[out], accompany_outs=True, fname=fname
        )
        repo._reset()

        if not stage:
            if pbar is not None:
                pbar.total -= 1
            continue

        stages.append(stage)
        if pbar is not None:
            pbar.update_desc(out)

    return stages
