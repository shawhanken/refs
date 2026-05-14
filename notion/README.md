# Notion — Imported Pages

This directory holds Markdown snapshots of external Notion documents that are
referenced during Cowboy / VM design work.

## Sources

| Folder | Notion Page | URL |
|---|---|---|
| [`cowboy-vm-shared/`](./cowboy-vm-shared/index.md) | **Cowboy <> VM Shared Folder** | https://www.notion.so/Cowboy-VM-Shared-Folder-ccbe6c7d52db82acb40d013648a92eb8 |

## Conversion notes

- Fetched via Notion's public API (`loadCachedPageChunkV2` + `syncRecordValues`)
  and converted block-by-block to Markdown.
- 14 pages, 1965 blocks, 19 images snapshotted.
- Image attachments are downloaded into each page-tree's `assets/` folder and
  linked relatively. Filenames are prefixed with the first 8 hex chars of the
  source block's UUID to avoid collisions.
- Each page is annotated with its Notion block id as an HTML comment
  (`<!-- Notion page id: ... -->`) to make round-tripping back to the source
  page easy.
- Sub-pages that themselves contain sub-pages are emitted as `<name>/index.md`;
  leaf sub-pages as `<name>.md`.
- Tables, callouts, code blocks, LaTeX equations, toggles, and nested lists are
  preserved.

## Tree

```
cowboy-vm-shared/
├── index.md                                            (root page)
├── Initial-Questions.md
├── Design-review.md
├── Design-Review-Summary-Cowboy-Input.md
├── Whitepaper-Sections-for-Reconsideration.md
├── Concept-Generation-Phase-2/
│   ├── index.md
│   ├── Runner-Market-Place-Concept-Generation.md
│   └── Timer-GBA-Concept-Generation.md
├── Concept-Selection-Phase-3/
│   ├── index.md
│   ├── Cowboy-Runner-Marketplace-Concept-Selection.md
│   └── Timer-GBA-Concept-Selection.md
├── Slashing---System-Architecture-Objectives.md
├── Slashing---Concept-Generation-Selection.md
├── Relative-Competitor-Analysis.md
├── _analysis/                                          (differential analysis vs CIPs + WP)
│   ├── 00-summary.md                                   (bilingual exec summary + decision register)
│   ├── 01-slashing.md ... 09-new-cips-proposed.md      (per-topic English analysis)
│   └── _index/{cip,wp}-impact-matrix.md
└── assets/                                             (19 images, .png + .svg)
```

## Differential analysis

`_analysis/` compares every reviewer finding (~70 items) against the live
CIPs in `refs/cips/` and the whitepaper at
`refs/whitepaper/2026-03-21_cowboy-technical-whitepaper-revised-v2.md`,
classifying each as actionable / resolved / dropped / defer-to-sim /
policy-decision. Start with `_analysis/00-summary.md`.
