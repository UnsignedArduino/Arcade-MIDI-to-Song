# https://github.com/microsoft/pxt/blob/master/pxtlib/music.ts

from typing import Optional, List
from struct import pack
from dataclasses import dataclass
from enum import Enum


@dataclass
class Envelope:
    attack: int
    decay: int
    sustain: int
    release: int
    amplitude: int


@dataclass
class LFO:
    frequency: int
    amplitude: int


@dataclass
class Instrument:
    waveform: int
    ampEnvelope: Envelope
    pitchEnvelope: Optional[Envelope] = None
    ampLFO: Optional[LFO] = None
    pitchLFO: Optional[LFO] = None
    octave: Optional[int] = None


@dataclass
class SongInfo:
    measures: int
    beatsPerMeasure: int
    beatsPerMinute: int
    ticksPerBeat: int


class EnharmonicSpelling(Enum):
    NORMAL = "normal"
    FLAT = "flat"
    SHARP = "sharp"


@dataclass
class Note:
    note: int
    enharmonicSpelling: EnharmonicSpelling


@dataclass
class NoteEvent:
    notes: List[Note]
    startTick: int
    endTick: int


@dataclass
class DrumSoundStep:
    waveform: int
    frequency: int
    volume: int
    duration: int


@dataclass
class DrumInstrument:
    startFrequency: int
    startVolume: int
    steps: List[DrumSoundStep]


@dataclass
class Track:
    instrument: Instrument
    id: int
    notes: List[NoteEvent]
    name: Optional[str] = None
    iconURI: Optional[str] = None
    drums: Optional[List[DrumInstrument]] = None


@dataclass
class Song(SongInfo):
    tracks: List[Track]


def get8BitNumber(num: Optional[int]) -> bytes:
    return bytes([0 if num is None else num])


def get16BitNumber(num: Optional[int]) -> bytes:
    return pack("<h", 0 if num is None else num)


def encodeNote(note: Note, instrumentOctave: int, isDrumTrack: bool) -> bytes:
    if isDrumTrack:
        return bytes([note.note])

    flags = 0
    if note.enharmonicSpelling == EnharmonicSpelling.FLAT:
        flags = 1
    elif note.enharmonicSpelling == EnharmonicSpelling.SHARP:
        flags = 2

    try:
        return bytes(
            [(note.note - (instrumentOctave - 2) * 12) | (flags << 6)])
    except ValueError:
        raise ValueError(f"{note.note} generates invalid byte "
                         f"{(note.note - (instrumentOctave - 2) * 12) | (flags << 6)}")


def encodeNoteEvent(event: NoteEvent, instrumentOctave: int,
                    isDrumTrack: bool) -> bytes:
    out = bytearray()
    out += get16BitNumber(event.startTick)
    out += get16BitNumber(event.endTick)
    out.append(len(event.notes))
    for note in event.notes:
        out += encodeNote(note, instrumentOctave, isDrumTrack)
    return out


def encodeInstrument(instrument: Instrument) -> bytes:
    out = bytearray()
    out.append(instrument.waveform)
    out += get16BitNumber(instrument.ampEnvelope.attack)
    out += get16BitNumber(instrument.ampEnvelope.decay)
    out += get16BitNumber(instrument.ampEnvelope.sustain)
    out += get16BitNumber(instrument.ampEnvelope.release)
    out += get16BitNumber(instrument.ampEnvelope.amplitude)
    if instrument.pitchEnvelope is None:
        for _ in range(5):
            out += get16BitNumber(0)
    else:
        out += get16BitNumber(instrument.pitchEnvelope.attack)
        out += get16BitNumber(instrument.pitchEnvelope.decay)
        out += get16BitNumber(instrument.pitchEnvelope.sustain)
        out += get16BitNumber(instrument.pitchEnvelope.release)
        out += get16BitNumber(instrument.pitchEnvelope.amplitude)
    out.append(0 if instrument.ampLFO is None else instrument.ampLFO.frequency)
    out += get16BitNumber(0 if instrument.ampLFO is None else instrument.ampLFO.amplitude)
    out.append(0 if instrument.pitchLFO is None else instrument.pitchLFO.frequency)
    out += get16BitNumber(0 if instrument.pitchLFO is None else instrument.pitchLFO.amplitude)
    out.append(instrument.octave)
    return out


def encodeMelodicTrack(track: Track) -> bytes:
    encodedInstrument = encodeInstrument(track.instrument)
    encodedNotes = [
        encodeNoteEvent(n, track.instrument.octave, False) for n in track.notes
    ]
    noteLength = sum([len(e) for e in encodedNotes])

    out = bytearray()
    out.append(track.id)
    out.append(0)
    out += get16BitNumber(len(encodedInstrument))
    out += encodedInstrument
    out += get16BitNumber(noteLength)
    for note in encodedNotes:
        out += note
    return out


def encodeTrack(track: Track) -> bytes:
    if track.drums is not None:
        raise NotImplementedError
        # return encodeDrumTrack(track)
    else:
        return encodeMelodicTrack(track)


def encodeSong(song: Song) -> bytes:
    encodedTracks = list(
        map(
            encodeTrack,
            filter(
                lambda track: len(track.notes) > 0,
                song.tracks
            )
        )
    )

    out = bytearray()
    out.append(0)
    out += get16BitNumber(song.beatsPerMinute)
    out.append(song.beatsPerMeasure)
    out.append(song.ticksPerBeat)
    out.append(song.measures)
    out.append(len(encodedTracks))
    for track in encodedTracks:
        out += track
    return out


def getEmptySong(measures: int) -> Song:
    return Song(
        ticksPerBeat=8,
        beatsPerMeasure=4,
        beatsPerMinute=120,
        measures=measures,
        tracks=[
            Track(
                id=0, name="Dog", notes=[],
                iconURI="/static/music-editor/dog.png",
                instrument=Instrument(
                    waveform=1,
                    octave=4,
                    ampEnvelope=Envelope(
                        attack=10,
                        decay=100,
                        sustain=500,
                        release=100,
                        amplitude=1024
                    ),
                    pitchLFO=LFO(
                        frequency=5,
                        amplitude=0
                    )
                )
            )
        ]
    )
