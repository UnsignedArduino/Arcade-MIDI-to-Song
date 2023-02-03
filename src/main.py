from pathlib import Path
from typing import Optional
from argparse import ArgumentParser
from mido import MidiFile, Message
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


msgs = list(midi)

time = 0
for i, msg in enumerate(msgs):
    time += round(msg.time * 1000)
    if msg.type != "note_on" or msg.velocity == 0:
        continue
    note_time = round(find_note_time(i, msg.note, msgs) * 1000)
    note_value = msg.note - 11
    enharmonic = EnharmonicSpelling.NORMAL
    start_tick = round((time - round(msg.time * 1000)) / 10)
    end_tick = round((time - round(msg.time * 1000) + note_time) / 10)
    logger.debug(f"Note {note_value} with enharmonic {enharmonic} starts on "
                 f"tick {start_tick} and ends on tick {end_tick} for "
                 f"{end_tick - start_tick} ticks")
    song.tracks[0].notes.append(
        NoteEvent(
            notes=[
                Note(
                    note=note_value,
                    enharmonicSpelling=enharmonic
                )
            ],
            startTick=start_tick,
            endTick=end_tick
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

