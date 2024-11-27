import argparse
import csv
import sys
from functools import cached_property
from pathlib import Path

from ipapy import is_valid_ipa
from praatio import textgrid
from praatio.data_classes.textgrid import Textgrid
from praatio.utilities.constants import Interval
from termcolor import colored
import lib


class Recording:
    # Location of the textgrid file.
    textgird_path: Path
    textgrid_data: Textgrid
    # Assert whether all words are in the orthography (and spelled correctly).
    valid_words: bool
    # Assert whether phones are all single IPA phones
    valid_phones: bool
    # TODO: record times in the file where invalid phones & words are detected
    invalid_phone_entries: list[Interval] = []
    invalid_word_entries: list[Interval] = []
    # Record when invalid words or phones are detected.
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

        self.valid_words, self.invalid_word_set, self.invalid_word_entries = Recording.validate_words(self.textgrid_data, self.orthography)
        self.valid_phones, self.invalid_phone_set, self.invalid_phone_entries = Recording.validate_phones(self.textgrid_data)

    def __str__(self) -> str:
        """Human-readable summary of the validation"""
        summary = f'''
        FILE:\t{self.textgrid_path.name}
        TIERS:\t{lib.emoji_bool(self.valid_tiers)}\t{self.textgrid_data.tierNames}
        PHONES:\t{lib.emoji_bool(self.valid_phones)}
        WORDS:\t{lib.emoji_bool(self.valid_words)}
        '''

        if self.invalid_word_set:
            summary += f'INVALID_WORDS:\t{', '.join(self.invalid_word_set)}\n'
        if self.invalid_phone_set:
            summary += f'INVALID_PHONES:\t{', '.join(self.invalid_phone_set)}\n'

        return summary

    # def to_tsv_line(self) -> str:
    #     # TSV Headers: FILENAME\tTIERS_VALID\tPHONES_VALID\tWORDS_VALID\tINVALID_PHONES\tINVALID_WORDS\t
    #     return f'{self.textgrid_path.name}\t{int(self.valid_tiers)}\t{int(self.valid_phones)}\t{' ; '.join(self.invalid_phone_set)}\t{' ; '.join(self.invalid_word_set)}\n'

    def to_dict(self) -> dict:
        invalid_words = None
        invalid_phones = None
        if self.invalid_word_set:
            invalid_words = ' '.join(self.invalid_word_set)
        if self.invalid_phone_set:
            invalid_phones = ' '.join(self.invalid_phone_set)
        return {
            'FILENAME': self.textgrid_path.name,
            'TIERS_VALID': self.valid_tiers,
            'PHONES_VALID': self.valid_phones,
            'WORDS_VALID': self.valid_words,
            'INVALID_PHONES': invalid_phones,
            'INVALID_WORDS': invalid_words,
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
    def validate_words(textgrid: Textgrid, orthography: set[str]) -> tuple[bool, set[str], list[Interval]]:
        """Check that all words in the word tier exist in the orthography."""
        if not orthography:
            return True, set()
        if 'word' not in textgrid.tierNames:
            return False, set()

        validity = True
        invalid_words = set()
        invalid_entries: list[Interval] = []
        word_tier = textgrid.getTier('word')

        for entry in word_tier.entries:
            word = entry.label
            if not word:
                continue
            if word not in orthography:
                validity = False
                invalid_words.add(word)
                invalid_entries.append(entry)

        return validity, invalid_words, invalid_entries

    @staticmethod
    def validate_phones(textgrid: Textgrid) -> tuple[bool, set[str], list[Interval]]:
        """Check that all phones in the phone tier are valid IPA characters."""
        if 'phone' not in textgrid.tierNames:
            return False, set()
        validity = True
        invalid_phones = set()
        invalid_phone_entries = []
        phone_tier = textgrid.getTier('phone')

        for entry in phone_tier.entries:
            phone = entry.label
            if not phone:
                continue
            for char in phone:
                if not is_valid_ipa(char):
                    validity = False
                    invalid_phones.add(char)
                    invalid_phone_entries.append(entry)

        return validity, invalid_phones, invalid_phone_entries


def get_args() -> tuple[list[Path], Path|None]:
    """Parse and validate command line arguments."""
    parser = argparse.ArgumentParser(
        prog='validate_textgrid.py',
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
        raise IOError(lib.err_str('Error: Please specify a textgrid file with --textgrid or a directory containing textgrid files with --orthography.'))

    if not args.orthography:
        lib.warn("If an orthography file isn't specified with --orthography, words will not be validated for spelling and inclusion in the orthography.")

    if args.orthography and not args.orthography.exists():
        lib.warn(f'Path {str(args.orthography)} does not exist.')

    paths = lib.get_textgrid_file_paths(args.textgrid, args.directory)

    if not paths:
        raise IOError(lib.err_str('No textgird files exist in --textgrid or --directory.'))

    return paths, args.orthography


def write_csv_report(textgrids: list[Recording]):
    if not textgrids:
        raise ValueError('No textgrid validations to write to report!')

    with open('validation_report.csv', 'w', newline='') as csvfile:
        filednames = ['FILENAME', 'TIERS_VALID', 'PHONES_VALID', 'WORDS_VALID', 'INVALID_PHONES', 'INVALID_WORDS',]
        writer = csv.DictWriter(csvfile, fieldnames=filednames)
        writer.writeheader()
        for textgrid in textgrids:
            writer.writerow(textgrid.to_dict())


def write_invalid_items_csv_report(textgrids: list[Recording]):
    if not textgrids:
        raise ValueError('No textgrid validations to write to report!')

    with open('invalid_items_report.csv', 'a', newline='') as csvfile:
        filednames = ['FILENAME', 'TIER', 'INVALID_TOKEN', 'START_TIME', 'END_TIME']
        writer = csv.DictWriter(csvfile, fieldnames=filednames)
        for tg in textgrids:
            # for invalid_phone in tg.invalid_phone_entries:
            #     writer.writerow({
            #         'FILENAME': tg.textgrid_path,
            #         'TIER': 'word',
            #         'INVALID_TOKEN': invalid_phone.label,
            #         'START_TIME': invalid_phone.start,
            #         'END_TIME': invalid_phone.end,
            #     })
            for invalid_word in tg.invalid_word_entries:
                writer.writerow({
                    'FILENAME': tg.textgrid_path,
                    'TIER': 'word',
                    'INVALID_TOKEN': invalid_word.label,
                    'START_TIME': invalid_word.start,
                    'END_TIME': invalid_word.end,
                })

def main():
    textgrid_paths, orthography_path = get_args()
    # TODO: add cli args for:
    # - no cli output
    # - specify tsv file output location
    # TODO: reconsider behavior of program when no orthography supplied

    validated_textgrids = []
    for textgrid_path in textgrid_paths:
        validated_textgrid = Recording(textgrid_path, orthography_path)
        validated_textgrids.append(validated_textgrid)
        # Print to stdout a human-readable summary of validation for each file
        print(validated_textgrid)

    if not validated_textgrids:
        raise ValueError('No textgrid validations to write to report!')

    write_csv_report(validated_textgrids)
    write_invalid_items_csv_report(validated_textgrids)


if __name__ == '__main__':
    main()
