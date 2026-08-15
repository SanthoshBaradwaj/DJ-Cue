"use client";

import { GENRES } from "./genres";
import { haptic } from "./motion";

/**
 * Screen 1 of the guest flow: one tap, no typing.
 *
 * Big thumb-sized buttons grouped North/South India so a guest scanning the
 * QR in a dark, loud room can find their language in under a second — no
 * reading, no thinking.
 */
export default function GenreGrid({
  eventLine,
  onPick,
}: {
  eventLine: string;
  onPick: (genreKey: string) => void;
}) {
  const north = GENRES.filter((g) => g.region === "north");
  const south = GENRES.filter((g) => g.region === "south");

  const pick = (key: string) => {
    haptic(12);
    onPick(key);
  };

  return (
    <div className="flex flex-col animate-rise">
      <header className="flex items-baseline justify-between gap-3">
        <span className="bg-gradient-to-r from-cue-1 via-cue-2 to-cue-3 bg-clip-text text-[15px] font-bold tracking-[0.42em] text-transparent">
          DJ-CUE
        </span>
        <span className="flex items-center gap-2 text-[13px] text-mist">
          <span
            aria-hidden="true"
            className="relative flex h-1.5 w-1.5 shrink-0 rounded-full bg-go"
          >
            <span className="absolute -inset-1 rounded-full bg-go/40 animate-pulse-ring" />
          </span>
          <span className="truncate">{eventLine}</span>
        </span>
      </header>

      <h1 className="mt-7 text-[28px] leading-[1.15] font-semibold tracking-[-0.02em] text-chalk">
        What&apos;s your sound tonight?
      </h1>
      <p className="mt-2 text-[15px] text-mist">Pick a genre to request a song.</p>

      <GenreSection title="North India" genres={north} onPick={pick} delay={80} />
      <GenreSection title="South India" genres={south} onPick={pick} delay={160} />
    </div>
  );
}

function GenreSection({
  title,
  genres,
  onPick,
  delay,
}: {
  title: string;
  genres: { key: string; label: string }[];
  onPick: (key: string) => void;
  delay: number;
}) {
  return (
    <section
      className="mt-8 animate-rise"
      style={{ animationDelay: `${delay}ms`, animationFillMode: "backwards" }}
    >
      <h2 className="mb-3 text-[13px] tracking-[0.14em] text-mist/80 uppercase">{title}</h2>
      <div className="grid grid-cols-2 gap-3">
        {genres.map((g) => (
          <button
            key={g.key}
            type="button"
            onClick={() => onPick(g.key)}
            className="tap flex h-24 flex-col items-center justify-center gap-1 rounded-2xl border border-ink-line bg-ink-card/80 px-3 text-center transition-all duration-150 active:scale-[0.97] active:border-cue-1/60 active:bg-cue-1/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70"
          >
            <span className="text-[19px] font-semibold tracking-[-0.01em] text-chalk">
              {g.label}
            </span>
          </button>
        ))}
      </div>
    </section>
  );
}
