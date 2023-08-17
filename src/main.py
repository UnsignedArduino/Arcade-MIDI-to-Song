from pathlib import Path
from typing import Optional
from argparse import ArgumentParser
from mido import MidiFile, Message
from math import ceil
from collections import namedtuple
from arcade_music import encodeSong, getEmptySong, \
    NoteEvent, Note, EnharmonicSpelling
from utils.logger import create_logger
import logging

logger = create_logger(name=__name__, level=logging.INFO)

parser = ArgumentParser(prog="ArcadeMIDItoSong",
                        description="A program to convert MIDI files to the "
                                    "Arcade song format. ")
parser.add_argument("--input", "-i", required=True, type=Path,
                    help="Input MIDI file")
parser.add_argument("--output", "-o", type=Optional[Path],
                    help="Output text file path, otherwise we will output to "
                         "standard output.")
parser.add_argument("--divisor", "-d", type=int,
                    default=1,
                    help="A divisor to reduce the number of measures used. "
                         "A higher integer means a longer song can fit in the "
                         "maximum of 255 measures of a song, but with less "
                         "precision. Must be greater than or equal to 1, and "
                         "defaults to 1 for no division.")
args = parser.parse_args()
logger.debug(f"Received arguments: {args}")

input_path = Path(args.input)
logger.info(f"Input path is {input_path}")

midi = MidiFile(input_path)
logger.info(f"MIDI is {midi.length}s long")

divisor = int(args.divisor)
if divisor < 1:
    raise ValueError(f"divisor must be an integer greater than or equal to 1, "
                     f"not {divisor}!")
logger.info(f"Using divisor of {divisor}")


def find_note_time(start_index: int, note: int, msgs: list[Message]) -> float:
    time = 0
    for i in range(start_index, len(msgs)):
        msg = msgs[i]
        if msg.type not in ("note_on", "note_off"):
            continue
        time += msg.time
        if ((msg.type == "note_on" and msg.velocity == 0) or
            msg.type == "note_off") and msg.note == note:
            break
    return time


NoteInfo = namedtuple("NoteInfo",
                      "note_value note_time start_tick end_tick")


def gather_note_info(index: int, msgs: list[Message],
                     current_time: int) -> NoteInfo:
    msg = msgs[index]
    if msg.type != "note_on":
        return NoteInfo(
            note_value=-1,
            note_time=-1,
            start_tick=-1,
            end_tick=-1
        )
    note_value = msg.note
    note_time = round(find_note_time(index + 1, msg.note, msgs) * 1000)
    start_tick = round((current_time - round(msg.time * 1000)) / 10)
    end_tick = round((current_time - round(msg.time * 1000) + note_time) / 10)
    return NoteInfo(
        note_value=note_value,
        note_time=note_time,
        start_tick=start_tick,
        end_tick=end_tick
    )


NoteSimpleEvent = namedtuple("NoteSimpleEvent",
                             "note start_tick end_tick")
ChordSimpleEvent = namedtuple("ChordSimpleEvent",
                              "notes start_tick end_tick")

msgs = list(midi)
simple_notes = []

curr_time = 0
ending_tick = 0
for i, msg in enumerate(msgs):
    curr_time += round(msg.time * 1000)
    if msg.type not in ("note_on", "note_off"):
        continue
    note_info = gather_note_info(i, msgs, curr_time)
    # logger.debug(f"{i}: {msg}")
    if msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
        pass
    else:
        note_simple_event = NoteSimpleEvent(note_info.note_value,
                                            note_info.start_tick,
                                            note_info.end_tick)
        ending_tick = max(ending_tick, note_info.end_tick)
        # duration = note_simple_event.end_tick - note_simple_event.start_tick
        # logger.debug(f"{i}: * {note_simple_event} ({duration})")
        simple_notes.append(note_simple_event)


logger.info(f"Last tick is {ending_tick}")


def find_chord_with_start_tick(chords: list[ChordSimpleEvent],
                               start_tick: int) -> int:
    for i, chord in enumerate(chords):
        if chord.start_tick == start_tick:
            return i
    return -1


simple_chords = []
for note in simple_notes:
    chord_index = find_chord_with_start_tick(simple_chords, note.start_tick)
    if chord_index == -1:
        simple_chords.append(
            ChordSimpleEvent([note.note], note.start_tick, note.end_tick)
        )
    else:
        simple_chords[chord_index].notes.append(note.note)

ticks_per_beat = 100
beats_per_measure = 10
beats_per_minute = round(60 / divisor)
measure_count = ceil(ending_tick / ticks_per_beat / beats_per_measure)

logger.info(f"measure_count = {measure_count}")
logger.info(f"ticksPerBeat = {ticks_per_beat}")
logger.info(f"beatsPerMeasure = {beats_per_measure}")
logger.info(f"beatsPerMinute = {beats_per_minute}")
logger.info(f"Maximum number of ticks is {measure_count * ticks_per_beat * beats_per_measure} ticks")

song = getEmptySong(ceil(midi.length / divisor))
song.ticksPerBeat = ticks_per_beat
song.beatsPerMeasure = beats_per_measure
song.beatsPerMinute = beats_per_minute
song.tracks[0].instrument.octave = 2

for i, chord in enumerate(simple_chords):
    logger.debug(f"Chord {i}: {chord}")
    song.tracks[0].notes.append(
        NoteEvent(
            notes=[
                Note(
                    note=n,
                    enharmonicSpelling=EnharmonicSpelling.NORMAL
                ) for n in chord.notes
            ],
            startTick=round(chord.start_tick / divisor),
            endTick=round(chord.end_tick / divisor)
        )
    )
    ending_tick = chord.end_tick

bin_result = encodeSong(song)

logger.info(f"Generated {len(bin_result)} bytes, converting to text")

hex_result = map(lambda v: format(v, "02x"), bin_result)
result = "hex`"
for hex_num in hex_result:
    result += hex_num
result += "`"

logger.info(f"Hex string result is {len(result)} characters long")

output_path = args.output
if output_path is None:
    logger.info("No output path provided, printing to standard output")
    print(result)
else:
    logger.info(f"Writing to {output_path}")
    Path(output_path).write_text(result)
