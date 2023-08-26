import logging
from argparse import ArgumentParser
from collections import namedtuple
from math import ceil
from pathlib import Path
from typing import Union

from mido import Message, MidiFile

from arcade.music import EnharmonicSpelling, Note, NoteEvent, Song, Track, \
    encodeSong, getEmptySong
from arcade.tracks import get_available_tracks
from utils.logger import create_logger

tracks = get_available_tracks()
track_names = [t.name.lower() for t in tracks]
track_ids = [t.id for t in tracks]

parser = ArgumentParser(prog="ArcadeMIDItoSong",
                        description="A program to convert MIDI files to the "
                                    "Arcade song format. ")
parser.add_argument("--input", "-i", required=True, type=Path,
                    help="Input MIDI file")
parser.add_argument("--output", "-o", type=Path,
                    help="Output text file path, otherwise we will output to "
                         "standard output.")
parser.add_argument("--track", "-t", metavar="TRACK",
                    choices=track_ids + track_names,
                    default=track_names[0],
                    help=f"A track to use, which changes the instrument. "
                         f"Available tracks include {track_names}. (You can "
                         f"also use indices 0-{len(track_ids) - 1}) Defaults "
                         f"to '{track_names[0]}'.")
parser.add_argument("--divisor", "-d", type=int,
                    default=1,
                    help="A divisor to reduce the number of measures used. "
                         "A higher integer means a longer song can fit in the "
                         "maximum of 255 measures of a song, but with less "
                         "precision. Must be greater than or equal to 1, and "
                         "defaults to 1 for no division.")
parser.add_argument("--debug", action="store_const",
                    const=logging.DEBUG, default=logging.INFO,
                    help="Include debug messages. Defaults to info and "
                         "greater severity messages only.")
args = parser.parse_args()
logger = create_logger(name=__name__, level=args.debug)
logger.debug(f"Received arguments: {args}")

input_path = Path(args.input)
logger.debug(f"Input path is {input_path}")

midi = MidiFile(input_path)
logger.debug(f"MIDI is {midi.length}s long")


def get_track_from_name_or_id(name_or_id: Union[int, str]) -> Track:
    logger.debug(f"Finding track {name_or_id}")
    for track in get_available_tracks():
        if name_or_id == track.name.lower() or name_or_id == track.id:
            selected_track = track
            break
    else:
        raise ValueError(f"Unknown track ID or name {name_or_id}!")
    logger.debug(f"Found track '{selected_track.name}' ({selected_track})")
    return selected_track


divisor = int(args.divisor)
if divisor < 1:
    raise ValueError(f"divisor must be an integer greater than or equal to 1, "
                     f"not {divisor}!")
logger.debug(f"Using divisor of {divisor}")


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
    note_time = round(find_note_time(index + 1, msg.note, msgs) * 1000)
    start_tick = round(current_time / 10)
    end_tick = start_tick + round(note_time / 10)
    return NoteInfo(
        note_value=msg.note,
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
    # logger.debug(f"{i}: {msg} (current time: {curr_time})")
    if msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0):
        pass
    else:
        note_info = gather_note_info(i, msgs, curr_time)
        note_simple_event = NoteSimpleEvent(note_info.note_value,
                                            note_info.start_tick,
                                            note_info.end_tick)
        ending_tick = max(ending_tick, note_info.end_tick)
        duration = note_simple_event.end_tick - note_simple_event.start_tick
        # logger.debug(f"{i}: * {note_simple_event} (duration: {duration})")
        simple_notes.append(note_simple_event)

logger.debug(f"Last tick is {ending_tick} ({round(ending_tick / divisor)} "
             f"after divisor)")

ending_tick = round(ending_tick / divisor)


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

logger.debug(f"measure_count = {measure_count}")
logger.debug(f"ticksPerBeat = {ticks_per_beat}")
logger.debug(f"beatsPerMeasure = {beats_per_measure}")
logger.debug(f"beatsPerMinute = {beats_per_minute}")
logger.debug(f"Maximum number of ticks is "
             f"{measure_count * ticks_per_beat * beats_per_measure} ticks")


def add_tracks_for_piano(song: Song):
    selected_track = get_track_from_name_or_id(args.track)
    selected_higher_track = get_track_from_name_or_id(args.track)
    song.tracks.append(selected_track)
    song.tracks[-1].instrument.octave = 2
    song.tracks.append(selected_higher_track)
    song.tracks[-1].instrument.octave = 7
    logger.debug(f"Added 2 piano tracks")


song = getEmptySong(measure_count)
song.ticksPerBeat = ticks_per_beat
song.beatsPerMeasure = beats_per_measure
song.beatsPerMinute = beats_per_minute
song.tracks.clear()
add_tracks_for_piano(song)

for i, chord in enumerate(simple_chords):
    # logger.debug(f"Chord {i}: {chord}")
    all_notes = [Note(note=n, enharmonicSpelling=EnharmonicSpelling.NORMAL)
                 for n in chord.notes]
    notes = []
    higher_notes = []
    for note in all_notes:
        instrumentOctave = song.tracks[-2].instrument.octave
        note_val = (note.note - (instrumentOctave - 2) * 12)
        note_val += 1 - 12
        if note_val > 63:
            higher_notes.append(note)
        else:
            notes.append(note)
    event = NoteEvent(
        notes=notes,
        startTick=round(chord.start_tick / divisor),
        endTick=round(chord.end_tick / divisor)
    )
    higher_event = NoteEvent(
        notes=higher_notes,
        startTick=round(chord.start_tick / divisor),
        endTick=round(chord.end_tick / divisor)
    )
    # logger.debug(f"Note event {i}: {event}")
    if len(event.notes) > 0:
        song.tracks[-2].notes.append(event)
    if len(higher_event.notes) > 0:
        song.tracks[-1].notes.append(higher_event)
    ending_tick = chord.end_tick

for i, track in enumerate(song.tracks):
    logger.debug(
        f"Created {len(song.tracks[i].notes)} note events in track {i}")
logger.debug(
    f"Total of {sum([len(t.notes) for t in song.tracks])} note events")

bin_result = encodeSong(song)

logger.debug(f"Generated {len(bin_result)} bytes, converting to text")

hex_result = map(lambda v: format(v, "02x"), bin_result)
result = "hex`"
for i, hex_num in enumerate(hex_result):
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
