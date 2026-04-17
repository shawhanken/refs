# Direction B: Periodic Receipt Pruning

## Context

After Direction A (receipt struct shrink), RSS still grows at ~3.58MB/s and `apply_batch_ms` increases over time. Root cause: QMDB `AnyVariableDb` (used for `tx_receipts` and `tx_index`) stores unique keys that are never overwritten, so `prune_all()` does nothing. Receipts and tx_index entries accumulate forever, growing the mmap footprint. `prune_receipts()` already exists in `process_block.rs` — it issues logical deletes. We just need to call it periodically.

**Goal:** Every `SYNC_INTERVAL_BLOCKS`, prune receipts older than `KEEP_RECEIPTS_BLOCKS` in a bounded batch. This caps receipt DB size and stabilizes `apply_batch_ms` long-term.

---

## Files to Modify

### 1. `storage/src/blockchain_storage.rs` — Add cursor field

In the `BlockchainStorage` struct, add:
```rust
pub receipt_prune_cursor: u64,   // last block height whose receipts have been pruned
```
Initialize to `0` in `BlockchainStorage::new()` and any other constructors / test helpers.

### 2. `storage/src/process_block.rs` — Add `prune_old_receipts_batch()`

Add alongside existing `prune_receipts()`:

```rust
pub async fn prune_old_receipts_batch(
    &mut self,
    keep_blocks: u64,
    batch_size: u64,
) -> Result<usize, Error> {
    let prune_up_to = self.current_height.saturating_sub(keep_blocks);
    if self.receipt_prune_cursor >= prune_up_to {
        return Ok(0);
    }
    let start = self.receipt_prune_cursor + 1;
    let end = (start + batch_size - 1).min(prune_up_to);
    let mut tx_hashes = Vec::new();
    for h in start..=end {
        if let Some(block) = self.marshal.get_block(Identifier::Height(h)).await {
            for tx in &block.transactions {
                use commonware_cryptography::Digestible;
                tx_hashes.push(tx.digest());
            }
        }
    }
    let pruned = self.prune_receipts(&tx_hashes).await?;
    self.receipt_prune_cursor = end;
    Ok(pruned)
}
```

`Identifier` and `marshal` are already in scope in this file.

### 3. `chain/src/application.rs` — Constants + extend sync_storage closure

Add near `SYNC_INTERVAL_BLOCKS` (line 62):
```rust
const KEEP_RECEIPTS_BLOCKS: u64 = 10_000;
const RECEIPT_PRUNE_BATCH: u64 = 200;
```

In the `sync_storage` closure (lines 240-257), add after `prune_all()`:
```rust
{
    let mut storage = storage.write().await;
    storage.prune_old_receipts_batch(KEEP_RECEIPTS_BLOCKS, RECEIPT_PRUNE_BATCH)
        .await
        .map_err(|e| format!("{}", e))?;
}
```

---

## Verification

1. **Compile**: `cargo build --workspace` — must compile cleanly.
2. **Tests**: `cargo test --workspace` — all tests pass.
3. **Devnet restart**: `./scripts/restart_validator.sh` (clears chain data).
4. **Benchmark**: After >10,000 blocks observe:
   - RSS growth rate plateaus (stops growing once pruning catches up)
   - `apply_batch_ms` stabilizes rather than slowly creeping up
5. **Smoke test**: `curl localhost:4000/receipt/<old_hash>` — returns 404 for pruned receipts (expected); recent receipts return normally.

---

# Direction A: Reduce TransactionReceipt Storage Size (COMPLETED)

## Context

`TransactionReceipt` currently embeds a full `Transaction` copy (~200B) and an always-present `bloom: [u8; 256]` (256B). For pure token transfers (the vast majority of benchmark traffic) the bloom is always all-zeros — wasted space. Together these account for ~450B of the ~600B per receipt stored in QMDB.

**Goal:** Replace `transaction: Transaction` with `tx_hash: Sha256Digest` (32B) and make `bloom: Option<[u8; 256]>` (1B when None). Reduces each receipt from ~600B to ~150B.

**Expected impact:**
- `apply_batch_ms`: ~56ms → ~15ms (fewer bytes written to QMDB per block)
- RSS growth rate: ~4MB/s → ~1MB/s
- Still linear growth (QMDB AnyVariableDb never prunes unique keys) — a full fix would need periodic receipt pruning

**Constraint:** `compute_receipt_root()` hashes `receipt.encode()` — this is a protocol-breaking change. Devnet chain restart required.

---

## Files to Modify

### 1. `storage/src/types.rs` — Struct, codec, rlp, tests

**Struct** (lines 436–463):
```rust
// Before
pub transaction: Transaction,
pub bloom: [u8; 256],

// After
pub tx_hash: Sha256Digest,
pub bloom: Option<[u8; 256]>,
```

**Write** (lines 465–494):
- Replace `self.transaction.write(writer)` → `self.tx_hash.write(writer)`
- Replace `writer.put_slice(&self.bloom)` →
  ```rust
  match &self.bloom {
      Some(b) => { 1u8.write(writer); writer.put_slice(b); }
      None    => { 0u8.write(writer); }
  }
  ```

**Read** (lines 496–591):
- Replace `let transaction = Transaction::read(reader)?` → `let tx_hash = Sha256Digest::read(reader)?`
- Remove the `tx_type` fallback that references `transaction.instruction.tx_type()`:
  ```rust
  let (tx_type, tx_sub_type) = if reader.has_remaining() {
      (u8::read(reader)?, u8::read(reader)?)
  } else {
      (0u8, 0u8) // safe default, devnet-only
  };
  ```
- Replace bloom read:
  ```rust
  let bloom = if reader.has_remaining() {
      match u8::read(reader)? {
          1 => {
              let mut buf = [0u8; 256];
              if reader.remaining() >= 256 { reader.copy_to_slice(&mut buf); Some(buf) }
              else { None }
          }
          _ => None,
      }
  } else { None };
  ```
- In the `Ok(Self { ... })` block: `tx_hash` instead of `transaction`

**EncodeSize** (lines 594–621):
- Replace `self.transaction.encode_size()` → `self.tx_hash.encode_size()`
- Replace `+ 256 // bloom` → `+ 1 + if self.bloom.is_some() { 256 } else { 0 }`

**rlp_encode** (line 664):
- Replace `let tx_hash = self.transaction.digest();` → `let tx_hash = self.tx_hash;`
- Replace `rlp::encode_bytes(&self.bloom)` → `rlp::encode_bytes(self.bloom.as_deref().unwrap_or(&[0u8; 256]))`

**Inline tests** (lines ~800, ~855, ~904):
- Each `TransactionReceipt { transaction: tx, ... bloom: [0u8; 256] }` →
  `TransactionReceipt { tx_hash: tx.digest(), ... bloom: None }`

---

### 2. `storage/src/speculative.rs` — Receipt construction (lines 407–426)

```rust
// Before
let receipt = TransactionReceipt {
    transaction: tx.clone(),
    ...
    bloom: compute_bloom(events),
    ...
};

// After
let receipt = TransactionReceipt {
    tx_hash,          // already computed above as `let tx_hash = tx.digest();`
    ...
    bloom: if events.is_empty() { None } else { Some(compute_bloom(events)) },
    ...
};
```

---

### 3. `storage/src/mailbox.rs` — Security check (lines 154–160)

```rust
// Before
if receipt.transaction.digest() != origin_tx_hash {
    tracing::warn!(
        claimed = ?origin_tx_hash,
        actual = ?receipt.transaction.digest(),
        ...
    );

// After
if receipt.tx_hash != origin_tx_hash {
    tracing::warn!(
        claimed = ?origin_tx_hash,
        actual = ?receipt.tx_hash,
        ...
    );
```

---

### 4. `storage/src/process_block.rs` — Receipt store loop (line 55)

```rust
// Before
let tx_hash = receipt.transaction.digest();
// After
let tx_hash = receipt.tx_hash;
```

---

### 5. `rpc/src/handlers/chain.rs` — Transaction lookup after receipt fetch (lines 627–638)

After `receipt` is loaded, we need `nonce`, `from`, and `instruction`. Use `marshal.get_block(Identifier::Digest(receipt.block_hash))` (same pattern already used at line 539 in the same file for transaction lookup) to fetch the block and index into `block.transactions[receipt.tx_index as usize]`.

```rust
// Add after receipt fetch succeeds:
let block = state.marshal.get_block(Identifier::Digest(receipt.block_hash)).await;
let tx = block.and_then(|b| b.transactions.get(receipt.tx_index as usize).cloned());

let tx_response = TransactionResponse {
    hash: hex(&tx_hash),
    nonce: tx.as_ref().map(|t| t.nonce).unwrap_or(0),
    from: tx.as_ref().map(|t| hex(&t.from)).unwrap_or_default(),
    instruction: {
        let mut buf = Vec::new();
        if let Some(t) = &tx {
            cbor_into_writer(&t.instruction, &mut buf).expect("instruction CBOR");
        }
        hex(&buf)
    },
    location: Some(...),
};
```

---

### 6. `storage/src/blockchain_storage.rs` — `test_receipt` helper (lines 772–800)

```rust
pub(crate) fn test_receipt(tx: Transaction, remaining_cycles: u64, remaining_cells: u64) -> TransactionReceipt {
    let tx_hash = tx.digest();
    TransactionReceipt {
        tx_hash,          // was: transaction: tx
        bloom: None,      // was: bloom: [0u8; 256]
        ...
    }
}
```

---

### 7. `storage/src/merkle_utils.rs` — `make_test_receipt` helper (lines 156–195)

Same pattern: `tx_hash: tx.digest()` instead of `transaction: tx`, `bloom: None`.

---

### 8. `storage/src/lib.rs` — Inline test receipt constructions (~4 locations: lines 847, 1330, 1405, 1474, 1612)

Each: `transaction: tx` → `tx_hash: tx.digest()` (or `tx_hash: tx_hash` where hash already computed), `bloom: [0u8; 256]` → `bloom: None`.

---

### 9. `execution/src/execution/tests.rs` — Inline receipt (lines 774–801)

```rust
// Before
store.receipts.insert(origin_tx_hash, TransactionReceipt {
    transaction: Transaction::create_deferred(origin_tx_hash, ...),
    ...
    bloom: [0u8; 256],
});

// After
store.receipts.insert(origin_tx_hash, TransactionReceipt {
    tx_hash: origin_tx_hash,   // hash already known
    ...
    bloom: None,
});
```

---

### 10. `indexer/src/json.rs` — `receipt_to_json` (line 100)

```rust
// Before
"transaction": transaction_to_json(&receipt.transaction),

// After
"tx_hash": hex(receipt.tx_hash.as_ref()),
```

---

## Verification

1. **Compile**: `cargo build --workspace` from `node/` — must compile cleanly.
2. **Tests**: `cargo test --workspace` — all ~130 tests pass.
3. **Devnet restart**: `./scripts/restart_validator.sh` (clears chain data).
4. **Benchmark**: run `bench/config_cowboy.json` benchmark, check:
   - `apply_batch_ms` drops from ~56ms → ~15ms
   - RSS growth rate drops from ~4MB/s → ~1MB/s
5. **RPC smoke test**: `curl localhost:4000/receipt/<hash>` — returns valid JSON with `tx_hash` field; `?encoding=rlp` still works.
