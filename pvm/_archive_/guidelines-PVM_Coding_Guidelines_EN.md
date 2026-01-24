# PVM Python Coding Guidelines and Best Practices

## Document Information

**Version**: 1.0  
**Last Updated**: 2025-01-03  
**Author**: Hanken SHAW (shawhanken@gmail.com)  
**Target Audience**: Developers building and running Python applications on PVM

---

## 1. Introduction

### 1.1 About PVM

PVM (Python Virtual Machine with Checkpoint/Resume) is a Python virtual machine with checkpoint/resume capabilities, built on RustPython. It allows you to save program state at any point during execution and resume from that point later.

**Key Features**:
- ✅ Supports most Python 3.x syntax and standard library
- ✅ Checkpoint/resume functionality
- ✅ Complex control flow structures
- ✅ Function call stack serialization

**Typical Use Cases**:
- Actor model transaction processing
- Long-running data processing tasks
- Fault tolerance in distributed computing
- State machine persistence
- Interruptible batch processing

### 1.2 Document Purpose

This document helps developers:
1. Understand which Python features are **fully supported**
2. Learn about features with **limitations** or **not supported**
3. Learn correct checkpoint placement
4. Avoid common errors and pitfalls
5. Write efficient and reliable PVM applications

---

## 2. Fully Supported Python Features

### 2.1 Basic Data Types

**✅ Supported**:

```python
# All basic types are fully supported
import rustpython_checkpoint as rpc

# Numbers
integer = 42
floating = 3.14
complex_num = 1 + 2j

# Strings
text = "Hello, PVM!"
multiline = """
    Multi-line
    string
"""

# Booleans
flag = True

# None
value = None

# Checkpoint can save all these types
rpc.checkpoint("state.rpsnap")
```

### 2.2 Container Types

**✅ Supported**:

```python
# Lists
numbers = [1, 2, 3, 4, 5]
mixed = [1, "two", 3.0, None]
nested = [[1, 2], [3, 4], [5, 6]]

# Tuples
coordinates = (10, 20)
immutable_data = (1, "two", 3.0)

# Dictionaries
user = {"name": "Alice", "age": 30, "active": True}
nested_dict = {"level1": {"level2": {"value": 42}}}

# Sets
unique_numbers = {1, 2, 3, 4, 5}
frozen_set = frozenset([1, 2, 3])

# All container types serialize correctly
rpc.checkpoint("containers.rpsnap")
```

### 2.3 Control Flow - Fully Supported

#### 2.3.1 List Iteration

**✅ Fully Supported**:

```python
# For loop - list iteration
data = [10, 20, 30, 40, 50]

for item in data:
    print(f"Processing {item}")
    if item == 30:
        # Checkpoint in list iteration loop fully supported
        rpc.checkpoint("loop.rpsnap")
    process(item)

# Nested loops
matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]

for row in matrix:
    for value in row:
        if value == 5:
            # Checkpoint in nested loop fully supported
            rpc.checkpoint("nested.rpsnap")
        process(value)
```

#### 2.3.2 Enumerate Loop

**✅ Fully Supported**:

```python
# Enumerate - recommended for index-based scenarios
items = ["apple", "banana", "cherry"]

for index, item in enumerate(items):
    print(f"{index}: {item}")
    if index == 1:
        # Checkpoint in enumerate loop fully supported
        rpc.checkpoint("enum.rpsnap")
    process(item)
```

#### 2.3.3 While Loop

**✅ Fully Supported**:

```python
# While loop
counter = 0

while counter < 10:
    print(f"Counter: {counter}")
    if counter == 5:
        # Checkpoint in while loop fully supported
        rpc.checkpoint("while.rpsnap")
    counter += 1
```

---

## 3. Features with Limitations

### 3.1 Range Loops

**⚠️ Partially Supported**:

```python
# ❌ Not Recommended: checkpoint in range() loop
for i in range(10):
    print(i)
    if i == 5:
        rpc.checkpoint("range.rpsnap")  # May fail on resume
    process(i)
```

**Problem**:
- Range iterator can be serialized
- But may error on resume: `TypeError: 'range' object is not an iterator`

**✅ Recommended Alternatives**:

```python
# Alternative 1: Use list instead of range
for i in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
    if i == 5:
        rpc.checkpoint("list.rpsnap")  # Works perfectly
    process(i)

# Alternative 2: Use while loop
i = 0
while i < 10:
    if i == 5:
        rpc.checkpoint("while.rpsnap")  # Works perfectly
    process(i)
    i += 1

# Alternative 3: Checkpoint outside loop
for i in range(10):
    process(i)

# Checkpoint after loop completes
rpc.checkpoint("after_loop.rpsnap")  # Works perfectly
```

### 3.2 Dictionary Iterators

**⚠️ Partially Supported**:

```python
# ❌ Not Recommended: checkpoint in dict iterator loop
data = {"a": 1, "b": 2, "c": 3}

for key, value in data.items():
    if key == "b":
        rpc.checkpoint("dict_iter.rpsnap")  # May cause infinite loop
    process(key, value)
```

**✅ Recommended Alternatives**:

```python
# Alternative 1: Convert to list before iteration
data = {"a": 1, "b": 2, "c": 3}
items_list = list(data.items())

for key, value in items_list:
    if key == "b":
        rpc.checkpoint("dict_list.rpsnap")  # Works perfectly
    process(key, value)

# Alternative 2: Checkpoint outside loop
for key, value in data.items():
    process(key, value)

# Checkpoint after loop
rpc.checkpoint("after_dict.rpsnap")  # Works perfectly
```

---

## 4. Checkpoint Placement Best Practices

### 4.1 Recommended Checkpoint Locations

**✅ Good Practices**:

```python
# 1. Before/after function calls
def process_transaction(data):
    validate(data)
    
    # Checkpoint before critical operation
    rpc.checkpoint("before_commit.rpsnap")
    
    commit(data)
    
    # Checkpoint after critical operation
    rpc.checkpoint("after_commit.rpsnap")
    
    return result

# 2. At batch boundaries
for batch in get_batches(data, batch_size=100):
    process_batch(batch)
    
    # Checkpoint after each batch
    rpc.checkpoint(f"batch_{batch.id}.rpsnap")

# 3. At state transitions
class StateMachine:
    def transition(self, new_state):
        # Checkpoint before state change
        rpc.checkpoint(f"state_{self.state}.rpsnap")
        
        self.state = new_state
        
        # Checkpoint after state change
        rpc.checkpoint(f"state_{new_state}.rpsnap")
```

### 4.2 Locations to Avoid

**❌ Bad Practices**:

```python
# 1. ❌ Inside range loops
for i in range(1000):
    rpc.checkpoint(f"loop_{i}.rpsnap")  # Not recommended
    process(i)

# 2. ❌ Inside dict iterators
for key, value in big_dict.items():
    rpc.checkpoint(f"dict_{key}.rpsnap")  # Not recommended
    process(key, value)

# 3. ❌ Inside closures
def outer(x):
    def inner(y):
        rpc.checkpoint("closure.rpsnap")  # May crash
        return x + y
    return inner

# 4. ❌ Too frequent checkpoints
for i in items:
    rpc.checkpoint("a.rpsnap")  # Poor performance
    step1(i)
    rpc.checkpoint("b.rpsnap")  # Too frequent
    step2(i)
```

---

## 5. Quick Reference

### 5.1 Feature Support Matrix

| Feature | Support | Checkpoint Location | Alternative |
|---------|---------|-------------------|-------------|
| List iteration | ✅ Full | Inside loop | - |
| Enumerate | ✅ Full | Inside loop | - |
| While loop | ✅ Full | Inside loop | - |
| Range loop | ⚠️ Partial | Outside loop | List/while |
| Dict iterators | ⚠️ Partial | Outside loop | Convert to list |
| Closures | ✅ Full | Outside | - |
| Try/Except | ✅ Full | Inside block | - |
| Match statement | ✅ Full | Inside case | - |
| Comprehensions | ✅ Full | Outside | - |
| Map/Filter | ✅ Full | Outside | - |

### 5.2 Error Code Quick Reference

| Error Message | Likely Cause | Solution |
|--------------|-------------|----------|
| `'range' object is not an iterator` | Range loop checkpoint | Use list or while |
| `index out of bounds` (cells_frees) | Checkpoint in closure | Move outside closure |
| Program hangs/timeout | Deadlock or complex structure | Simplify data structure |
| `checkpoint restore failed` | Unsupported object type | Check object types |
| Infinite loop after resume | Iterator state error | Convert to list iteration |

---

## 6. Complete Example

### 6.1 Actor Transaction Processing

```python
"""Actor Model Transaction Processing Example"""
import rustpython_checkpoint as rpc

CHECKPOINT_PATH = "actor_transaction.rpsnap"

class Actor:
    def __init__(self, actor_id, initial_balance):
        self.actor_id = actor_id
        self.balance = initial_balance
        self.history = []
        self.checkpoint_flags = set()
    
    def process_mailbox(self, messages):
        """Process message queue"""
        results = []
        
        for index, message in enumerate(messages):
            print(f"[{self.actor_id}] Processing message {index}")
            
            result = self.process_message(message)
            if result:
                results.append(result)
            
            # Checkpoint every 10 messages
            if (index + 1) % 10 == 0:
                rpc.checkpoint(CHECKPOINT_PATH)
                print(f"[{self.actor_id}] Checkpoint at message {index + 1}")
        
        return results
    
    def process_message(self, message):
        """Process a single message"""
        msg_type = message["type"]
        
        if msg_type == "deposit":
            self.balance += message["amount"]
            self.history.append({
                "type": "deposit",
                "amount": message["amount"]
            })
        
        elif msg_type == "transfer":
            if self.balance >= message["amount"]:
                self.balance -= message["amount"]
                self.history.append({
                    "type": "transfer",
                    "amount": message["amount"],
                    "to": message["to"]
                })
        
        return None

# Usage
actor = Actor("actor_001", 1000.0)
messages = [
    {"type": "deposit", "amount": 500.0},
    {"type": "transfer", "amount": 200.0, "to": "actor_002"},
    # ... more messages
]
actor.process_mailbox(messages)
```

---

## 7. Summary

### 7.1 Core Principles

1. **Prefer fully supported features**: List iteration, while loops, enumerate
2. **Avoid limited features**: Range loops, dict iterators, generators
3. **Place checkpoints wisely**: At transaction boundaries, batch boundaries, state transitions
4. **Keep it simple**: Avoid overly complex data structures
5. **Test thoroughly**: Verify checkpoint/resume functionality

### 7.2 Getting Help

If you encounter issues:

1. **Check documentation**: `refs/Block_Stack_Checkpoint_Support.md`
2. **See examples**: `examples/breakpoint_resume_demo/`
3. **Review limitations**: `refs/Block_Stack_Implementation_Challenges.md`
4. **Contact support**: shawhanken@gmail.com

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-03  
**Author**: Hanken SHAW (shawhanken@gmail.com)  
**License**: MIT License

