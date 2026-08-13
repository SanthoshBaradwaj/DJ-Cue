"use client";

interface Vibe {
  label: string;
  emoji: string;
  text: string;
}

/**
 * Most guests will never type. Six taps that cover the floor's real spread —
 * this is the path that gets a request in under fifteen seconds.
 */
const VIBES: Vibe[] = [
  { label: "Bhangra", emoji: "🔥", text: "high-energy punjabi bhangra" },
  { label: "Slow & romantic", emoji: "💗", text: "something slow and romantic" },
  { label: "90s throwback", emoji: "📼", text: "90s throwback bangers" },
  { label: "Hip-hop", emoji: "🎤", text: "hip-hop that hits hard" },
  { label: "House", emoji: "🌀", text: "house music, keep it moving" },
  { label: "Something new", emoji: "✨", text: "something new i haven't heard yet" },
];

export default function VibeChips({
  onPick,
  disabled,
}: {
  onPick: (text: string) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {VIBES.map((vibe) => (
        <button
          key={vibe.label}
          type="button"
          disabled={disabled}
          onClick={() => onPick(vibe.text)}
          className="tap flex items-center gap-2 rounded-full border border-ink-line bg-ink-card/70 px-4 text-[15px] font-medium text-chalk/90 transition-colors duration-150 active:bg-ink-line/80 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cue-2/70"
        >
          <span aria-hidden="true" className="text-base leading-none">
            {vibe.emoji}
          </span>
          {vibe.label}
        </button>
      ))}
    </div>
  );
}
