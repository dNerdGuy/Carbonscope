"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuth } from "@/lib/auth-context";
import { PageSkeleton } from "@/components/Skeleton";
import {
  getIndustryBenchmarks,
  getPeerComparison,
  type IndustryBenchmark,
  type PeerComparison,
} from "@/lib/api";

export default function BenchmarksPage() {
  useDocumentTitle("Benchmarks");
  const { user, loading } = useAuth();
  const router = useRouter();
  const [benchmarks, setBenchmarks] = useState<IndustryBenchmark | null>(null);
  const [peers, setPeers] = useState<PeerComparison | null>(null);
  const [industry, setIndustry] = useState("technology");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!loading && !user) router.push("/login");
  }, [user, loading, router]);

  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        const [b, p] = await Promise.all([
          getIndustryBenchmarks(industry),
          getPeerComparison(),
        ]);
        setBenchmarks(b);
        setPeers(p);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load benchmarks");
      }
    })();
  }, [user, industry]);

  if (loading) return <PageSkeleton />;
  if (!user) return null;

  return (
    <main className="mx-auto max-w-5xl p-8">
      <div className="mb-8 flex items-center justify-between">
        <h1 className="text-3xl font-bold">Industry Benchmarks</h1>
        <select
          className="input w-auto"
          value={industry}
          onChange={(e) => setIndustry(e.target.value)}
          aria-label="Select industry"
        >
          {[
            "technology",
            "manufacturing",
            "finance",
            "energy",
            "retail",
            "healthcare",
          ].map((ind) => (
            <option key={ind} value={ind}>
              {ind.charAt(0).toUpperCase() + ind.slice(1)}
            </option>
          ))}
        </select>
      </div>

      {error && (
        <p className="mb-4 rounded bg-red-900/30 p-3 text-red-400">{error}</p>
      )}

      {/* Benchmark metrics */}
      {benchmarks && (
        <section className="mb-8">
          <h2 className="mb-4 text-xl font-semibold">
            {industry.charAt(0).toUpperCase() + industry.slice(1)} Benchmarks
          </h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {Object.entries(benchmarks)
              .filter(
                ([, val]) =>
                  typeof val === "number" || typeof val === "string",
              )
              .map(([key, val]) => (
                <div key={key} className="card">
                  <p className="text-sm text-[var(--muted)]">
                    {key.replace(/_/g, " ")}
                  </p>
                  <p className="mt-1 text-2xl font-bold">
                    {typeof val === "number"
                      ? val.toLocaleString()
                      : String(val)}
                  </p>
                </div>
              ))}
          </div>
        </section>
      )}

      {/* Peer comparison */}
      {peers && (
        <section>
          <h2 className="mb-4 text-xl font-semibold">Peer Comparison</h2>
          <div className="overflow-x-auto rounded-lg border border-[var(--card-border)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-[var(--card)] text-[var(--muted)]">
                <tr>
                  {Object.entries(peers)
                    .filter(
                      ([, val]) =>
                        typeof val === "number" || typeof val === "string",
                    )
                    .map(([key]) => (
                      <th key={key} className="px-4 py-3">
                        {key.replace(/_/g, " ")}
                      </th>
                    ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--card-border)]">
                <tr>
                  {Object.entries(peers)
                    .filter(
                      ([, val]) =>
                        typeof val === "number" || typeof val === "string",
                    )
                    .map(([key, val]) => (
                      <td key={key} className="px-4 py-3">
                        {typeof val === "number"
                          ? val.toLocaleString()
                          : String(val)}
                      </td>
                    ))}
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
