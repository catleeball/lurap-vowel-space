import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from praatio import textgrid
from praatio.data_classes.textgrid import Textgrid
from termcolor import colored


@dataclass(frozen=True)
class TranscribedRecording:
    textgrid_path: Path
    textgrid_data: Textgrid
    audio_path: Path | None

    # TODO: Put audio data into this model
    # audio_data: Path | None

    @staticmethod
    def from_path(textgrid_path: Path, audio_path: Path | None = None) -> 'TranscribedRecording':
        if not textgrid_path.exists():
            IOError(err_str(f'File does not exsit at {textgrid_path}'))

        textgrid_data = textgrid.openTextgrid(str(textgrid_path), includeEmptyIntervals=False)

        return TranscribedRecording(
            textgrid_path=textgrid_path,
            textgrid_data=textgrid_data,
            audio_path=audio_path,
            # audio_data=
        )


# ----- File system utilities -----
def get_textgrid_file_paths(textgrid_path: Path | None, textgrid_dir_path: Path | None) -> list[Path]:
    """Get textgrid files from CLI arguments"""
    paths: list[Path] = []
    for path in (textgrid_path, textgrid_dir_path):
        if path and path.exists():
            if path.is_dir():
                paths.extend(get_textgrid_files_from_directory(path))
            else:
                # Don't assert path.is_file() in case this is a symlink we need to follow
                paths.append(path)
        if path and not path.exists():
            warn(f'Path {str(path)} does not exist.')
    return paths


def get_textgrid_files_from_directory(path: Path) -> list[Path]:
    """Get files that end in .textgrid from the given directory path. Don't recurse the entire directory structure."""
    files: list[Path] = [i for i in path.iterdir() if i.is_file()]
    files = [i for i in files if i.name.lower().endswith('textgrid')]
    if not files:
        warn(f'Directory {str(path)} contains no textgrid files.')
    return files


# ----- Text formatting utilities -----
def err_str(message: str) -> str:
    return colored(f'ERROR: {message}', color='red')


def warn_str(message: str) -> str:
    return colored(f'WARNING: {message}', color='yellow')


def warn(message: str):
    print(warn_str(message), file=sys.stderr)


def err(message: str):
    print(err_str(message), file=sys.stderr)


def emoji_bool(b: bool) -> str:
    """For human-readable output, represent booleans as colorful emoji."""
    if b:
        return '✅'
    return '❌'

