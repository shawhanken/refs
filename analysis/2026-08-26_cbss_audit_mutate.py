import subprocess, sys, os, shutil, time, json
W="/home/ubuntu/marshal-worktrees/cbss-deep-0826"
D="/home/ubuntu/marshal-worktrees/_deep0826"
F=os.path.join(W,"crates/cbssd/src/chain_authorizer.rs")
ORIG=os.path.join(D,"chain_authorizer.rs.orig")

MUTS = {
 "M2_freshness": (
   """        if request.body.request_block > current_head
            || request
                .body
                .request_block
                .saturating_add(REQUEST_FRESHNESS_BLOCKS)
                < current_head
        {
            return Err(PartialSignError::StaleRequestBlock);
        }""",
   """        if false {
            return Err(PartialSignError::StaleRequestBlock);
        }"""),
 "M3_metadata_equality": (
   """        if secret_id != request.body.secret_id
            || metadata.version != request.body.version
            || recipient != request.body.recipient
        {
            return Err(PartialSignError::Unauthorized);
        }""",
   """        if false {
            return Err(PartialSignError::Unauthorized);
        }"""),
 "M4_scope": (
   """        if release_key.scope != scope_from_release_key_ref(&request.body.recipient) {
            return Err(PartialSignError::ScopeMismatch);
        }""",
   """        if false {
            return Err(PartialSignError::ScopeMismatch);
        }"""),
 "M5_runner_sig": (
   """        verify_runner_signature(request)?;""",
   """        let _ = verify_runner_signature(request);"""),
 "M6_job_assignment": (
   """        self.validate_job_assignment(request).await?;""",
   """        let _ = self.validate_job_assignment(request).await;"""),
 "M7_manifest": (
   """        let trading_post_label = self.validate_actor_manifest(request).await?;""",
   """        let trading_post_label = self.validate_actor_manifest(request).await.unwrap_or(None);"""),
 "M8_chain_id": (
   """        if request.body.chain_id != self.chain_id {
            return Err(PartialSignError::WrongChain);
        }""",
   """        if false {
            return Err(PartialSignError::WrongChain);
        }"""),
}

def restore():
    shutil.copyfile(ORIG, F)
    os.utime(F, None)   # bust mtime cache -- copy2/cp -p would reuse stale artifacts

results={}
for name,(old,new) in MUTS.items():
    restore()
    s=open(ORIG).read()
    if s.count(old)!=1:
        results[name]={"status":"PATTERN_MISS","count":s.count(old)}
        print(f"{name}: PATTERN_MISS ({s.count(old)})", flush=True)
        continue
    open(F,"w").write(s.replace(old,new))
    os.utime(F,None)
    r=subprocess.run(["cargo","nextest","run","--workspace","--locked",
                      "-E","not binary(e2e)","--no-fail-fast"],
                     cwd=W, capture_output=True, text=True,
                     env={**os.environ,"PATH":"/home/ubuntu/.cargo/bin:"+os.environ["PATH"]})
    out=r.stdout+r.stderr
    open(os.path.join(D,f"mut-{name}.log"),"w").write(out)
    if "error[" in out or "error: could not compile" in out:
        results[name]={"status":"NOCOMPILE"}
    else:
        fails=sorted({l.split("FAIL")[1].strip() for l in out.splitlines() if "FAIL [" in l})
        adv=[l for l in out.splitlines() if "cbssd::adversarial" in l]
        results[name]={"status":"KILLED" if fails else "SURVIVED",
                       "killers":fails,
                       "adversarial_pass": sum(1 for l in adv if "PASS" in l),
                       "adversarial_total": len(adv)}
    print(f"{name}: {results[name]['status']} killers={results[name].get('killers')}", flush=True)

restore()
json.dump(results, open(os.path.join(D,"mutation-table.json"),"w"), indent=2)
print("\n=== DONE ===")
print(json.dumps(results, indent=2))
