"use client";

import { useEffect, useRef } from "react";
import RotatingPlaceholder from "./RotatingPlaceholder";
import VibeChips from "./VibeChips";

export default function RequestComposer({
  text,
  onTextChange,
  onSubmit,
  pending,
  error,
  eventLine,
}: {
  text: string;
  onTextChange: (text: string) => void;
  onSubmit: () => void;
  pending: boolean;
  error: string | null;
  eventLine: string;
}) {
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Autofocus on mount and whenever we come back from a confirmation, so the
  // second request costs nothing. iOS may withhold the keyboard without a
  // gesture; the caret placement still saves a tap.
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const canSend = text.trim().length > 0 && !pending;

  return (
    <div className="flex flex-col animate-rise">
      <header className="flex items-baseline justify-between gap-3">
        <span className="bg-gradient-to-r from-cue-1 via-cue-2 to-cue-3 bg-clip-text text-[15px] font-bold tracking-[0.42em] text-transparent">
          CUE
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

      <form
        className="mt-7 flex flex-col"
        onSubmit={(e) => {
          e.preventDefault();
          if (canSend) onSubmit();
        }}
      >
        <label
          htmlFor="cue-request"
          className="block text-[28px] leading-[1.15] font-semibold tracking-[-0.02em] text-chalk"
        >
          What do you want to hear?
        </label>

        <div className="relative mt-4 card p-5 transition-shadow duration-200 focus-within:ring-2 focus-within:ring-cue-1/60">
          <RotatingPlaceholder paused={text.length > 0} />
          <textarea
            id="cue-request"
            ref={inputRef}
            value={text}
            onChange={(e) => onTextChange(e.target.value)}
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                !e.shiftKey &&
                !e.nativeEvent.isComposing
              ) {
                e.preventDefault();
                if (canSend) onSubmit();
              }
            }}
            rows={3}
            maxLength={280}
            autoComplete="off"
            autoCapitalize="none"
            autoCorrect="on"
            spellCheck={false}
            enterKeyHint="send"
            disabled={pending}
            /* 22px: comfortably over the 16px floor that triggers iOS zoom. */
            className="relative block h-[132px] w-full resize-none bg-transparent text-[22px] leading-[1.35] font-medium tracking-[-0.01em] text-chalk caret-cue-1 outline-none disabled:opacity-70"
          />
        </div>

        {error ? (
          <div
            role="alert"
            className="mt-3 flex items-center justify-between gap-3 rounded-xl border border-hold/40 bg-hold/10 px-4 py-3 text-[14px] text-chalk/90 animate-rise"
          >
            <span className="min-w-0">{error}</span>
            <button
              type="submit"
              className="shrink-0 rounded-lg px-3 py-1.5 text-[14px] font-semibold text-hold underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-hold/70"
            >
              Retry
            </button>
          </div>
        ) : null}

        <button
          type="submit"
          disabled={!canSend}
          className="tap mt-4 flex h-14 w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-cue-1 to-cue-2 text-[18px] font-semibold text-white shadow-[0_10px_40px_-12px_rgba(255,45,120,0.75)] transition-all duration-150 active:scale-[0.985] disabled:cursor-not-allowed disabled:bg-none disabled:bg-ink-card disabled:text-mist disabled:shadow-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-chalk/80 focus-visible:ring-offset-2 focus-visible:ring-offset-ink"
        >
          {pending ? (
            <>
              <span
                aria-hidden="true"
                className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-white/35 border-t-white"
              />
              Sending
            </>
          ) : (
            "Send it to the DJ"
          )}
        </button>
      </form>

      <div className="mt-7">
        <p className="mb-3 text-[13px] tracking-[0.14em] text-mist/80 uppercase">
          Or tap a vibe
        </p>
        <VibeChips onPick={onTextChange} disabled={pending} />
      </div>
    </div>
  );
}
