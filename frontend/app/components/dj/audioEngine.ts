"use client";

/**
 * Two-deck WebAudio player with an automatic crossfade (M7).
 *
 * This exists so the pitch makes a noise. It is a sandbox, not a DJ tool: the
 * point is that when the DJ taps PLAY on a recommendation, the room hears the
 * floor change, and the change *sounds like* the wave that asked for it.
 *
 * Two sources of sound, in priority order:
 *
 * 1. **A real file**, if `track.audio_file` is set — i.e. someone dropped an
 *    MP3 into `audio/` and the backend matched it to this track.
 * 2. **A synthesised loop**, otherwise. Parameters are derived from the
 *    track's own metadata (bpm, energy, genre, key-ish root), so a bhangra
 *    recommendation reads as dhol-and-minor-pentatonic and a house one reads
 *    as four-on-the-floor with offbeat hats. Deterministic per track id: the
 *    same track sounds the same every time it comes up.
 *
 * Both land on a per-deck gain node, and a decision is always a crossfade
 * between the two decks rather than a cut, because a cut on a PA sounds like a
 * bug and this screen is being watched by investors.
 *
 * Browsers refuse to start audio without a gesture, so nothing here touches an
 * AudioContext until `unlock()` is called from a real click.
 */

import type { Track } from "@/lib/types";
import { apiBase } from "@/lib/api";

export const CROSSFADE_S = 8;

/** How far ahead the step scheduler queues events, and how often it wakes. */
const LOOKAHEAD_S = 0.12;
const TICK_MS = 25;

const STEPS_PER_BAR = 16;

/** Master ceiling. A pitch is loud enough without us clipping the PA. */
const MASTER_GAIN = 0.55;

type Semitones = number[];

// Scales are semitone offsets from the track's root. Minor pentatonic carries
// most of the bhangra/desi register; the others are chosen to sit right under
// their genre without needing real harmony.
const SCALES: Record<string, Semitones> = {
  minor_pentatonic: [0, 3, 5, 7, 10],
  natural_minor: [0, 2, 3, 5, 7, 8, 10],
  harmonic_minor: [0, 2, 3, 5, 7, 8, 11],
  dorian: [0, 2, 3, 5, 7, 9, 10],
  major: [0, 2, 4, 5, 7, 9, 11],
};

interface Character {
  scale: Semitones;
  bassWave: OscillatorType;
  /** Kick on every beat — house, disco, most bhangra floors. */
  fourOnFloor: boolean;
  /** Backbeat feel at half the tempo — hip-hop, R&B. */
  halfTime: boolean;
  /** 0..1 chance of a 16th-note hat. */
  hatDensity: number;
  /** Sustained pad level; carries the chill/romantic end. */
  padLevel: number;
  /** Root note, in MIDI. Low, because this is a bassline. */
  rootMidi: number;
}

/** Cheap deterministic PRNG so a track's loop is identical every time. */
function seeded(seed: string): () => number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i += 1) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return () => {
    h ^= h << 13;
    h ^= h >>> 17;
    h ^= h << 5;
    return ((h >>> 0) % 100000) / 100000;
  };
}

function midiToFreq(midi: number): number {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

function has(list: string[], ...names: string[]): boolean {
  return names.some((n) => list.includes(n));
}

/**
 * Translate catalog metadata into synth parameters.
 *
 * The genre buckets here mirror `app.taxonomy`; anything unrecognised falls
 * through to a neutral four-on-the-floor rather than silence.
 */
function characterOf(track: Track): Character {
  const genres = track.genres ?? [];
  const moods = track.moods ?? [];
  const energy = Math.min(1, Math.max(0, track.energy ?? 0.5));
  const mellow = energy < 0.45 || has(moods, "romantic", "chill", "melancholy");

  const base: Character = {
    scale: SCALES.natural_minor,
    bassWave: "sawtooth",
    fourOnFloor: true,
    halfTime: false,
    hatDensity: 0.25 + energy * 0.5,
    padLevel: mellow ? 0.5 : 0.16,
    rootMidi: 33, // A1
  };

  if (has(genres, "bhangra", "desi_hiphop", "punjabi_pop")) {
    return { ...base, scale: SCALES.minor_pentatonic, bassWave: "square", rootMidi: 33 };
  }
  if (has(genres, "bollywood", "filmi", "ghazal", "sufi", "qawwali")) {
    return {
      ...base,
      scale: mellow ? SCALES.harmonic_minor : SCALES.dorian,
      bassWave: "triangle",
      fourOnFloor: !mellow,
      padLevel: mellow ? 0.62 : 0.24,
      rootMidi: 31,
    };
  }
  if (has(genres, "house", "techno", "edm", "trance", "disco")) {
    return { ...base, scale: SCALES.natural_minor, bassWave: "sawtooth", hatDensity: 0.55 + energy * 0.35 };
  }
  if (has(genres, "hiphop", "rap", "rnb", "trap")) {
    return {
      ...base,
      scale: SCALES.minor_pentatonic,
      bassWave: "sine",
      fourOnFloor: false,
      halfTime: true,
      hatDensity: 0.4 + energy * 0.4,
      rootMidi: 29,
    };
  }
  if (has(genres, "afrobeat", "amapiano", "reggaeton", "latin", "dancehall")) {
    return { ...base, scale: SCALES.dorian, bassWave: "triangle", fourOnFloor: false, rootMidi: 33 };
  }
  if (has(genres, "pop", "rock", "retro")) {
    return { ...base, scale: SCALES.major, bassWave: "triangle" };
  }
  return base;
}

/** One deck: a gain node plus whichever source is currently feeding it. */
class Deck {
  readonly gain: GainNode;
  private ctx: AudioContext;
  private source: AudioBufferSourceNode | null = null;
  private synth: SynthLoop | null = null;

  constructor(ctx: AudioContext, destination: AudioNode) {
    this.ctx = ctx;
    this.gain = ctx.createGain();
    this.gain.gain.value = 0;
    this.gain.connect(destination);
  }

  playBuffer(buffer: AudioBuffer) {
    this.stop();
    const source = this.ctx.createBufferSource();
    source.buffer = buffer;
    source.loop = true;
    source.connect(this.gain);
    source.start();
    this.source = source;
  }

  playSynth(track: Track) {
    this.stop();
    this.synth = new SynthLoop(this.ctx, this.gain, track);
    this.synth.start();
  }

  stop() {
    if (this.source) {
      try {
        this.source.stop();
      } catch {
        // Already stopped; nothing to do.
      }
      this.source.disconnect();
      this.source = null;
    }
    if (this.synth) {
      this.synth.stop();
      this.synth = null;
    }
  }

  /** Ramp this deck's level, cancelling any crossfade already in flight. */
  fadeTo(value: number, seconds: number, now: number) {
    const g = this.gain.gain;
    g.cancelScheduledValues(now);
    g.setValueAtTime(g.value, now);
    g.linearRampToValueAtTime(value, now + Math.max(0.01, seconds));
  }
}

/**
 * A step sequencer that renders a one-bar groove with plain oscillators.
 *
 * Everything is scheduled against `ctx.currentTime` with a short lookahead —
 * timers on the main thread jitter, the audio clock does not, so patterns stay
 * locked even while React is re-rendering the dashboard around it.
 */
class SynthLoop {
  private ctx: AudioContext;
  private out: GainNode;
  private character: Character;
  private stepDur: number;
  private rand: () => number;
  private noise: AudioBuffer;
  private pad: { osc: OscillatorNode[]; gain: GainNode } | null = null;

  private timer: number | null = null;
  private nextStepTime = 0;
  private step = 0;
  private bassPattern: (number | null)[];

  constructor(ctx: AudioContext, out: GainNode, track: Track) {
    this.ctx = ctx;
    this.out = out;
    this.character = characterOf(track);
    this.rand = seeded(track.id || track.title || "cue");

    // Half-time is expressed in the pattern (sparser kicks, longer bass), not
    // in the clock — the grid stays at the track's real tempo so a bridged
    // hip-hop pick still counts in against the outgoing track.
    const bpm = Math.min(180, Math.max(60, track.bpm || 120));
    this.stepDur = 60 / bpm / 4;

    this.noise = SynthLoop.noiseBuffer(ctx);
    this.bassPattern = this.buildBass();
  }

  private static noiseBuffer(ctx: AudioContext): AudioBuffer {
    const length = Math.floor(ctx.sampleRate * 0.4);
    const buffer = ctx.createBuffer(1, length, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < length; i += 1) data[i] = Math.random() * 2 - 1;
    return buffer;
  }

  /** A bar of bass notes drawn from the scale — root-anchored, then wandering. */
  private buildBass(): (number | null)[] {
    const { scale, rootMidi, halfTime } = this.character;
    const out: (number | null)[] = new Array(STEPS_PER_BAR).fill(null);
    const gap = halfTime ? 4 : 2;
    for (let i = 0; i < STEPS_PER_BAR; i += gap) {
      // Beat one is always the root, so the loop has a home to return to.
      if (i === 0) {
        out[i] = rootMidi;
        continue;
      }
      if (this.rand() < (halfTime ? 0.55 : 0.75)) {
        const degree = Math.floor(this.rand() * scale.length);
        const octave = this.rand() < 0.18 ? 12 : 0;
        out[i] = rootMidi + scale[degree] + octave;
      }
    }
    return out;
  }

  start() {
    this.nextStepTime = this.ctx.currentTime + 0.06;
    this.step = 0;
    this.startPad();
    this.tick();
  }

  stop() {
    if (this.timer !== null) {
      clearTimeout(this.timer);
      this.timer = null;
    }
    if (this.pad) {
      const now = this.ctx.currentTime;
      this.pad.gain.gain.cancelScheduledValues(now);
      this.pad.gain.gain.setValueAtTime(this.pad.gain.gain.value, now);
      this.pad.gain.gain.linearRampToValueAtTime(0, now + 0.3);
      const { osc } = this.pad;
      window.setTimeout(() => {
        osc.forEach((o) => {
          try {
            o.stop();
          } catch {
            // Already stopped.
          }
          o.disconnect();
        });
      }, 400);
      this.pad = null;
    }
  }

  private tick = () => {
    const horizon = this.ctx.currentTime + LOOKAHEAD_S;
    while (this.nextStepTime < horizon) {
      this.scheduleStep(this.step % STEPS_PER_BAR, this.nextStepTime);
      this.nextStepTime += this.stepDur;
      this.step += 1;
    }
    this.timer = window.setTimeout(this.tick, TICK_MS);
  };

  private scheduleStep(step: number, when: number) {
    const { fourOnFloor, halfTime, hatDensity } = this.character;
    const onBeat = step % 4 === 0;

    if (fourOnFloor ? onBeat : step === 0 || step === 6 || step === 10) {
      this.kick(when);
    }
    // Backbeat: beat 2 and 4 of the bar.
    if (step === 4 || step === 12) this.snare(when, halfTime ? 0.5 : 0.34);
    if (!onBeat && this.rand() < hatDensity) this.hat(when);

    const note = this.bassPattern[step];
    if (note !== null && note !== undefined) {
      this.bass(when, note, this.stepDur * (halfTime ? 3.2 : 1.7));
    }
  }

  private kick(when: number) {
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(130, when);
    osc.frequency.exponentialRampToValueAtTime(46, when + 0.11);
    gain.gain.setValueAtTime(0.0001, when);
    gain.gain.exponentialRampToValueAtTime(0.9, when + 0.006);
    gain.gain.exponentialRampToValueAtTime(0.0001, when + 0.3);
    osc.connect(gain).connect(this.out);
    osc.start(when);
    osc.stop(when + 0.34);
  }

  private snare(when: number, level: number) {
    const src = this.ctx.createBufferSource();
    const filter = this.ctx.createBiquadFilter();
    const gain = this.ctx.createGain();
    src.buffer = this.noise;
    filter.type = "bandpass";
    filter.frequency.value = 1900;
    filter.Q.value = 0.9;
    gain.gain.setValueAtTime(level, when);
    gain.gain.exponentialRampToValueAtTime(0.0001, when + 0.16);
    src.connect(filter).connect(gain).connect(this.out);
    src.start(when);
    src.stop(when + 0.2);
  }

  private hat(when: number) {
    const src = this.ctx.createBufferSource();
    const filter = this.ctx.createBiquadFilter();
    const gain = this.ctx.createGain();
    src.buffer = this.noise;
    filter.type = "highpass";
    filter.frequency.value = 7600;
    gain.gain.setValueAtTime(0.12 + this.rand() * 0.06, when);
    gain.gain.exponentialRampToValueAtTime(0.0001, when + 0.045);
    src.connect(filter).connect(gain).connect(this.out);
    src.start(when);
    src.stop(when + 0.06);
  }

  private bass(when: number, midi: number, length: number) {
    const osc = this.ctx.createOscillator();
    const filter = this.ctx.createBiquadFilter();
    const gain = this.ctx.createGain();
    osc.type = this.character.bassWave;
    osc.frequency.value = midiToFreq(midi);
    filter.type = "lowpass";
    filter.frequency.setValueAtTime(1500, when);
    filter.frequency.exponentialRampToValueAtTime(360, when + length);
    filter.Q.value = 6;
    gain.gain.setValueAtTime(0.0001, when);
    gain.gain.exponentialRampToValueAtTime(0.38, when + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, when + length);
    osc.connect(filter).connect(gain).connect(this.out);
    osc.start(when);
    osc.stop(when + length + 0.05);
  }

  /** Two detuned saws an octave up — the bed a ballad needs and a banger doesn't. */
  private startPad() {
    const { padLevel, rootMidi, scale } = this.character;
    if (padLevel <= 0.02) return;

    const now = this.ctx.currentTime;
    const gain = this.ctx.createGain();
    const filter = this.ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 1100;
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.linearRampToValueAtTime(padLevel * 0.22, now + 1.6);
    filter.connect(gain).connect(this.out);

    const third = scale[Math.min(2, scale.length - 1)];
    const osc = [0, third, 12].map((offset, i) => {
      const o = this.ctx.createOscillator();
      o.type = "sawtooth";
      o.frequency.value = midiToFreq(rootMidi + 12 + offset);
      o.detune.value = (i - 1) * 7;
      o.connect(filter);
      o.start(now);
      return o;
    });

    this.pad = { osc, gain };
  }
}

export class AudioEngine {
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private decks: [Deck, Deck] | null = null;
  private active = 0;
  private buffers = new Map<string, AudioBuffer>();
  private currentTrackId: string | null = null;
  private muted = false;

  /** True once an AudioContext exists and is running. */
  get ready(): boolean {
    return this.ctx !== null && this.ctx.state === "running";
  }

  /**
   * Create/resume the context. Must be called from a user gesture — browsers
   * silently refuse otherwise, which looks exactly like a broken feature.
   */
  async unlock(): Promise<boolean> {
    try {
      if (!this.ctx) {
        type WithLegacy = typeof globalThis & {
          webkitAudioContext?: typeof AudioContext;
        };
        const Ctor =
          window.AudioContext ?? (globalThis as WithLegacy).webkitAudioContext;
        if (!Ctor) return false;
        const ctx = new Ctor();
        const master = ctx.createGain();
        master.gain.value = this.muted ? 0 : MASTER_GAIN;
        master.connect(ctx.destination);
        this.ctx = ctx;
        this.master = master;
        this.decks = [new Deck(ctx, master), new Deck(ctx, master)];
      }
      if (this.ctx.state === "suspended") await this.ctx.resume();
      return this.ctx.state === "running";
    } catch {
      return false;
    }
  }

  setMuted(muted: boolean) {
    this.muted = muted;
    if (!this.ctx || !this.master) return;
    const now = this.ctx.currentTime;
    const g = this.master.gain;
    g.cancelScheduledValues(now);
    g.setValueAtTime(g.value, now);
    g.linearRampToValueAtTime(muted ? 0 : MASTER_GAIN, now + 0.25);
  }

  /**
   * Crossfade to `track` on the idle deck. Re-calling with the track that is
   * already playing is a no-op, so a `"state"` push that merely repeats
   * now-playing does not restart the music.
   */
  async playTrack(track: Track | null): Promise<void> {
    if (!this.ctx || !this.decks) return;
    if (!track) {
      this.fadeOutAll();
      this.currentTrackId = null;
      return;
    }
    if (track.id === this.currentTrackId) return;
    this.currentTrackId = track.id;

    const buffer = await this.bufferFor(track);
    // An await happened; a newer decision may have landed meanwhile.
    if (this.currentTrackId !== track.id || !this.ctx || !this.decks) return;

    const nextIndex = this.active === 0 ? 1 : 0;
    const incoming = this.decks[nextIndex];
    const outgoing = this.decks[this.active];

    if (buffer) incoming.playBuffer(buffer);
    else incoming.playSynth(track);

    const now = this.ctx.currentTime;
    incoming.fadeTo(1, CROSSFADE_S, now);
    outgoing.fadeTo(0, CROSSFADE_S, now);
    // Let the tail finish before tearing the old source down.
    window.setTimeout(() => outgoing.stop(), (CROSSFADE_S + 0.5) * 1000);
    this.active = nextIndex;
  }

  private fadeOutAll() {
    if (!this.ctx || !this.decks) return;
    const now = this.ctx.currentTime;
    this.decks.forEach((deck) => deck.fadeTo(0, 1.5, now));
    window.setTimeout(() => this.decks?.forEach((d) => d.stop()), 2000);
  }

  /** Decode and memoise a drop-in file, or `null` to fall back to the synth. */
  private async bufferFor(track: Track): Promise<AudioBuffer | null> {
    if (!track.audio_file || !this.ctx) return null;
    const cached = this.buffers.get(track.id);
    if (cached) return cached;
    try {
      const url = `${apiBase()}/audio/${encodeURIComponent(track.audio_file)}`;
      const res = await fetch(url);
      if (!res.ok) return null;
      const decoded = await this.ctx.decodeAudioData(await res.arrayBuffer());
      this.buffers.set(track.id, decoded);
      return decoded;
    } catch {
      // A corrupt or half-copied MP3 must not silence the demo.
      return null;
    }
  }

  dispose() {
    this.decks?.forEach((deck) => deck.stop());
    this.decks = null;
    this.master = null;
    this.buffers.clear();
    const ctx = this.ctx;
    this.ctx = null;
    void ctx?.close().catch(() => undefined);
  }
}
