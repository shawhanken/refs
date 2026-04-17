# Plan: Add Basefee Change Tracking to bench:all

## Context

`npm run bench:all` currently fetches basefee only to set transaction fee limits (2× safety margin). The actual basefee values (`cycle_basefee`, `cell_basefee`) are never recorded or reported — making it impossible to observe EIP-1559 feedback behavior under load (i.e., whether high-TPS flood causes basefee to rise and then settle).

Goal: capture per-second basefee snapshots during the flood test and per-block snapshots during block monitoring, then surface summary stats (start/end/min/max/delta%) in the JSON report.

---

## Files to Modify

| File | Change |
|------|--------|
| `bench/src/cowboy/types.ts` | Add fields to `TpsSample`, `BlockSample`, and flood/blocks summary sections of `BenchmarkReport` |
| `bench/src/cowboy/flood.ts` | Fetch basefee each second in the stats-sampler interval |
| `bench/src/cowboy/blocks.ts` | Fetch basefee per-block observation |
| `bench/src/cowboy/report.ts` | Compute and emit basefee summary stats |

---

## Step-by-Step Changes

### 1. `types.ts` — Extend interfaces

**`TpsSample`** (after line 166, inside the interface):
```typescript
basefee_cycle: bigint | null;
basefee_cell:  bigint | null;
```

**`BlockSample`** (after line 147, inside the interface):
```typescript
basefee_cycle?: bigint | null;
basefee_cell?:  bigint | null;
```

**`BenchmarkReport`** — add a `basefee` summary sub-object to the `flood` section (alongside existing `peak_confirmed_tps` etc.):
```typescript
basefee_summary?: {
    cycle_start:   number | null;   // first observed value (converted from bigint for JSON)
    cycle_end:     number | null;   // last observed value
    cycle_min:     number | null;
    cycle_max:     number | null;
    cycle_change_pct: number | null; // (end - start) / start × 100
    cell_start:    number | null;
    cell_end:      number | null;
    cell_min:      number | null;
    cell_max:      number | null;
    cell_change_pct: number | null;
};
```

Also add the same `basefee_summary` to the `blocks` section of `BenchmarkReport`.

---

### 2. `flood.ts` — Per-second basefee sampling

Location: stats-sampler `setInterval` callback (line 383).

Change callback from `() => {` to `async () => {`, then before constructing `TpsSample`:
```typescript
const bf = await client.getBasefee().catch(() => null);
```

Add to the `TpsSample` object:
```typescript
basefee_cycle: bf?.cycle_basefee ?? null,
basefee_cell:  bf?.cell_basefee  ?? null,
```

No other changes to flood logic needed. `getBasefee()` already handles errors gracefully (returns null), so failures won't interrupt sampling.

---

### 3. `blocks.ts` — Per-block basefee sampling

Location: inside the block-observation loop where block data is fetched (lines 100-115). The function needs access to a `CowboyClient` instance.

Check whether `client` is already passed to the block monitor function. If not, add it as a parameter.

After fetching block data, fetch basefee:
```typescript
const bf = await client.getBasefee().catch(() => null);
samples[sampleIdx]!.basefee_cycle = bf?.cycle_basefee ?? null;
samples[sampleIdx]!.basefee_cell  = bf?.cell_basefee  ?? null;
```

Update the call sites in `bench.ts` to pass `client` if the signature changes.

---

### 4. `report.ts` — Compute and emit basefee summary

After assembling `floodTimeseries` (line ~198), compute flood basefee summary:
```typescript
function basfeeStats(samples: Array<{basefee_cycle?: bigint|null; basefee_cell?: bigint|null}>) {
    const cycles = samples.map(s => s.basefee_cycle).filter((v): v is bigint => v != null);
    const cells  = samples.map(s => s.basefee_cell ).filter((v): v is bigint => v != null);
    if (!cycles.length) return null;
    const toNum = (b: bigint) => Number(b);
    const pct = (start: number, end: number) =>
        start === 0 ? null : Math.round((end - start) / start * 10000) / 100;
    return {
        cycle_start:      toNum(cycles[0]!),
        cycle_end:        toNum(cycles[cycles.length - 1]!),
        cycle_min:        toNum(cycles.reduce((a, b) => a < b ? a : b)),
        cycle_max:        toNum(cycles.reduce((a, b) => a > b ? a : b)),
        cycle_change_pct: pct(toNum(cycles[0]!), toNum(cycles[cycles.length - 1]!)),
        cell_start:       cells.length ? toNum(cells[0]!) : null,
        cell_end:         cells.length ? toNum(cells[cells.length - 1]!) : null,
        cell_min:         cells.length ? toNum(cells.reduce((a, b) => a < b ? a : b)) : null,
        cell_max:         cells.length ? toNum(cells.reduce((a, b) => a > b ? a : b)) : null,
        cell_change_pct:  cells.length ? pct(toNum(cells[0]!), toNum(cells[cells.length - 1]!)) : null,
    };
}
```

Attach to report:
```typescript
flood: {
    ...existingFloodFields,
    basefee_summary: opts.flood ? basfeeStats(opts.flood.timeseries) : null,
}
blocks: {
    ...existingBlockFields,
    basefee_summary: opts.blockMonitor ? basfeeStats(opts.blockMonitor.samples) : null,
}
```

Raw samples (`raw.block_samples`, flood `timeseries` inside flood section) automatically include the new fields via JSON serialization — no extra work needed.

---

## What the Report Will Gain

```json
"flood": {
  "basefee_summary": {
    "cycle_start": 1,
    "cycle_end": 3,
    "cycle_min": 1,
    "cycle_max": 4,
    "cycle_change_pct": 200.0,
    "cell_start": 1,
    "cell_end": 2,
    ...
  }
}
```

And per-second raw entries will look like:
```json
{ "t_sec": 12, "tps": 847, ..., "basefee_cycle": 3, "basefee_cell": 2 }
```

---

## Verification

1. Run `npm run bench:latency` (quick) — check that report JSON has no new errors
2. Run `npm run bench:flood` — inspect `cowboy-logs/*.json`, verify:
   - `flood.basefee_summary` is present with non-null values
   - `raw` timeseries entries contain `basefee_cycle` / `basefee_cell`
3. Run `npm run bench:blocks` — verify `blocks.basefee_summary` is present
4. Run `npm run bench:all` — verify full report includes both summaries
