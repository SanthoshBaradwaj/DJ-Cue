"use client";

import { useCallback, useEffect, useState } from "react";

export interface GuestHistoryEntry {
  id: string;
  text: string;
  waveLabel: string;
  waveSize: number;
  joined: boolean;
  at: number;
}

const KEY = "cue_guest_requests";
const MAX = 10;

function isEntry(value: unknown): value is GuestHistoryEntry {
  if (!value || typeof value !== "object") return false;
  const e = value as Record<string, unknown>;
  return typeof e.id === "string" && typeof e.text === "string";
}

function read(): GuestHistoryEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(isEntry).slice(0, MAX).map((e) => ({
      id: e.id,
      text: e.text,
      waveLabel: typeof e.waveLabel === "string" ? e.waveLabel : "",
      waveSize: typeof e.waveSize === "number" ? e.waveSize : 0,
      joined: e.joined === true,
      at: typeof e.at === "number" ? e.at : 0,
    }));
  } catch {
    return [];
  }
}

/**
 * This session's requests, kept in localStorage so a refresh (or an accidental
 * back-swipe) doesn't wipe the guest's sense of what they already asked for.
 * Reads happen after mount — writing it into the first render would desync
 * hydration.
 */
export function useGuestHistory() {
  const [entries, setEntries] = useState<GuestHistoryEntry[]>([]);

  useEffect(() => {
    setEntries(read());
  }, []);

  const add = useCallback((entry: GuestHistoryEntry) => {
    setEntries((prev) => {
      const next = [entry, ...prev.filter((e) => e.id !== entry.id)].slice(0, MAX);
      try {
        window.localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        /* private mode / quota — the in-memory list still works tonight */
      }
      return next;
    });
  }, []);

  return { entries, add };
}
