from pathlib import Path
from typing import Optional
from argparse import ArgumentParser
from mido import MidiFile, Message
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

song = getEmptySong(2)
song.ticksPerBeat = 100
song.beatsPerMeasure = 10
song.beatsPerMinute = 120
song.tracks[0].instrument.octave = 2


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


NoteInfo = namedtuple("NoteInfo", "note_value note_time start_tick end_tick")


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
    note_time = round(find_note_time(i, msg.note, msgs) * 1000)
    start_tick = round((current_time - round(msg.time * 1000)) / 10)
    end_tick = round((current_time - round(msg.time * 1000) + note_time) / 10)
    return NoteInfo(
        note_value=note_value,
        note_time=note_time,
        start_tick=start_tick,
        end_tick=end_tick
    )


msgs = list(midi)

time = 0
i = 0
while i < len(msgs):
    msg = msgs[i]
    time += round(msg.time * 1000)
    if msg.type != "note_on" or msg.velocity == 0:
        i += 1
        continue
    chord = [gather_note_info(i, msgs, time)]
    while (gather_note_info(i, msgs, time).start_tick ==
           gather_note_info(i + 1, msgs, time).start_tick):
        i += 1
        chord.append(gather_note_info(i, msgs, time))
    logger.debug(f"Chord {[c.note_value for c in chord]} starts on tick "
                 f"{chord[0].start_tick} and ends on tick {chord[0].end_tick} "
                 f"for {chord[0].end_tick - chord[0].start_tick} ticks")
    song.tracks[0].notes.append(
        NoteEvent(
            notes=[
                Note(
                    note=n.note_value,
                    enharmonicSpelling=EnharmonicSpelling.NORMAL
                ) for n in chord
            ],
            startTick=chord[0].start_tick,
            endTick=chord[0].end_tick
        )
    )
    i += 1

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

