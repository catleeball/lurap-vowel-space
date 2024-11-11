from dataclasses import dataclass
from pathlib import Path

from praatio import textgrid
from praatio.data_classes.textgrid import Textgrid

import lib


@dataclass(frozen=True)
class TranscribedRecording:
    textgrid_path: Path
    textgrid_data: Textgrid
    audio_path: Path
    # audio_data:

    @staticmethod
    def from_paths(textgrid_path: Path, audio_path: Path) -> 'TranscribedRecording':
        if not textgrid_path.exists():
            raise IOError(lib.err_str(f'Textgrid file does not exist! {textgrid_path}'))

        textgrid.openTextgrid(str(textgrid_path), includeEmptyIntervals=False)
