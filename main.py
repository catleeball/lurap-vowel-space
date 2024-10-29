import argparse

from praatio import textgrid
from praatio.data_classes.textgrid import Textgrid
from ipapy import is_valid_ipa

from dataclasses import dataclass


@dataclass(frozen=True)
class Recording:
    textgrid_file_path: str
    textgrid_data: Textgrid
    audio_file_path: str | None = None


@dataclass(frozen=True)
class RecordingValidity:
    """Things we want to validate for a given Recording (and methods to perform such validation)."""
    # Must have 4 tiers
    valid_tier_count: bool
    # Tiers are named 'phone', 'word', 'phrase', and 'notes'
    valid_tier_names: bool
    # Tiers are in the order ['phone', 'word', 'phrase', 'notes']
    valid_tier_order: bool
    # All words are in the orthography (and spelled correctly).
    valid_words: bool
    # Phones are all single IPA phones
    valid_phones: bool
    invalid_words: set[str]
    invalid_phones: set[str]

    @staticmethod
    def validate(recording: Recording) -> 'RecordingValidity':
        """Given a recording, check for validity using all validation methods."""
        valid_tier_count = RecordingValidity.validate_tier_count(recording.textgrid_data)
        valid_tier_names = RecordingValidity.validate_tier_names(recording.textgrid_data)
        valid_tier_order = RecordingValidity.validate_tier_order(recording.textgrid_data)
        valid_words, invalid_words = RecordingValidity.validate_words(recording.textgrid_data)
        valid_phones, invalid_phones = RecordingValidity.validate_phones(recording.textgrid_data)
        return RecordingValidity(
            valid_tier_count=valid_tier_count,
            valid_tier_names=valid_tier_names,
            valid_tier_order=valid_tier_order,
            valid_words=valid_words,
            valid_phones=valid_phones,
            invalid_words=invalid_words,
            invalid_phones=invalid_phones
        )

    @staticmethod
    def validate_tier_count(textgrid: Textgrid) -> bool:
        return len(textgrid.tiers) == 4

    @staticmethod
    def validate_tier_names(textgrid: Textgrid) -> bool:
        return {'phone', 'word', 'phrase', 'notes'} == set(textgrid.tierNames)

    @staticmethod
    def validate_tier_order(textgrid: Textgrid) -> bool:
        return ('phone', 'word', 'phrase', 'notes') == set(textgrid.tierNames)

    @staticmethod
    def validate_words(textgrid: Textgrid, orthography: set[str]) -> tuple[bool, set[str]]:
        if 'word' not in textgrid.tierNames:
            return False, set()

        validity = True
        invalid_words = set()
        word_tier = textgrid.getTier('word')

        for word in set(word_tier.entries):
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

        for phone in set(phone_tier.entries):
            for char in phone:
                if not is_valid_ipa(char):
                    validity = False
                    invalid_phones.add(char)

        return validity, invalid_phones


def main():
    parser = argparse.ArgumentParser()
    # todo: write arg parser for individual files and directories with many fils
    main()

    # tg = textgrid.openTextgrid(
    #     fnFullPath='/Users/catball/data/lurap/Completed_transcriptions/kâârö_vowelspace_transcribed.TextGrid',
    #     includeEmptyIntervals=True,
    # )
    # tiers = tg.tiers
    # for tier in tiers:
    #     print(tier.name)


if __name__ == '__main__':
    main()
