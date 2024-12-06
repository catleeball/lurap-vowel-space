import argparse
import csv
import unicodedata
from pathlib import Path

import parselmouth
from praatio.audio import extractSubwav
from praatio.utilities.constants import Interval
from ipapy import UNICODE_TO_IPA
from pydub import AudioSegment

from lib import TranscribedRecording


def get_phrase_final_vowels(tr: TranscribedRecording) -> list[Interval]:
    phrase_final_vowels = []
    max_index = len(tr.phones)

    for index, phone in enumerate(tr.phones):
        # current phone is empty, skip
        if not phone.label:
            continue

        # Skip labels that have only whitespace in them, effectively being empty
        label = str(phone.label).strip()  # Should already be a string, but let's make sure
        if label == '':
            continue

        # fetch the next interval if it exists
        if index >= max_index:
            continue
        next_label: str = tr.phones[index+1].label
        next_interval = tr.phones[index+1]
        if type(next_label) == str:
            next_label = next_label.strip()

        # If the next interval is empty and longer than 1s, we're probably at the end of a phrase
        if next_label:
            continue
        if next_interval.end - next_interval.start < 1.0:
            continue

        if is_grapheme_an_ipa_vowel(phone.label):
            phrase_final_vowels.append(phone)

    return phrase_final_vowels


IPA_SUBS = {
    'ẽ': 'ẽ',
    'õ': 'õ',
    'ũ': 'ũ',
    'ã': 'ã',
    'ĩ': 'ĩ',
    'ë': 'ë',
    'ö': 'ö',
    'ü': 'ü',
    'ä': 'ä',
    'ï': 'ï',
    'í': 'î',
    'ô': 'ô',
    'â': 'â',
    'ê': 'ê',
}


def fix_ipa(s: str) -> str:
    if s in IPA_SUBS:
        return IPA_SUBS[s]
    else:
        return s


def remove_diacritics(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def is_grapheme_an_ipa_vowel(grapheme: str) -> bool:
    firstchar = fix_ipa(grapheme[0])
    firstchar = remove_diacritics(firstchar).strip()
    return UNICODE_TO_IPA[firstchar].is_vowel


def get_cli_path() -> tuple[Path, Path]:
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
        '-w', '--wav',
        type=Path,
        help='wav file audio recording.'
    )
    args = parser.parse_args()
    textgrid_path: Path = args.textgrid
    wav_path: Path = args.wav

    if not textgrid_path:
        raise IOError('No textgrid specified! Use --textgrid')

    if not wav_path:
        raise IOError('No wav file specified! Use --wav')

    if not textgrid_path.exists():
        raise IOError(f'File does not exist or is inaccessible: {textgrid_path}')

    if not wav_path.exists():
        raise IOError(f'File does not exist or is inaccessible: {wav_path}')

    return textgrid_path, wav_path


def extract_sounds(vowels: list[Interval], wav_path: Path, filename_prefix: str = '') -> list[Path]:
    output_filenames = []
    # make a directory to put all our new wav files and report into
    Path(filename_prefix).mkdir(mode=0o755, exist_ok=True)

    with open(wav_path, 'rb') as wav_in:
        audio = AudioSegment.from_file(wav_in, format='wav')
        for vowel in vowels:
            output_filename = Path(f'{filename_prefix}/{filename_prefix}_vowel_{vowel.start}_to_{vowel.end}.wav')
            start = sec_to_ms(vowel.start)
            end = sec_to_ms(vowel.end)
            audio_slice = audio[start:end]

            with open(output_filename, 'wb') as wav_out:
                audio_slice.export(wav_out, format='wav')

            output_filenames.append(output_filename)

    return output_filenames


def sec_to_ms(seconds: float) -> float:
    return seconds * 1000


def get_filename_prefix(s: str) -> str:
    for i in s.split('_'):
        if not i or i == '':
            continue
        return i


def write_report(
        report_path: Path,
        tg_path: Path,
        input_wav_path: Path,
        vowel_wav_files: list[Path],
        vowel_intervals: list[Interval],
        tr: TranscribedRecording,
):
    report_data_rows = []
    for vowel, vowel_wav in zip(vowel_intervals, vowel_wav_files):
        report_data_rows.append({
            'start': vowel.start,
            'end': vowel.end,
            'phone': vowel.label,
            'word': tr.word_at_time(vowel.start),
            'phrase': tr.phrase_at_time(vowel.end),
            'vowel_wav_file': str(vowel_wav),
            'recording_wav_file': str(input_wav_path),
            'textgrid_file': str(tg_path),
        })
    with open(report_path, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['start', 'end', 'phone', 'word', 'phrase', 'vowel_wav_file', 'recording_wav_file', 'textgrid_file'])
        writer.writerows(report_data_rows)


def voiced_percents(vowel_wav_files: list[Path]) -> list[float]:
    for vowel_wav in vowel_wav_files:
        pass
        # TODO: either figure out how to get this to call the "Voice report" praat command,
        # or figure out how call the Pitch.count_voiced_frames command
        # - https://parselmouth.readthedocs.io/en/stable/api_reference.html#parselmouth.Pitch.count_voiced_frames
        # - https://github.com/YannickJadoul/Parselmouth/blob/4d62714f4117679f0569706c8b7a199dd52b3364/praat/fon/VoiceAnalysis.h#L50
        # - https://github.com/YannickJadoul/Parselmouth/blob/4d62714f4117679f0569706c8b7a199dd52b3364/praat/dwtools/MultiSampledSpectrogram.h#L57


def main():
    tg_path, wav_path = get_cli_path()
    tr = TranscribedRecording.from_path(
        textgrid_path=tg_path,
        audio_path=wav_path
    )
    final_phones = get_phrase_final_vowels(tr)
    for phone in final_phones:
        is_vowel = is_grapheme_an_ipa_vowel(phone.label)
        print(f'{phone.label}\t{is_vowel}')

    filename_prefix = get_filename_prefix(str(tg_path.name))
    vowel_wav_files = extract_sounds(final_phones, wav_path, filename_prefix)
    write_report(
        report_path=Path(f'{filename_prefix}_vowels_report.csv'),
        tg_path=tg_path,
        input_wav_path=wav_path,
        vowel_wav_files=vowel_wav_files,
        vowel_intervals=final_phones,
        tr=tr,
    )


if __name__ == '__main__':
    main()
