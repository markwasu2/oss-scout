"use client";

import React from "react";
import { useMemo, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

type ProjectsPayload = {
  generated_at: string;
  count: number;
  facets?: {
    tags?: Record<string, number>;
    source?: Record<string, number>;
    health_label?: Record<string, number>;
  };
  projects: any[];
};

function formatDate(iso: string) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function sourceLabel(source: string) {
  if (source === "huggingface") return "Hugging Face";
  if (source === "github") return "GitHub";
  return source || "Unknown";
}

export default function HomeClient() {
  const searchParams = useSearchParams();
  const [payload, setPayload] = useState<ProjectsPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  // UI state
  const [query, setQuery] = useState("");
  const [source, setSource] = useState<"all" | "github" | "huggingface">("all");
  const [tag, setTag] = useState<string>("all");

  // Hydrate from URL params
  useEffect(() => {
    const q = searchParams.get("q");
    const s = searchParams.get("source");
    const t = searchParams.get("tag");

    if (q) setQuery(q);
    if (s === "github" || s === "huggingface" || s === "all") setSource(s);
    if (t) setTag(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load data (legacy projects.json is what we deploy today)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setError(null);
        const res = await fetch("/data/projects.json", { cache: "no-store" });
        if (!res.ok) {
          throw new Error(`Failed to load /data/projects.json (${res.status})`);
        }
        const data = (await res.json()) as ProjectsPayload;
        if (!cancelled) setPayload(data);
      } catch (e: any) {
        if (!cancelled) setError(e?.message || "Failed to load data");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const availableTags = useMemo(() => {
    const tags = payload?.facets?.tags || {};
    return Object.entries(tags)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 80); // keep UI snappy
  }, [payload]);

  const filtered = useMemo(() => {
    const projects = payload?.projects || [];
    const q = query.trim().toLowerCase();
    return projects.filter((p) => {
      if (source !== "all" && p.source !== source) return false;
      if (tag !== "all" && !(p.tags || []).includes(tag)) return false;
      if (!q) return true;
      const hay = [
        p.name,
        p.full_name,
        p.description,
        (p.topics || []).join(" "),
        (p.tags || []).join(" "),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [payload, query, source, tag]);

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold">OSS Scout</h1>
              <p className="text-sm text-gray-600">
                Discover open-source video, audio, and 3D generation projects.
              </p>
              {payload?.generated_at && (
                <p className="text-xs text-gray-500 mt-1">
                  Updated {formatDate(payload.generated_at)} · {payload.count} items
                </p>
              )}
            </div>
            <div className="flex items-center gap-3">
              <a
                href="/graph"
                className="text-sm font-medium text-blue-600 hover:text-blue-800"
              >
                Contributor Graph →
              </a>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search (name, description, tags)…"
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <select
              value={source}
              onChange={(e) =>
                setSource(e.target.value as "all" | "github" | "huggingface")
              }
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All sources</option>
              <option value="github">GitHub</option>
              <option value="huggingface">Hugging Face</option>
            </select>
            <select
              value={tag}
              onChange={(e) => setTag(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All tags</option>
              {availableTags.map(([t, c]) => (
                <option key={t} value={t}>
                  {t} ({c})
                </option>
              ))}
            </select>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-800 rounded-lg p-4 text-sm">
            {error}
          </div>
        )}

        {!payload && !error && (
          <div className="text-sm text-gray-600">Loading data…</div>
        )}

        {payload && (
          <>
            <div className="text-xs text-gray-500 mb-3">
              Showing {filtered.length} results
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filtered.map((p) => (
                <a
                  key={`${p.source}:${p.id}`}
                  href={p.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block bg-white border border-gray-200 rounded-lg p-4 hover:shadow-sm transition-shadow"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium px-2 py-0.5 rounded bg-gray-100 text-gray-700">
                          {sourceLabel(p.source)}
                        </span>
                        {p.health?.health_label && (
                          <span className="text-xs font-medium px-2 py-0.5 rounded bg-green-50 text-green-700 border border-green-100">
                            {p.health.health_label}
                          </span>
                        )}
                        {p.momentum?.momentum_label_v2 && (
                          <span className="text-xs font-medium px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-100">
                            {p.momentum.momentum_label_v2}
                          </span>
                        )}
                      </div>
                      <h2 className="mt-2 font-semibold text-gray-900">
                        {p.full_name || p.name}
                      </h2>
                      {p.description && (
                        <p className="mt-1 text-sm text-gray-600 line-clamp-3">
                          {p.description}
                        </p>
                      )}
                    </div>

                    <div className="text-right text-xs text-gray-600 whitespace-nowrap">
                      <div>
                        Score{" "}
                        <span className="font-semibold text-gray-900">
                          {p.score ?? "-"}
                        </span>
                      </div>
                      {typeof p.stars === "number" && (
                        <div>⭐ {p.stars.toLocaleString()}</div>
                      )}
                      {typeof p.downloads === "number" && p.downloads > 0 && (
                        <div>⬇️ {p.downloads.toLocaleString()}</div>
                      )}
                      {typeof p.likes === "number" && p.likes > 0 && (
                        <div>♥ {p.likes.toLocaleString()}</div>
                      )}
                    </div>
                  </div>

                  {(p.tags || []).length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {(p.tags || []).slice(0, 8).map((t: string) => (
                        <span
                          key={t}
                          className="text-xs px-2 py-0.5 rounded bg-gray-50 text-gray-700 border border-gray-200"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  )}

                  {p.health?.health_reason && (
                    <div className="mt-3 text-xs text-gray-500">
                      {p.health.health_reason}
                    </div>
                  )}
                </a>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
