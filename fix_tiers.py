import argparse
import math
from pathlib import Path

from praatio.data_classes.textgrid_tier import TextgridTier

import lib
from lib import TranscribedRecording
from praatio.utilities.constants import Interval


def get_cli_paths() -> Path:
    parser = argparse.ArgumentParser(
        prog='fix_word_tier.py',
        add_help=True,
        epilog='Github repo for this program: https://github.com/catleeball/lurap-vowel-space'
    )
    parser.add_argument(
        '-t', '--textgrid',
        type=Path,
        help='Praat textgrid file path.'
    )
    parser.add_argument(
        '-o', '--orthography',
        type=Path,
        help='Orthography file path.'
    )
    args = parser.parse_args()
    textgrid_path: Path = args.textgrid
    orthography_path: Path = args.orthography

    if not textgrid_path:
        raise IOError('No textgrid specified! Use --textgrid')

    if not orthography_path:
        raise IOError('No orthography specified! Use --orthography')

    if not textgrid_path.exists():
        raise IOError(f'File does not exist or is inaccessible: {textgrid_path}')

    if not orthography_path.exists():
        raise IOError(f'File does not exist or is inaccessible: {orthography_path}')

    return textgrid_path, orthography_path


def remove_single_char_words(word_tier: TextgridTier, log_prefix: str = '') -> TextgridTier:
    """Some phones appear in the word tier of some textgrids. Start by removing all intervals containing 1 character. There are no single items in the orthography less than 3 chars long. This also accounts for a single pair of combining unicode characters."""
    entries_to_delete: list[Interval] = []
    deletion_log = []

    for entry in word_tier.entries:
        entry: Interval
        if len(entry.label) < 2:
            entries_to_delete.append(entry)
            deletion_log.append(f'{entry.start}\t{entry.end}\t{entry.label}')

    for entry in entries_to_delete:
        word_tier.deleteEntry(entry)

    deletion_log = '\n'.join(deletion_log)
    deletion_log = 'START\tEND\tLABEL\n' + deletion_log
    with open(f'{log_prefix}_word_tier_deletion_log.tsv', 'w') as f:
        f.write(deletion_log)

    return word_tier


def fix_typos(word_tier: TextgridTier, phrase_tier: TextgridTier, orthography: set[str], log_prefix: str = ''):
    replacement_log = []

    for entry in word_tier.entries:
        entry: Interval
        label = str(entry.label).strip()
        if label not in orthography:
            # Try to fetch the word's spelling from the phrase tier
            old_label = entry.label
            phrase_label = get_label_at_endtime(phrase_tier, entry.end)
            new_label = extract_word_from_phrase(phrase_label)
            if not phrase_label or not new_label:
                replacement_log.append(f'{entry.start}\t{entry.end}\t{old_label}\tNONE')
                continue

            new_entry = Interval(start=entry.start, end=entry.end, label=new_label)
            word_tier.insertEntry(new_entry, 'replace', 'silence')
            replacement_log.append(f'{entry.start}\t{entry.end}\t{old_label}\t{new_label}')

    replacement_log = '\n'.join(replacement_log)
    replacement_log = 'START\tEND\tOLD_LABEL\tNEW_LABEL' + replacement_log
    with open(f'{log_prefix}_word_tier_typo_log.tsv', 'w') as f:
        f.write(replacement_log)

    return word_tier


def get_label_at_endtime(tier: TextgridTier, end_time) -> str | None:
    for entry in tier.entries:
        if math.isclose(entry.end, end_time, abs_tol=0.01):
            return entry.label


def extract_word_from_phrase(phrase: str) -> str | None:
    if not phrase:
        return None
    phrase = phrase.strip()
    tokens = phrase.split(' ')
    if len(tokens) < 3:
        return None
    if tokens[0].startswith('inkj') and tokens[1].startswith('kas'):
        return ' '.join(tokens[2:])


def remove_long_ipa(word_tier: TextgridTier, log_prefix: str = '') -> TextgridTier:
    """Remove ː from word tier entries; it doesn't appear in orthography."""
    replacement_log = []
    for entry in word_tier.entries:
        entry: Interval
        if 'ː' in entry.label:
            new_label = str(entry.label).replace('ː', '')
            replacement_log.append(f'{entry.start}\t{entry.end}\t{entry.label}\t{new_label}')
            new_entry = Interval(start=entry.start, end=entry.end, label=new_label)
            word_tier.insertEntry(new_entry, 'replace', 'silence')

    replacement_log = '\n'.join(replacement_log)
    replacement_log = 'START\tEND\tOLD_LABEL\tNEW_LABEL' + replacement_log
    with open(f'{log_prefix}_word_tier_long_ipa_removal_log.tsv', 'w') as f:
        f.write(replacement_log)

    return word_tier


def replace_chars(tier: TextgridTier, target_text: str, replacement_text: str, log_prefix: str = '') -> TextgridTier:
    """Remove ː from word tier entries; it doesn't appear in orthography."""
    replacement_log = []
    for entry in tier.entries:
        entry: Interval
        if target_text in entry.label:
            new_label = str(entry.label).replace(target_text, '')
            replacement_log.append(f'{entry.start}\t{entry.end}\t{entry.label}\t{new_label}')
            new_entry = Interval(start=entry.start, end=entry.end, label=new_label)
            tier.insertEntry(new_entry, 'replace', 'silence')

    replacement_log = '\n'.join(replacement_log)
    replacement_log = 'START\tEND\tOLD_LABEL\tNEW_LABEL' + replacement_log
    with open(f'{log_prefix}_word_tier_replace_{target_text}_with_{replacement_text}_log.tsv', 'w') as f:
        f.write(replacement_log)

    return tier


def multireplace_chars(phrase_tier: TextgridTier, word_tier: TextgridTier, replacements: list[tuple[str, str]], log_prefix: str) -> tuple[TextgridTier, TextgridTier]:
    for tier in (phrase_tier, word_tier):
        for target, replacement in replacements:
            replace_chars(tier, target, replacement, log_prefix)
    return phrase_tier, word_tier


def main():
    textgrid_path, orthography_path = get_cli_paths()
    tr = TranscribedRecording.from_path(textgrid_path)
    orthography = parse_orthography(orthography_path)

    if 'word' not in tr.textgrid_data.tierNames:
        raise ValueError(f'Textgrid {tr.textgrid_path} does not contain a tier named "word".')
    if 'phrase' not in tr.textgrid_data.tierNames:
        raise ValueError(f'Textgrid {tr.textgrid_path} does not contain a tier named "phrase".')

    prefix = tr.textgrid_path.name.split('_')[0]

    word_tier = tr.textgrid_data.getTier('word')
    phrase_tier = tr.textgrid_data.getTier('phrase')

    replacements = [
        ('ː', ''),
        ('_', ' '),
        ('myn', 'mÿn'),
        ('pëëpjo', 'pëëpjo'),
        ('sïïpjo', 'sïï pjo'),
        ('sêêpjo', 'sïï pjo'),
        ('puutä', 'puu ttä'),
        ('pôôpy', 'pôpy'),
        ('jykrii', 'jy krii'),
        ('mÿnpjo', 'mÿn pjo')
    ]
    multireplace_chars(phrase_tier, word_tier, replacements, prefix)
    word_tier = remove_single_char_words(word_tier, log_prefix=prefix)

    new_file_path = f'_{tr.textgrid_path.name}'
    tr.textgrid_data.save(new_file_path, 'long_textgrid', True)
    tr = TranscribedRecording.from_path(Path(new_file_path))
    word_tier = tr.textgrid_data.getTier('word')
    word_tier = fix_typos(word_tier, phrase_tier=phrase_tier, orthography=orthography, log_prefix=prefix)
    tr.textgrid_data.save(new_file_path, 'long_textgrid', True)


def parse_orthography(orthography_path: Path) -> set[str]:
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


if __name__ == '__main__':
    main()
