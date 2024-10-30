import argparse
import sys
from pathlib import Path

import praatio.textgrid
from ipapy import is_valid_ipa
from praatio import textgrid
from praatio.data_classes.textgrid import Textgrid
from termcolor import colored


class Recording:
    textgird_path: Path
    textgrid_data: Textgrid
    # All words are in the orthography (and spelled correctly).
    valid_words: bool
    # Phones are all single IPA phones
    valid_phones: bool
    invalid_words: set[str] = []
    invalid_phones: set[str] = []
    orthography_path: Path | None = None
    orthography: set[str] | None = None

    @property
    def valid_tier_count(self) -> bool:
        return len(self.textgrid_data.tiers) == 4

    @property
    def valid_tier_names(self) -> bool:
        return {'phone', 'word', 'phrase', 'notes'} == set(self.textgrid_data.tierNames)

    @property
    def valid_tier_order(self) -> bool:
        return ('phone', 'word', 'phrase', 'notes') == self.textgrid_data.tierNames

    @property
    def valid_tiers(self) -> bool:
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

        # TODO: Also check IPA transcriptions in phones, but for now, just get the first column
        if orthograpy_path and orthograpy_path.exists():
            orthography: set[str] = set()
            with open(orthograpy_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    splitline = line.split(sep='\t', maxsplit=1)
                    if not splitline:
                        continue
                    word = splitline[0]
                    orthography.add(word)
            if orthography:
                self.orthography = orthography

        self.valid_words, self.invalid_words = Recording.validate_words(self.textgrid_data, self.orthography)
        self.valid_phones, self.invalid_phones = Recording.validate_phones(self.textgrid_data)

    def __str__(self) -> str:
        summary = f'''
        FILE:\t{self.textgrid_path}
        TIERS:\t{emoji_bool(self.valid_tiers)}\t{self.textgrid_data.tierNames}
        PHONES:\t{emoji_bool(self.valid_phones)}
        WORDS:\t{emoji_bool(self.valid_words)}
        '''

        if self.invalid_words:
            summary += f'INVALID_WORDS:\t{', '.join(self.invalid_words)}\n'
        if self.invalid_phones:
            summary += f'INVALID_PHONES:\t{', '.join(self.invalid_phones)}\n'

        return summary

    def to_tsv_line(self) -> str:
        # TSV Headers: FILENAME\tTIERS_VALID\tPHONES_VALID\tWORDS_VALID\tINVALID_PHONES\tINVALID_WORDS\t
        return f'{self.textgrid_path}\t{int(self.valid_tiers)}\t{int(self.valid_phones)}\t{' ; '.join(self.invalid_phones)}\t{' ; '.join(self.invalid_words)}\t'

    @staticmethod
    def validate_words(textgrid: Textgrid, orthography: set[str]) -> tuple[bool, set[str]]:
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
    if b:
        return '✅'
    return '❌'


def get_args() -> tuple[list[Path], Path|None]:
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

    if not args.orthography:
        print(colored(text="Warning: If an orthography file isn't specified with --orthography, words will not be validated for spelling and inclusion in the orthography.", color='yellow'), file=sys.stderr)

    if args.orthography and not args.orthography.exists():
        print(colored(text=f'Warning: Path {str(args.orthography)} does not exist.', color='yellow'), file=sys.stderr)

    # TODO: make this less nested, break this out into another function
    paths: list[Path] = []
    for path in (args.textgrid, args.directory):
        path: Path
        if path and path.exists():
            if path.is_dir():
                files: list[Path] = [i for i in path.iterdir() if i.is_file()]
                files = [i for i in files if i.name.lower().endswith('textgrid')]
                if not files:
                    print(colored(text=f'Warning: Directory {str(path)} contains no textgrid files.', color='yellow'), file=sys.stderr)
                paths.extend(files)
            else:
                paths.append(path)
        if path and not path.exists():
            print(colored(text=f'Warning: Path {str(path)} does not exist.', color='yellow'), file=sys.stderr)

    if not paths:
        print(colored(text=f'Error: No textgird files exist in --textgrid or --directory.', color='red'), file=sys.stderr)

    return paths, args.orthography


def main():
    textgrid_paths, orthography_path = get_args()

    tsv_output = ['FILENAME\tTIERS_VALID\tPHONES_VALID\tWORDS_VALID\tINVALID_PHONES\tINVALID_WORDS\t']

    for textgrid_path in textgrid_paths:
        validity = Recording(textgrid_path, orthography_path)
        # print(validity)
        tsv_output.append(validity.to_tsv_line())

    print(tsv_output)


if __name__ == '__main__':
    main()
