from pathlib import Path
from typing import Optional
from argparse import ArgumentParser
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


