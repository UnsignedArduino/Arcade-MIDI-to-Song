from pathlib import Path
from typing import Optional
from argparse import ArgumentParser
# from mido import MidiFile
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

# midi = MidiFile(input_path)

song = getEmptySong(2)

song.tracks[0].notes.append(
    NoteEvent(
        notes=[
            Note(
                note=49,  # Lowest C in octave
                enharmonicSpelling=EnharmonicSpelling.NORMAL
            )
        ],
        startTick=0,
        endTick=8
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

