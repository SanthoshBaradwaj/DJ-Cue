"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { api, ApiError, clearPin, getPin, setPin, type PinRole } from "@/lib/api";

const ROLE_LABEL: Record<PinRole, string> = {
  dj: "the DJ PIN",
  present: "the presenter PIN",
};

/**
 * Full-page gate for /dj and /present -- both are reachable by anyone with
 * the URL, and /present in particular can flush an event's live data. Each
 * page has its own independent PIN (see require_dj_pin / require_present_pin
 * in main.py), checked server-side on every write for that role too, so
 * this gate is the UI half of that, not the whole story -- finding a route
 * in devtools doesn't skip it, and knowing one page's PIN doesn't unlock
 * the other.
 *
 * sessionStorage, not localStorage: a shared venue laptop or a TV browser
 * left open shouldn't still be unlocked the next time someone opens it.
 */
export function PinGate({ role, children }: { role: PinRole; children: ReactNode }) {
  const [checking, setChecking] = useState(true);
  const [unlocked, setUnlocked] = useState(false);
  const [pinInput, setPinInput] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const stored = getPin(role);
    if (!stored) {
      setChecking(false);
      return;
    }
    api.auth
      .verifyPin(stored, role)
      .then(() => setUnlocked(true))
      .catch(() => clearPin(role)) // stale/rotated PIN -- fall through to the entry form
      .finally(() => setChecking(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- role is fixed per page, never changes across this component's lifetime
  }, []);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = pinInput.trim();
    if (!trimmed || verifying) return;
    setVerifying(true);
    setError(null);
    api.auth
      .verifyPin(trimmed, role)
      .then(() => {
        setPin(role, trimmed);
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
          <p className="mt-1.5 text-center text-sm text-mist">
            Enter {ROLE_LABEL[role]} to continue.
          </p>
          <input
            type="password"
            inputMode="numeric"
            autoComplete="off"
            autoFocus
            value={pinInput}
            onChange={(e) => {
              setPinInput(e.target.value);
              setError(null);
            }}
            placeholder="••••"
            aria-label={role === "dj" ? "DJ PIN" : "Presenter PIN"}
            className="mt-6 h-14 w-full rounded-2xl border border-ink-line bg-ink-raised px-4 text-center text-2xl tracking-[0.4em] text-chalk outline-none focus-visible:ring-2 focus-visible:ring-cue-1/70"
          />
          <p role="alert" className="mt-2 h-5 text-center text-[13px] font-medium text-danger">
            {error ?? ""}
          </p>
          <button
            type="submit"
            disabled={!pinInput.trim() || verifying}
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
