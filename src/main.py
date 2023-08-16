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

logger = create_logger(name=__name__, level=logging.DEBUG)

parser = ArgumentParser(prog="ArcadeMIDItoSong",
                        description="A program to convert MIDI files to the "
                                    "Arcade song format. ")
parser.add_argument("--input", "-i", required=True, type=Path,
                    help="Input MIDI file")
parser.add_argument("--output", "-o", type=Optional[Path],
                    help="Output text file path, otherwise we will output to "
                         "standard output.")
args = parser.parse_args()
logger.debug(f"Received arguments: {args}")

input_path = Path(args.input)
logger.debug(f"Input path is {input_path}")

midi = MidiFile(input_path)

logger.debug(f"MIDI is {midi.length}s long, "
             f"using {ceil(midi.length)} measures")


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
    note_time = round(find_note_time(index, msg.note, msgs) * 1000)
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
for i, msg in enumerate(msgs):
    curr_time += round(msg.time * 1000)
    if msg.type not in ("note_on", "note_off"):
        continue
    note_info = gather_note_info(i, msgs, curr_time)
    if msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
        pass
    else:
        note_simple_event = NoteSimpleEvent(note_info.note_value,
                                            note_info.start_tick,
                                            note_info.end_tick)
        # logger.debug(note_simple_event)
        simple_notes.append(note_simple_event)


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

song = getEmptySong(ceil(midi.length))
song.ticksPerBeat = 100
song.beatsPerMeasure = 10
song.beatsPerMinute = 60
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
            startTick=chord.start_tick,
            endTick=chord.end_tick
        )
    )

bin_result = encodeSong(song)

logger.debug(f"Generated {len(bin_result)} bytes, converting to text")

hex_result = map(lambda v: format(v, "02x"), bin_result)
result = "hex`"
for hex_num in hex_result:
    result += hex_num
result += "`"

logger.debug(f"Hex string result is {len(result)} characters long")

output_path = args.output
if output_path is None:
    logger.debug("No output path provided, printing to standard output")
    print(result)
else:
    logger.debug(f"Writing to {output_path}")
    Path(output_path).write_text(result)
