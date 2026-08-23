"use client";

import { useState } from "react";
import type { GenreBucketView, SongRequest } from "@/lib/types";
import { BucketCard } from "./BucketCard";
import { BucketDetailModal } from "./BucketDetailModal";

/**
 * The genre-quota chart: one column per configured bucket, each with a
 * fixed number of slots (`bucket.requests.length`, already padded with
 * nulls by the backend). Only rendered when the event has genre_buckets
 * configured -- see dj/page.tsx, which falls back to the flat ranked list
 * for every event that hasn't opted in.
 */
export function BucketBoard({
  buckets,
  onPlayed,
  onDismiss,
}: {
  buckets: GenreBucketView[];
  onPlayed: (requestId: string) => void;
  onDismiss: (requestId: string) => void;
}) {
  const [expanded, setExpanded] = useState<SongRequest | null>(null);

  return (
    <>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {buckets.map((bucket) => (
          <div key={bucket.label} className="flex flex-col gap-2">
            <p className="px-1 text-[14px] font-semibold uppercase tracking-[0.12em] text-mist/70">
              {bucket.label}
            </p>
            {bucket.requests.map((request, i) => (
              <BucketCard
                key={request?.id ?? `${bucket.label}-empty-${i}`}
                request={request}
                onExpand={() => request && setExpanded(request)}
                onPlayed={() => request && onPlayed(request.id)}
                onDismiss={() => request && onDismiss(request.id)}
              />
            ))}
          </div>
        ))}
      </div>

      {expanded && (
        <BucketDetailModal
          request={expanded}
          onClose={() => setExpanded(null)}
          onPlayed={() => {
            onPlayed(expanded.id);
            setExpanded(null);
          }}
          onDismiss={() => {
            onDismiss(expanded.id);
            setExpanded(null);
          }}
        />
      )}
    </>
  );
}
