import argparse
from pathlib import Path

import lib
from lib import TranscribedRecording


def get_args() -> list[Path]:
    parser = argparse.ArgumentParser(
        prog='fix_ipa.py',
        description='Substitute lookalike graphemes with their proper IPA codepoints.',
        add_help=True,
        epilog='Github repo for this program: https://github.com/catleeball/lurap-vowel-space'
    )
    parser.add_argument('-t', '--textgrid', type=Path,
                        help='Praat textgrid file path.')
    parser.add_argument('-d', '--directory', type=Path,
                        help='Directory containing a number of Praat textgrid files.')

    args = parser.parse_args()

    if not args.textgrid and not args.directory:
        raise IOError(lib.err_str('Please specify a textgrid file with --textgrid or a directory containing textgrid files with --orthography.'))

    paths = lib.get_textgrid_file_paths(args.textgrid, args.directory)

    if not paths:
        raise IOError(lib.err_str('No textgird files exist in --textgrid or --directory.'))

    return paths


def substitute_ipa(phone: str):
    # invalid phone characters from first validation run:
    #     ? ẽ í õ ö ä ë ô â ũ : ã ê ĩ ï ÿ
    # pairwise replacements:
    #    'ẽ', 'ẽ', 'õ', 'õ', 'ũ', 'ũ', 'ã', 'ã', 'ĩ', 'ĩ', 'ë', 'ë', 'ö', 'ö', 'ü', 'ü', 'ä', 'ä', 'ï ', 'ï', 'í ', 'î ', 'ô ', 'ô ', 'â ', 'â ', 'ê ', 'ê', ': ', 'ː'
    match phone:
        # nasalized vowels
        case 'ẽ':  # U+1EBD
            return 'ẽ'
        case 'õ':
            return 'õ'
        case 'ũ':
            return 'ũ'
        case 'ã':
            return 'ã'
        case 'ĩ':
            return 'ĩ'
        # centralized vowels
        case 'ë':
            return 'ë'
        case 'ö':
            return 'ö'
        case 'ü':
            return 'ü'
        case 'ä':
            return 'ä'
        case 'ï':
            return 'ï'
        case 'ÿ':
            return 'ÿ'
        # tone
        case 'í':
            return 'î'
        case 'ô':
            return 'ô'
        case 'â':
            return 'â'
        case 'ê':
            return 'ê'
        # typos
        case ':':
            return 'ː'


def main():
    paths = get_args()
    recordings = []
    for path in paths:
        if not path.exists():
            lib.warn(f'Path does not exist, skipping: {path}')
            continue
        recordings.append(TranscribedRecording.from_paths(textgrid_path=path))
    


if __name__ == '__main__':
    main()
