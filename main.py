import argparse
import sys
from functools import cached_property
from pathlib import Path

from ipapy import is_valid_ipa
from praatio import textgrid
from praatio.data_classes.textgrid import Textgrid
from termcolor import colored


class Recording:
    # Location of the textgrid file.
    textgird_path: Path
    textgrid_data: Textgrid
    # Assert whether all words are in the orthography (and spelled correctly).
    valid_words: bool
    # Assert whether phones are all single IPA phones
    valid_phones: bool
    # Record when invalid words or phones are detected.
    invalid_phones: dict = {}
    invalid_words: dict = {}
    invalid_word_set: set[str] = set()
    invalid_phone_set: set[str] = set()
    # TSV file containing the orthography, where words are the first column. Further columns not yet used.
    # If orthography is not supplied, word verification will simply return true.
    orthography_path: Path | None = None
    orthography: set[str] | None = None

    @property
    def valid_tier_count(self) -> bool:
        """Assert whether there's four tiers."""
        return len(self.textgrid_data.tiers) == 4

    @cached_property
    def valid_tier_names(self) -> bool:
        """Assert whether tiers are names correctly."""
        return {'phone', 'word', 'phrase', 'notes'} == set(self.textgrid_data.tierNames)

    @property
    def valid_tier_order(self) -> bool:
        """Assert whether tiers are in order."""
        return ('phone', 'word', 'phrase', 'notes') == self.textgrid_data.tierNames

    @cached_property
    def valid_tiers(self) -> bool:
        """Assert whether tiers have the correct names in the correct order."""
        return all((self.valid_tier_order, self.valid_tier_count, self.valid_tier_names))

    def __init__(
            self,
            textgrid_path: Path,
            orthograpy_path: Path | None = None
    ):
        """Given a textgrid, validate attributes of the transcription."""
        self.textgrid_path = textgrid_path
        self.textgrid_data = textgrid.openTextgrid(str(textgrid_path), includeEmptyIntervals=False)
        self.orthography_path = orthograpy_path

        # TODO: Also check IPA transcriptions in orthography match the phone tier transcriptions,
        #  but for now, just get the first column for word verification.
        if orthograpy_path and orthograpy_path.exists():
            orthography = Recording._parse_orthography(orthograpy_path)
            if orthography:
                self.orthography = orthography

        self.valid_words, self.invalid_word_set = Recording.validate_words(self.textgrid_data, self.orthography)
        self.valid_phones, self.invalid_phone_set = Recording.validate_phones(self.textgrid_data)

    def __str__(self) -> str:
        """Human-readable summary of the validation"""
        summary = f'''
        FILE:\t{self.textgrid_path}
        TIERS:\t{emoji_bool(self.valid_tiers)}\t{self.textgrid_data.tierNames}
        PHONES:\t{emoji_bool(self.valid_phones)}
        WORDS:\t{emoji_bool(self.valid_words)}
        '''

        if self.invalid_word_set:
            summary += f'INVALID_WORDS:\t{', '.join(self.invalid_word_set)}\n'
        if self.invalid_phone_set:
            summary += f'INVALID_PHONES:\t{', '.join(self.invalid_phone_set)}\n'

        return summary

    def to_tsv_line(self) -> str:
        # TSV Headers: FILENAME\tTIERS_VALID\tPHONES_VALID\tWORDS_VALID\tINVALID_PHONES\tINVALID_WORDS\t
        return f'{self.textgrid_path}\t{int(self.valid_tiers)}\t{int(self.valid_phones)}\t{' ; '.join(self.invalid_phone_set)}\t{' ; '.join(self.invalid_word_set)}\n'

    def to_dict(self) -> dict:
        return {
            'FILENAME': str(self.textgrid_path),
            'TIERS_ARE_VALID': self.valid_tiers,
            # 'TIER_COUNT_VALID': self.valid_tier_count,
            # 'TIER_NAMES_VALID': self.valid_tier_names,
            # 'TIER_ORDER_VALID': self.valid_tier_order,
            'PHONES_ARE_VALID': self.valid_phones,
            'INVALID_PHONES': self.invalid_phone_set,
            'INVALID_WORDS': self.invalid_word_set,
        }

    @staticmethod
    def _parse_orthography(orthography_path: Path) -> set[str]:
        orthography: set[str] = set()
        with open(orthography_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                splitline = line.split(sep='\t', maxsplit=1)
                if not splitline:
                    continue
                word = splitline[0]
                orthography.add(word)
        return orthography

    @staticmethod
    def validate_words(textgrid: Textgrid, orthography: set[str]) -> tuple[bool, set[str]]:
        """Check that all words in the word tier exist in the orthography."""
        if not orthography:
            return True, set()
        if 'word' not in textgrid.tierNames:
            return False, set()

        validity = True
        invalid_words = set()
        word_tier = textgrid.getTier('word')

        for entry in word_tier.entries:
            word = entry.label
            if not word:
                continue
            if word not in orthography:
                validity = False
                invalid_words.add(word)

        return validity, invalid_words

    @staticmethod
    def validate_phones(textgrid: Textgrid) -> tuple[bool, set[str]]:
        """Check that all phones in the phone tier are valid IPA characters."""
        if 'phone' not in textgrid.tierNames:
            return False, set()
        validity = True
        invalid_phones = set()
        phone_tier = textgrid.getTier('phone')

        for entry in phone_tier.entries:
            phone = entry.label
            if not phone:
                continue
            for char in phone:
                if not is_valid_ipa(char):
                    validity = False
                    invalid_phones.add(char)

        return validity, invalid_phones


def emoji_bool(b: bool) -> str:
    """For human-readable output, represent booleans as colorful emoji."""
    if b:
        return '✅'
    return '❌'


def get_args() -> tuple[list[Path], Path|None]:
    """Parse and validate command line arguments."""
    parser = argparse.ArgumentParser(
        prog='Textgrid Validator',
        description='''Validates Praat TextGrid annotations.

        Validates the following features of a TextGrid:
            - Contains tiers in order: (phone, word, phrase, notes)
            - Words exist in the orthography (if one is specified with --orthography)
            - Phones are valid IPA phones

        One or both of --textgrid and --directory must be specified.
        If --orthography is not specified, words will not be checked for validity.
        ''',
        add_help=True,
        epilog='Github repo for this program: https://github.com/catleeball/lurap-vowel-space'
    )
    parser.add_argument('-t', '--textgrid', type=Path,
                        help='Praat textgrid file path.')
    parser.add_argument('-d', '--directory', type=Path,
                        help='Directory containing a number of Praat textgrid files.')
    parser.add_argument('-o', '--orthography', type=Path,
                        help='Tab-separated file containing orthography. Used to check word validity. First column should be word, second column should be IPA pronunciation.')
    args = parser.parse_args()

    if not args.textgrid and not args.directory:
        print(colored(text='Error: Please specify a textgrid file with --textgrid or a directory containing textgrid files with --orthography.', color='red'), file=sys.stderr)
        exit(1)

    if not args.orthography:
        print(colored(text="Warning: If an orthography file isn't specified with --orthography, words will not be validated for spelling and inclusion in the orthography.", color='yellow'), file=sys.stderr)

    if args.orthography and not args.orthography.exists():
        print(colored(text=f'Warning: Path {str(args.orthography)} does not exist.', color='yellow'), file=sys.stderr)

    paths = get_textgrid_file_paths(args)

    if not paths:
        print(colored(text=f'Error: No textgird files exist in --textgrid or --directory.', color='red'), file=sys.stderr)
        exit(1)

    return paths, args.orthography


def get_textgrid_file_paths(args: argparse.Namespace) -> list[Path]:
    """Get textgrid files from CLI arguments"""
    paths: list[Path] = []
    for path in (args.textgrid, args.directory):
        path: Path
        if path and path.exists():
            if path.is_dir():
                paths.extend(get_textgrid_files_from_directory(path))
            else:
                # Don't assert path.is_file() in case this is a symlink we need to follow
                paths.append(path)
        if path and not path.exists():
            print(colored(text=f'Warning: Path {str(path)} does not exist.', color='yellow'), file=sys.stderr)
    return paths


def get_textgrid_files_from_directory(path: Path) -> list[Path]:
    """Get files that end in .textgrid from the given directory path. Don't recurse the entire directory structure."""
    files: list[Path] = [i for i in path.iterdir() if i.is_file()]
    files = [i for i in files if i.name.lower().endswith('textgrid')]
    if not files:
        print(colored(text=f'Warning: Directory {str(path)} contains no textgrid files.', color='yellow'),
              file=sys.stderr)
    return files


def main():
    textgrid_paths, orthography_path = get_args()

    # Header for TSV file
    tsv_output = ['FILENAME\tTIERS_VALID\tPHONES_VALID\tWORDS_VALID\tINVALID_PHONES\tINVALID_WORDS\t']

    for textgrid_path in textgrid_paths:
        validity = Recording(textgrid_path, orthography_path)
        # print(validity)
        tsv_output.append(validity.to_tsv_line())

    print(tsv_output)


if __name__ == '__main__':
    main()
