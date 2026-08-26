"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type CreditPool = {
  id: number;
  name: string;
  totalCredits: number;
  allocatedCredits: number;
  createdAt: string;
};

export default function Home() {
  const [pools, setPools] = useState<CreditPool[]>([]);
  const [name, setName] = useState("");
  const [totalCredits, setTotalCredits] = useState("1000");
  const [allocationAmounts, setAllocationAmounts] = useState<
    Record<number, string>
  >({});
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadPools = useCallback(async () => {
    const response = await fetch("/api/pools");
    const data = (await response.json()) as { pools: CreditPool[] };
    setPools(data.pools);
    setLoading(false);
  }, []);

  useEffect(() => {
    void loadPools();
  }, [loadPools]);

  async function handleCreatePool(event: FormEvent) {
    event.preventDefault();
    setMessage(null);

    const response = await fetch("/api/pools", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        totalCredits: Number(totalCredits),
      }),
    });

    if (!response.ok) {
      const data = (await response.json()) as { error?: string };
      setMessage(data.error ?? "Failed to create pool");
      return;
    }

    setName("");
    setTotalCredits("1000");
    setMessage("Credit pool created");
    await loadPools();
  }

  async function handleAllocate(poolId: number) {
    setMessage(null);
    const amount = Number(allocationAmounts[poolId] ?? "0");

    const response = await fetch(`/api/pools/${poolId}/allocate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ amount }),
    });

    const data = (await response.json()) as { error?: string };
    if (!response.ok) {
      setMessage(data.error ?? "Allocation failed");
      return;
    }

    setAllocationAmounts((current) => ({ ...current, [poolId]: "" }));
    setMessage(`Allocated ${amount} credits`);
    await loadPools();
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex max-w-5xl flex-col gap-8 px-6 py-12">
        <header className="space-y-2">
          <p className="text-sm uppercase tracking-[0.2em] text-emerald-400">
            Credit Pool
          </p>
          <h1 className="text-4xl font-semibold">Shared credit pools</h1>
          <p className="max-w-2xl text-slate-300">
            Create pools, track total credits, and allocate them to members.
          </p>
        </header>

        {message ? (
          <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-4 py-3 text-emerald-200">
            {message}
          </div>
        ) : null}

        <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
          <h2 className="mb-4 text-xl font-medium">Create a pool</h2>
          <form
            className="grid gap-4 md:grid-cols-[2fr_1fr_auto]"
            onSubmit={handleCreatePool}
          >
            <input
              className="rounded-lg border border-slate-700 bg-slate-950 px-4 py-3"
              placeholder="Pool name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
            />
            <input
              className="rounded-lg border border-slate-700 bg-slate-950 px-4 py-3"
              type="number"
              min="1"
              placeholder="Total credits"
              value={totalCredits}
              onChange={(event) => setTotalCredits(event.target.value)}
              required
            />
            <button
              className="rounded-lg bg-emerald-500 px-5 py-3 font-medium text-slate-950 hover:bg-emerald-400"
              type="submit"
            >
              Create pool
            </button>
          </form>
        </section>

        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-medium">Pools</h2>
            <span className="text-sm text-slate-400">
              {loading ? "Loading..." : `${pools.length} total`}
            </span>
          </div>

          {pools.length === 0 && !loading ? (
            <div className="rounded-2xl border border-dashed border-slate-800 px-6 py-10 text-center text-slate-400">
              No pools yet. Create one to get started.
            </div>
          ) : (
            <div className="grid gap-4">
              {pools.map((pool) => {
                const available = pool.totalCredits - pool.allocatedCredits;
                return (
                  <article
                    key={pool.id}
                    className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6"
                  >
                    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                      <div>
                        <h3 className="text-2xl font-medium">{pool.name}</h3>
                        <p className="text-sm text-slate-400">
                          Created {new Date(pool.createdAt).toLocaleString()}
                        </p>
                      </div>
                      <div className="grid grid-cols-3 gap-3 text-center md:min-w-[360px]">
                        <div className="rounded-xl bg-slate-950 px-4 py-3">
                          <p className="text-xs uppercase text-slate-400">
                            Total
                          </p>
                          <p className="text-lg font-semibold">
                            {pool.totalCredits}
                          </p>
                        </div>
                        <div className="rounded-xl bg-slate-950 px-4 py-3">
                          <p className="text-xs uppercase text-slate-400">
                            Allocated
                          </p>
                          <p className="text-lg font-semibold">
                            {pool.allocatedCredits}
                          </p>
                        </div>
                        <div className="rounded-xl bg-slate-950 px-4 py-3">
                          <p className="text-xs uppercase text-slate-400">
                            Available
                          </p>
                          <p className="text-lg font-semibold text-emerald-400">
                            {available}
                          </p>
                        </div>
                      </div>
                    </div>

                    <div className="mt-4 flex flex-col gap-3 md:flex-row">
                      <input
                        className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-4 py-3"
                        type="number"
                        min="1"
                        max={available}
                        placeholder="Credits to allocate"
                        value={allocationAmounts[pool.id] ?? ""}
                        onChange={(event) =>
                          setAllocationAmounts((current) => ({
                            ...current,
                            [pool.id]: event.target.value,
                          }))
                        }
                      />
                      <button
                        className="rounded-lg border border-emerald-500/40 px-5 py-3 font-medium text-emerald-300 hover:bg-emerald-500/10 disabled:cursor-not-allowed disabled:opacity-50"
                        type="button"
                        disabled={available <= 0}
                        onClick={() => void handleAllocate(pool.id)}
                      >
                        Allocate credits
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
