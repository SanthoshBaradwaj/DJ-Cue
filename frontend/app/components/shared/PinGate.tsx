"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError, clearOperatorPin, getOperatorPin, setOperatorPin } from "@/lib/api";

/**
 * Full-page gate for /dj and /present -- both are reachable by anyone with
 * the URL, and /present in particular can flush an event's live data. The
 * PIN is checked server-side on every DJ-only write too (see
 * require_operator_pin in main.py), so this gate is the UI half of that,
 * not the whole story -- finding a route in devtools doesn't skip it.
 *
 * sessionStorage, not localStorage: a shared venue laptop or a TV browser
 * left open shouldn't still be unlocked the next time someone opens it.
 */
export function PinGate({ children }: { children: ReactNode }) {
  const [checking, setChecking] = useState(true);
  const [unlocked, setUnlocked] = useState(false);
  const [pin, setPin] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const stored = getOperatorPin();
    if (!stored) {
      setChecking(false);
      return;
    }
    api.auth
      .verifyPin(stored)
      .then(() => setUnlocked(true))
      .catch(() => clearOperatorPin()) // stale/rotated PIN -- fall through to the entry form
      .finally(() => setChecking(false));
  }, []);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = pin.trim();
    if (!trimmed || verifying) return;
    setVerifying(true);
    setError(null);
    api.auth
      .verifyPin(trimmed)
      .then(() => {
        setOperatorPin(trimmed);
        setUnlocked(true);
      })
      .catch((err) => {
        setError(
          err instanceof ApiError && err.status === 401
            ? "Wrong PIN."
            : "Couldn't reach the server -- try again.",
        );
      })
      .finally(() => setVerifying(false));
  };

  // Avoid a flash of the entry form while the stored PIN is still being verified.
  if (checking) return null;

  if (!unlocked) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-ink px-5">
        <form onSubmit={submit} className="w-full max-w-xs">
          <h1 className="text-center text-2xl font-black tracking-[-0.04em] text-chalk">
            <span style={{ color: "var(--color-cue-1)" }}>DJ</span>-CUE
          </h1>
          <p className="mt-1.5 text-center text-sm text-mist">Enter the operator PIN to continue.</p>
          <input
            type="password"
            inputMode="numeric"
            autoComplete="off"
            autoFocus
            value={pin}
            onChange={(e) => {
              setPin(e.target.value);
              setError(null);
            }}
            placeholder="••••"
            aria-label="Operator PIN"
            className="mt-6 h-14 w-full rounded-2xl border border-ink-line bg-ink-raised px-4 text-center text-2xl tracking-[0.4em] text-chalk outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70"
          />
          <p role="alert" className="mt-2 h-5 text-center text-[13px] font-medium text-danger">
            {error ?? ""}
          </p>
          <button
            type="submit"
            disabled={!pin.trim() || verifying}
            className="tap h-12 w-full rounded-2xl bg-cue-1 text-[15px] font-bold text-ink transition-all duration-150 active:scale-[0.985] disabled:opacity-40"
          >
            {verifying ? "Checking…" : "Unlock"}
          </button>
        </form>
      </div>
    );
  }

  return <>{children}</>;
}
