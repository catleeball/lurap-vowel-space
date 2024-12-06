import sys
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from praatio import textgrid
from praatio.data_classes.textgrid import Textgrid
from praatio.utilities.constants import Interval
from termcolor import colored
import intervaltree
from intervaltree import IntervalTree


@dataclass(frozen=True)
class TierLabelPair:
    tier: str
    label: str


# @dataclass(frozen=True)
class TranscribedRecording:
    textgrid_path: Path
    textgrid_data: Textgrid
    audio_path: Path | None

    @cached_property
    def phones(self) -> list[Interval]:
        """Get list of phones sorted by start time ascending."""
        return sorted(self.textgrid_data.getTier('phone').entries, key=lambda t: t.start)

    @cached_property
    def words(self) -> list[Interval]:
        """Get list of words sorted by start time ascending."""
        return sorted(self.textgrid_data.getTier('word').entries, key=lambda t: t.start)

    @cached_property
    def phrases(self) -> list[Interval]:
        """Get list of phrases sorted by start time ascending."""
        return sorted(self.textgrid_data.getTier('phrase').entries, key=lambda t: t.start)

    @cached_property
    def interval_tree(self) -> IntervalTree:
        all_intervals = []
        for phone in self.phones:
            all_intervals.append((phone.start, phone.end, TierLabelPair('phone', phone.label)))
        for word in self.words:
            all_intervals.append((word.start, word.end, TierLabelPair('word', word.label)))
        for phrase in self.phrases:
            all_intervals.append((phrase.start, phrase.end, TierLabelPair('word', phrase.phrases)))

        return IntervalTree(intervaltree.Interval(*iv) for iv in all_intervals)

    def interval_at_time(self, timestamp: float | int) -> set[tuple[float, float, TierLabelPair]]:
        intervals: set[intervaltree.Interval] = self.interval_tree.at(timestamp)
        return [(i.begin, i.end, i.data) for i in intervals]

    def phrase_at_time(self, timestamp: float | int) -> str:
        intervals = self.interval_at_time(timestamp)
        phrase = ''
        for i in intervals:
            tier = i[2].tier
            label = i[2].label
            if tier == 'phrase':
                return label
        return phrase

    def word_at_time(self, timestamp: float | int) -> str:
        intervals = self.interval_at_time(timestamp)
        phrase = ''
        for i in intervals:
            tier = i[2].tier
            label = i[2].label
            if tier == 'word':
                return label
        return phrase

    def __init__(self, textgrid_path: Path, audio_path: Path | None = None):
        if not textgrid_path.exists():
            IOError(err_str(f'File does not exsit at {textgrid_path}'))

        textgrid_data = textgrid.openTextgrid(str(textgrid_path), includeEmptyIntervals=True)

        # Asserts textgrid tiers will be named 'phone', 'word', and 'phrase' exactly.
        if 'phone' not in textgrid_data.tierNames:
            raise ValueError(f'Phone tier not present or incorrectly named in textgrid {textgrid_path}. Tiers present: {textgrid_data.tierNames}')

        if 'word' not in textgrid_data.tierNames:
            raise ValueError(f'Word tier not present or incorrectly named in textgrid {textgrid_path}. Tiers present: {textgrid_data.tierNames}')

        if 'phrase' not in textgrid_data.tierNames:
            raise ValueError(f'Phrase tier not present or incorrectly named in textgrid {textgrid_path}. Tiers present: {textgrid_data.tierNames}')

        self.textgrid_path = textgrid_path
        self.textgrid_data = textgrid_data
        self.audio_path = audio_path

    @staticmethod
    def from_path(textgrid_path: Path, audio_path: Path | None = None) -> 'TranscribedRecording':
        """Old initialization method from when this was a dataclass. Left here so I don't have to refactor everything."""
        return TranscribedRecording(textgrid_path, audio_path)
        # if not textgrid_path.exists():
        #     IOError(err_str(f'File does not exsit at {textgrid_path}'))
        #
        # textgrid_data = textgrid.openTextgrid(str(textgrid_path), includeEmptyIntervals=True)
        #
        # # Asserts textgrid tiers will be named 'phone', 'word', and 'phrase' exactly.
        # if 'phone' not in textgrid_data.tierNames:
        #     raise ValueError(f'Phone tier not present or incorrectly named in textgrid {textgrid_path}. Tiers present: {textgrid_data.tierNames}')
        #
        # if 'word' not in textgrid_data.tierNames:
        #     raise ValueError(f'Word tier not present or incorrectly named in textgrid {textgrid_path}. Tiers present: {textgrid_data.tierNames}')
        #
        # if 'phrase' not in textgrid_data.tierNames:
        #     raise ValueError(f'Phrase tier not present or incorrectly named in textgrid {textgrid_path}. Tiers present: {textgrid_data.tierNames}')
        #
        # return TranscribedRecording(textgrid_path, textgrid_data, audio_path)


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

