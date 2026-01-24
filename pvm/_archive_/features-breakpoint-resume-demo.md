# PVM Checkpoint/Resume Demo

This directory contains multiple examples demonstrating PVM's checkpoint/resume functionality.

## Feature Overview

PVM's checkpoint/resume feature allows programs to save state snapshots during execution and resume from those snapshots in subsequent runs. This is very useful for long-running programs, debugging, and scenarios that require pausing and resuming.

## Demo Files

### 1. `demo.py` - Main Demo

Demonstrates a trading system simulation scenario. The program executes in three phases, with a checkpoint between each phase:

1. **Phase 1**: Prepare input data (orders, prices, risk limits)
2. **Phase 2**: Simulate fills, calculate slippage and notional value, flag risks
3. **Phase 3**: Generate final report and cleanup

#### Usage

```bash
# First run (execute to first checkpoint)
./target/release/pvm examples/breakpoint_resume_demo/demo.py

# Resume from first checkpoint (execute to second checkpoint)
./target/release/pvm --resume examples/breakpoint_resume_demo/demo.rpsnap examples/breakpoint_resume_demo/demo.py

# Resume from second checkpoint (complete program execution)
./target/release/pvm --resume examples/breakpoint_resume_demo/demo.rpsnap examples/breakpoint_resume_demo/demo.py
```

### 2. `comprehensive_demo.py` - Comprehensive Demo

Demonstrates the wide variety of Python control flow structures that PVM can successfully checkpoint and resume, including:

- Functions (nested calls)
- For loops (list iteration, enumerate, zip, map, filter)
- While loops
- If/elif/else statements
- Try/except/finally blocks
- Match statements (pattern matching)
- List comprehensions
- Dictionary and set operations
- Nested control structures

**Note**: This demo avoids using `range()` due to a known issue with range_iterator restoration in loop contexts. It's recommended to use list iteration or while loops as alternatives.

#### Usage

```bash
./target/release/pvm examples/breakpoint_resume_demo/comprehensive_demo.py
# Then use --resume to continue execution
```

### 3. `actor_complex_demo.py` - Complex Actor Demo

Demonstrates using checkpoint functionality in complex actor patterns, including:

- Actor state management
- Checkpoints in function calls
- Checkpoints in loops
- Checkpoints in conditional statements
- Checkpoints in exception handling

#### Usage

```bash
./target/release/pvm examples/breakpoint_resume_demo/actor_complex_demo.py
# Then use --resume to continue execution
```

### 4. `test_checkpoint.py` - Automated Test Script

Automatically executes the complete three-phase flow and verifies that the checkpoint/resume functionality works correctly.

#### Usage

```bash
python3 examples/breakpoint_resume_demo/test_checkpoint.py
```

Or specify a custom binary path:

```bash
python3 examples/breakpoint_resume_demo/test_checkpoint.py --bin ./target/release/pvm
```

## Key API

All demos use the `rustpython_checkpoint` module:

```python
import rustpython_checkpoint as rpc

# Save checkpoint (program will save state here and exit)
rpc.checkpoint(CHECKPOINT_PATH)
```

**Important Notes**:
- The `checkpoint()` call must be a standalone statement
- You need to re-import the `rustpython_checkpoint` module after resume
- Checkpoint file path should be a string type (serializable)

## Checkpoint Files

Checkpoint files use the `.rpsnap` extension and contain complete VM state snapshots, including:
- All local and global variables
- Call stack
- Program counter position
- Other runtime state

## More Information

For more detailed information about the checkpoint/resume feature, see the main project [README.md](../../README.md).
