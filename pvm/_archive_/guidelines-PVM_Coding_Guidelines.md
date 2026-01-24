# PVM Python 代码规范与最佳实践

## 文档信息

**版本**: 1.0  
**最后更新**: 2025-01-03  
**作者**: Hanken SHAW (shawhanken@gmail.com)  
**适用对象**: 在 PVM 上开发和运行 Python 应用的开发者

---

## 1. 简介

### 1.1 关于 PVM

PVM (Python Virtual Machine with Checkpoint/Resume) 是一个支持 checkpoint/resume 功能的 Python 虚拟机，基于 RustPython 开发。它允许你在程序执行的任意点保存状态，并在之后从该点恢复执行。

**主要特性**：
- ✅ 支持大部分 Python 3.x 语法和标准库
- ✅ 支持 checkpoint/resume（检查点/恢复）
- ✅ 支持复杂的控制流结构
- ✅ 支持函数调用栈的序列化

**典型应用场景**：
- Actor 模型的事务处理
- 长时间运行的数据处理任务
- 分布式计算中的容错
- 状态机的持久化
- 可中断的批处理任务

### 1.2 文档目的

本文档旨在帮助开发者：
1. 了解哪些 Python 特性在 PVM 中**完全支持**
2. 了解哪些特性**有限制**或**不支持**
3. 学习如何正确放置 checkpoint
4. 避免常见错误和陷阱
5. 编写高效、可靠的 PVM 应用

---

## 2. 完全支持的 Python 特性

### 2.1 基本数据类型

**✅ 支持**：

```python
# 所有基本类型都完全支持
import rustpython_checkpoint as rpc

# 数字
integer = 42
floating = 3.14
complex_num = 1 + 2j

# 字符串
text = "Hello, PVM!"
multiline = """
    Multi-line
    string
"""

# 布尔值
flag = True

# None
value = None

# Checkpoint 可以保存所有这些类型
rpc.checkpoint("state.rpsnap")
```

### 2.2 容器类型

**✅ 支持**：

```python
# 列表
numbers = [1, 2, 3, 4, 5]
mixed = [1, "two", 3.0, None]
nested = [[1, 2], [3, 4], [5, 6]]

# 元组
coordinates = (10, 20)
immutable_data = (1, "two", 3.0)

# 字典
user = {"name": "Alice", "age": 30, "active": True}
nested_dict = {"level1": {"level2": {"value": 42}}}

# 集合
unique_numbers = {1, 2, 3, 4, 5}
frozen_set = frozenset([1, 2, 3])

# 所有容器类型都可以正确序列化
rpc.checkpoint("containers.rpsnap")
```

**注意事项**：
- 字典的键必须是可哈希的类型
- 嵌套深度没有硬性限制，但过深可能影响性能

### 2.3 函数和类

**✅ 支持**：

```python
# 函数定义
def calculate(x, y):
    """普通函数完全支持"""
    result = x + y
    rpc.checkpoint("func.rpsnap")  # 函数内 checkpoint
    return result

# 类定义
class Counter:
    """类定义完全支持"""
    def __init__(self, initial=0):
        self.value = initial
    
    def increment(self):
        self.value += 1
        rpc.checkpoint("class.rpsnap")  # 方法内 checkpoint
        return self.value

# 使用
result = calculate(10, 20)
counter = Counter(100)
counter.increment()
```

**支持的函数特性**：
- ✅ 位置参数和关键字参数
- ✅ 默认参数值
- ✅ `*args` 和 `**kwargs`
- ✅ 嵌套函数定义
- ✅ 递归函数
- ✅ 装饰器

### 2.4 控制流 - 完全支持

#### 2.4.1 条件语句

**✅ 支持**：

```python
# If/elif/else 完全支持
value = 75

if value < 0:
    category = "negative"
elif value < 50:
    category = "low"
    rpc.checkpoint("if1.rpsnap")
elif value < 100:
    # Checkpoint 在条件分支中完全支持
    rpc.checkpoint("if2.rpsnap")
    category = "medium"
else:
    category = "high"
    rpc.checkpoint("if3.rpsnap")
```

#### 2.4.2 循环 - 列表迭代

**✅ 完全支持**：

```python
# For 循环 - 列表迭代
data = [10, 20, 30, 40, 50]

for item in data:
    print(f"Processing {item}")
    if item == 30:
        # Checkpoint 在列表迭代循环中完全支持
        rpc.checkpoint("loop.rpsnap")
    process(item)

# 嵌套循环
matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]

for row in matrix:
    for value in row:
        if value == 5:
            # 嵌套循环中的 checkpoint 完全支持
            rpc.checkpoint("nested.rpsnap")
        process(value)
```

#### 2.4.3 While 循环

**✅ 完全支持**：

```python
# While 循环
counter = 0

while counter < 10:
    print(f"Counter: {counter}")
    if counter == 5:
        # While 循环中的 checkpoint 完全支持
        rpc.checkpoint("while.rpsnap")
    counter += 1
    
# Break 和 continue 也完全支持
while True:
    value = get_next_value()
    if value < 0:
        break
    if value % 2 == 0:
        continue
    rpc.checkpoint("loop_control.rpsnap")
    process(value)
```

#### 2.4.4 Enumerate 循环

**✅ 完全支持**：

```python
# Enumerate - 推荐用于需要索引的场景
items = ["apple", "banana", "cherry"]

for index, item in enumerate(items):
    print(f"{index}: {item}")
    if index == 1:
        # Enumerate 循环中的 checkpoint 完全支持
        rpc.checkpoint("enum.rpsnap")
    process(item)

# 带起始值的 enumerate
for index, item in enumerate(items, start=100):
    if index == 101:
        rpc.checkpoint("enum_start.rpsnap")
    print(f"{index}: {item}")
```

#### 2.4.5 异常处理

**✅ 完全支持**：

```python
# Try/except/finally 完全支持
try:
    risky_operation()
    rpc.checkpoint("try.rpsnap")  # Try 块中的 checkpoint
    more_operations()
except ValueError as e:
    # Except 块中的 checkpoint 完全支持
    rpc.checkpoint("except.rpsnap")
    handle_error(e)
except Exception as e:
    log_error(e)
finally:
    # Finally 块中的 checkpoint 也支持
    rpc.checkpoint("finally.rpsnap")
    cleanup()

# 嵌套 try/except
try:
    try:
        inner_operation()
        rpc.checkpoint("inner_try.rpsnap")
    except ValueError:
        handle_value_error()
except Exception:
    handle_general_error()
```

#### 2.4.6 Match 语句（Pattern Matching）

**✅ 完全支持**：

```python
# Match 语句 (Python 3.10+)
data = {"type": "transfer", "amount": 100, "to": "account_123"}

match data:
    case {"type": "deposit", "amount": amt}:
        handle_deposit(amt)
    case {"type": "transfer", "amount": amt, "to": target}:
        # Match case 中的 checkpoint 完全支持
        rpc.checkpoint("match.rpsnap")
        handle_transfer(amt, target)
    case _:
        handle_unknown()
```

### 2.5 高阶函数和迭代器

#### 2.5.1 列表推导式

**✅ 支持**（checkpoint 在外部）：

```python
# 列表推导式
numbers = [1, 2, 3, 4, 5]
squares = [x * x for x in numbers]

# Checkpoint 放在推导式之后
rpc.checkpoint("comprehension.rpsnap")

# 条件推导式
evens = [x for x in numbers if x % 2 == 0]

# 嵌套推导式
matrix = [[i * j for j in range(3)] for i in range(3)]
rpc.checkpoint("nested_comp.rpsnap")
```

#### 2.5.2 Map 和 Filter

**✅ 支持**（checkpoint 在外部）：

```python
# Map
def double(x):
    return x * 2

numbers = [1, 2, 3, 4, 5]
doubled = list(map(double, numbers))

# Checkpoint 在 map 操作之后
rpc.checkpoint("map.rpsnap")

# Filter
def is_even(x):
    return x % 2 == 0

evens = list(filter(is_even, numbers))
rpc.checkpoint("filter.rpsnap")

# Lambda 函数
squared = list(map(lambda x: x * x, numbers))
```

#### 2.5.3 Zip

**✅ 支持**（checkpoint 在外部）：

```python
# Zip - 多个迭代器
names = ["Alice", "Bob", "Charlie"]
ages = [30, 25, 35]

# 将 zip 结果转换为列表后 checkpoint
pairs = list(zip(names, ages))
rpc.checkpoint("zip.rpsnap")

# 或在循环外 checkpoint
for name, age in zip(names, ages):
    print(f"{name}: {age}")

# Checkpoint 在循环后
rpc.checkpoint("zip_loop.rpsnap")
```

### 2.6 闭包

**✅ 支持**（checkpoint 在外部）：

```python
# 闭包函数
def make_multiplier(factor):
    """返回一个闭包"""
    def multiply(x):
        return x * factor
    return multiply

times_3 = make_multiplier(3)
result = times_3(10)  # 30

# Checkpoint 在闭包调用之后
rpc.checkpoint("closure.rpsnap")
```

**注意**：
- ⚠️ 闭包**内部**的 checkpoint 可能导致问题（cells_frees 数组越界）
- ✅ 闭包**外部**的 checkpoint 完全正常

---

## 3. 有限制的特性

### 3.1 Range 循环

**⚠️ 部分支持**：

```python
# ❌ 不推荐：range() 循环中的 checkpoint
for i in range(10):
    print(i)
    if i == 5:
        rpc.checkpoint("range.rpsnap")  # 恢复后可能出错
    process(i)
```

**问题**：
- Range iterator 可以序列化
- 但恢复后继续循环时可能报错：`TypeError: 'range' object is not an iterator`

**✅ 推荐的替代方案**：

```python
# 方案 1：使用列表替代 range
for i in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
    if i == 5:
        rpc.checkpoint("list.rpsnap")  # 完全正常
    process(i)

# 方案 2：使用 while 循环
i = 0
while i < 10:
    if i == 5:
        rpc.checkpoint("while.rpsnap")  # 完全正常
    process(i)
    i += 1

# 方案 3：Checkpoint 在循环外部
for i in range(10):
    process(i)

# Checkpoint 在循环完成后
rpc.checkpoint("after_loop.rpsnap")  # 完全正常
```

### 3.2 字典迭代器

**⚠️ 部分支持**：

```python
# ❌ 不推荐：字典迭代器循环中的 checkpoint
data = {"a": 1, "b": 2, "c": 3}

for key, value in data.items():
    if key == "b":
        rpc.checkpoint("dict_iter.rpsnap")  # 可能导致无限循环
    process(key, value)
```

**✅ 推荐的替代方案**：

```python
# 方案 1：转换为列表后迭代
data = {"a": 1, "b": 2, "c": 3}
items_list = list(data.items())

for key, value in items_list:
    if key == "b":
        rpc.checkpoint("dict_list.rpsnap")  # 完全正常
    process(key, value)

# 方案 2：Checkpoint 在循环外部
for key, value in data.items():
    process(key, value)

# Checkpoint 在循环后
rpc.checkpoint("after_dict.rpsnap")  # 完全正常
```

### 3.3 生成器

**⚠️ 有限支持**：

```python
# ❌ 生成器的状态难以完整序列化
def my_generator():
    for i in range(10):
        yield i

gen = my_generator()
next(gen)
rpc.checkpoint("generator.rpsnap")  # 可能有问题
```

**✅ 推荐的替代方案**：

```python
# 方案 1：使用普通函数返回列表
def get_data():
    return [i for i in range(10)]

data = get_data()
for item in data:
    if item == 5:
        rpc.checkpoint("list_data.rpsnap")  # 完全正常
    process(item)

# 方案 2：使用类封装状态
class DataIterator:
    def __init__(self):
        self.position = 0
        self.data = list(range(10))
    
    def next(self):
        if self.position < len(self.data):
            value = self.data[self.position]
            self.position += 1
            return value
        return None

iterator = DataIterator()
while True:
    value = iterator.next()
    if value is None:
        break
    if value == 5:
        rpc.checkpoint("class_iter.rpsnap")  # 可能更好
    process(value)
```

---

## 4. Checkpoint 放置的最佳实践

### 4.1 推荐的 Checkpoint 位置

**✅ 好的实践**：

```python
# 1. 函数调用前后
def process_transaction(data):
    validate(data)
    
    # Checkpoint 在关键操作前
    rpc.checkpoint("before_commit.rpsnap")
    
    commit(data)
    
    # Checkpoint 在关键操作后
    rpc.checkpoint("after_commit.rpsnap")
    
    return result

# 2. 循环的关键迭代点
for item in items:
    if is_critical(item):
        # 处理关键项前 checkpoint
        rpc.checkpoint(f"critical_{item.id}.rpsnap")
    
    process(item)

# 3. 异常处理的关键点
try:
    risky_operation()
    rpc.checkpoint("after_risky.rpsnap")
except Exception as e:
    # 异常处理后 checkpoint
    handle_error(e)
    rpc.checkpoint("after_error.rpsnap")

# 4. 状态转换点
class StateMachine:
    def transition(self, new_state):
        # 状态转换前 checkpoint
        rpc.checkpoint(f"state_{self.state}.rpsnap")
        
        self.state = new_state
        
        # 状态转换后 checkpoint
        rpc.checkpoint(f"state_{new_state}.rpsnap")

# 5. 批处理的批次边界
for batch in get_batches(data, batch_size=100):
    process_batch(batch)
    
    # 每个批次后 checkpoint
    rpc.checkpoint(f"batch_{batch.id}.rpsnap")
```

### 4.2 避免的 Checkpoint 位置

**❌ 不好的实践**：

```python
# 1. ❌ Range 循环内部
for i in range(1000):
    rpc.checkpoint(f"loop_{i}.rpsnap")  # 不推荐
    process(i)

# 2. ❌ 字典迭代器内部
for key, value in big_dict.items():
    rpc.checkpoint(f"dict_{key}.rpsnap")  # 不推荐
    process(key, value)

# 3. ❌ 闭包函数内部
def outer(x):
    def inner(y):
        rpc.checkpoint("closure.rpsnap")  # 可能导致崩溃
        return x + y
    return inner

# 4. ❌ 过于频繁的 checkpoint
for i in items:
    rpc.checkpoint("a.rpsnap")  # 性能差
    step1(i)
    rpc.checkpoint("b.rpsnap")  # 过于频繁
    step2(i)
    rpc.checkpoint("c.rpsnap")  # 不必要

# 5. ❌ 在紧密循环中
while True:
    rpc.checkpoint("tight.rpsnap")  # 严重影响性能
    do_small_step()
```

### 4.3 Checkpoint 粒度的选择

**平衡原则**：

```python
# ❌ 太粗：丢失太多进度
def process_huge_dataset(data):
    for item in data:  # 假设有百万条
        process(item)
    
    # 只在最后 checkpoint，前功尽弃
    rpc.checkpoint("done.rpsnap")

# ❌ 太细：性能开销大
def process_dataset(data):
    for item in data:
        step1(item)
        rpc.checkpoint("step1.rpsnap")  # 过于频繁
        step2(item)
        rpc.checkpoint("step2.rpsnap")  # 过于频繁

# ✅ 合适：批次级别
def process_dataset(data):
    batch_size = 1000
    for i in range(0, len(data), batch_size):
        batch = data[i:i+batch_size]
        
        for item in batch:
            process(item)
        
        # 每批次 checkpoint 一次
        rpc.checkpoint(f"batch_{i//batch_size}.rpsnap")
```

---

## 5. 常见错误和解决方案

### 5.1 程序卡死（Deadlock）

**问题**：

```python
# 程序在 checkpoint 时卡住，无任何输出
def my_function():
    x = 42
    rpc.checkpoint("stuck.rpsnap")  # 程序卡在这里
```

**可能原因**：
- 内部锁竞争
- 递归深度过大
- 循环引用过多

**解决方案**：

```python
# 1. 简化数据结构
# ❌ 复杂的循环引用
class Node:
    def __init__(self):
        self.parent = None
        self.children = []
        self.sibling = None

# ✅ 简化为树结构
class Node:
    def __init__(self):
        self.children = []

# 2. 限制递归深度
def process(data, depth=0):
    if depth > 100:  # 限制深度
        return
    
    if should_checkpoint(depth):
        rpc.checkpoint(f"depth_{depth}.rpsnap")
    
    for child in data.children:
        process(child, depth + 1)

# 3. 使用超时测试
import subprocess
import time

# 测试脚本
proc = subprocess.Popen(["pvm", "my_script.py"])
time.sleep(5)  # 5秒超时

if proc.poll() is None:
    print("程序卡住了！")
    proc.kill()
```

### 5.2 恢复后出现 TypeError

**问题**：

```python
for i in range(10):
    if i == 5:
        rpc.checkpoint("range.rpsnap")

# 恢复后报错：TypeError: 'range' object is not an iterator
```

**解决方案**：

```python
# 改用列表或 while 循环
for i in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
    if i == 5:
        rpc.checkpoint("list.rpsnap")  # ✅ 正常
```

### 5.3 恢复后数据不一致

**问题**：

```python
# Checkpoint 时机不当导致数据不一致
balance = 1000
balance -= 100  # 扣款
rpc.checkpoint("inconsistent.rpsnap")
# 如果这里失败，扣款已执行但后续操作未完成
record_transaction(-100)
```

**解决方案**：

```python
# ✅ 在事务边界设置 checkpoint
balance = 1000

# Checkpoint 在事务开始前
rpc.checkpoint("before_transaction.rpsnap")

# 事务操作
balance -= 100
record_transaction(-100)
update_database(balance)

# Checkpoint 在事务完成后
rpc.checkpoint("after_transaction.rpsnap")
```

### 5.4 Checkpoint 文件过大

**问题**：

```python
# 保存大量数据导致 checkpoint 文件过大
huge_data = [i for i in range(10000000)]  # 千万条记录
rpc.checkpoint("huge.rpsnap")  # 文件可能达到 GB 级别
```

**解决方案**：

```python
# 1. 分批处理，只保存必要状态
def process_huge_dataset(data):
    for i in range(0, len(data), 10000):
        batch = data[i:i+10000]
        process_batch(batch)
        
        # 只保存进度，不保存全部数据
        state = {"processed": i + 10000, "total": len(data)}
        save_state(state)
        rpc.checkpoint("progress.rpsnap")

# 2. 使用外部存储
import json

def save_large_data(data):
    # 大数据保存到文件
    with open("large_data.json", "w") as f:
        json.dump(data, f)
    
    # 只保存文件路径
    state = {"data_file": "large_data.json"}
    rpc.checkpoint("with_file.rpsnap")

def load_large_data():
    with open("large_data.json", "r") as f:
        return json.load(f)
```

### 5.5 恢复后无限循环

**问题**：

```python
# 字典迭代器中 checkpoint 可能导致无限循环
for key, value in big_dict.items():
    if key == "target":
        rpc.checkpoint("dict.rpsnap")  # 恢复后可能重复处理
    process(key, value)
```

**解决方案**：

```python
# ✅ 使用已处理集合跟踪进度
processed = set()

for key, value in big_dict.items():
    if key in processed:
        continue
    
    process(key, value)
    processed.add(key)
    
    if key == "target":
        # 保存 processed 状态
        rpc.checkpoint("dict_safe.rpsnap")
```

---

## 6. 性能优化建议

### 6.1 Checkpoint 频率

**指导原则**：

```python
# 根据场景选择合适的频率

# 1. 快速操作（毫秒级）：每 N 次操作 checkpoint
operation_count = 0
for item in items:
    fast_operation(item)
    operation_count += 1
    
    if operation_count % 1000 == 0:  # 每1000次
        rpc.checkpoint(f"ops_{operation_count}.rpsnap")

# 2. 中速操作（秒级）：每批次 checkpoint
for batch in batches:
    process_batch(batch)  # 耗时几秒
    rpc.checkpoint(f"batch_{batch.id}.rpsnap")

# 3. 慢速操作（分钟级）：每次操作后 checkpoint
for task in slow_tasks:
    process_slow_task(task)  # 耗时数分钟
    rpc.checkpoint(f"task_{task.id}.rpsnap")
```

### 6.2 数据结构优化

**原则**：避免深层嵌套和循环引用

```python
# ❌ 不好：深层嵌套
deeply_nested = {
    "level1": {
        "level2": {
            "level3": {
                "level4": {
                    "level5": {...}
                }
            }
        }
    }
}

# ✅ 好：扁平化结构
flat_structure = {
    "level1": data1,
    "level2": data2,
    "level3": data3,
    "level4": data4,
    "level5": data5,
}

# ❌ 不好：循环引用
class Node:
    def __init__(self):
        self.parent = None
        self.children = []

node1 = Node()
node2 = Node()
node1.children.append(node2)
node2.parent = node1  # 循环引用

# ✅ 好：单向引用
class Node:
    def __init__(self):
        self.children = []  # 只保存向下引用
```

### 6.3 内存管理

**原则**：及时清理不需要的数据

```python
# ✅ 清理临时数据
def process_large_dataset(data):
    for batch in get_batches(data):
        temp_results = process_batch(batch)
        save_results(temp_results)
        
        # 清理临时数据
        del temp_results
        
        rpc.checkpoint(f"batch_{batch.id}.rpsnap")
```

---

## 7. 调试技巧

### 7.1 添加调试输出

```python
# 在关键点添加输出
def complex_operation(data):
    print("[DEBUG] Starting complex operation")
    
    step1_result = step1(data)
    print(f"[DEBUG] Step 1 completed: {step1_result}")
    
    rpc.checkpoint("after_step1.rpsnap")
    print("[DEBUG] Checkpoint after step 1")
    
    step2_result = step2(step1_result)
    print(f"[DEBUG] Step 2 completed: {step2_result}")
    
    return step2_result
```

### 7.2 使用条件 Checkpoint

```python
import os

DEBUG = os.getenv("PVM_DEBUG", "0") == "1"

def conditional_checkpoint(name):
    """开发时启用，生产时禁用"""
    if DEBUG:
        rpc.checkpoint(f"debug_{name}.rpsnap")
        print(f"[DEBUG] Checkpoint: {name}")

# 使用
for item in items:
    process(item)
    conditional_checkpoint(f"item_{item.id}")
```

### 7.3 测试 Checkpoint/Resume

```python
#!/usr/bin/env python3
"""测试 checkpoint/resume 功能"""

import rustpython_checkpoint as rpc
import sys

# 状态跟踪
state = {"step": 0}

if len(sys.argv) > 1 and sys.argv[1] == "--resume":
    print("[TEST] Resuming from checkpoint")
else:
    print("[TEST] Starting fresh")

# 步骤 1
if state["step"] < 1:
    print("[TEST] Step 1")
    state["step"] = 1
    rpc.checkpoint("test.rpsnap")
    print("[TEST] Step 1 checkpoint done")

# 步骤 2
if state["step"] < 2:
    print("[TEST] Step 2")
    state["step"] = 2
    rpc.checkpoint("test.rpsnap")
    print("[TEST] Step 2 checkpoint done")

# 步骤 3
print("[TEST] Step 3 (final)")
print("[TEST] All steps completed")
```

**运行测试**：

```bash
# 第一次运行
pvm test_checkpoint.py

# 恢复运行
pvm --resume test.rpsnap test_checkpoint.py
```

---

## 8. 完整示例

### 8.1 Actor 事务处理

```python
"""Actor 模型事务处理示例"""
import rustpython_checkpoint as rpc
from pathlib import Path

CHECKPOINT_PATH = "actor_transaction.rpsnap"

class Actor:
    def __init__(self, actor_id, initial_balance):
        self.actor_id = actor_id
        self.balance = initial_balance
        self.history = []
        self.checkpoint_flags = set()
    
    def process_message(self, message):
        """处理单个消息"""
        msg_type = message["type"]
        
        # Checkpoint 在消息处理前
        if "before_msg" not in self.checkpoint_flags:
            rpc.checkpoint(CHECKPOINT_PATH)
            self.checkpoint_flags.add("before_msg")
        
        if msg_type == "deposit":
            self.balance += message["amount"]
            self.history.append({"type": "deposit", "amount": message["amount"]})
        
        elif msg_type == "transfer":
            if self.balance >= message["amount"]:
                self.balance -= message["amount"]
                self.history.append({
                    "type": "transfer",
                    "amount": message["amount"],
                    "to": message["to"]
                })
        
        elif msg_type == "query":
            result = {
                "balance": self.balance,
                "history_size": len(self.history)
            }
            return result
        
        # Checkpoint 在消息处理后
        if "after_msg" not in self.checkpoint_flags:
            rpc.checkpoint(CHECKPOINT_PATH)
            self.checkpoint_flags.add("after_msg")
        
        return None
    
    def process_mailbox(self, messages):
        """处理消息队列"""
        results = []
        
        for index, message in enumerate(messages):
            print(f"[{self.actor_id}] Processing message {index}")
            
            result = self.process_message(message)
            if result:
                results.append(result)
            
            # 每10条消息 checkpoint 一次
            if (index + 1) % 10 == 0:
                rpc.checkpoint(CHECKPOINT_PATH)
                print(f"[{self.actor_id}] Checkpoint at message {index + 1}")
        
        return results

# 使用示例
def main():
    actor = Actor("actor_001", 1000.0)
    
    messages = [
        {"type": "deposit", "amount": 500.0},
        {"type": "transfer", "amount": 200.0, "to": "actor_002"},
        {"type": "query"},
        # ... 更多消息
    ]
    
    results = actor.process_mailbox(messages)
    print(f"Final balance: {actor.balance}")
    print(f"Results: {results}")

if __name__ == "__main__":
    main()
```

### 8.2 批量数据处理

```python
"""批量数据处理示例"""
import rustpython_checkpoint as rpc

class BatchProcessor:
    def __init__(self, batch_size=1000):
        self.batch_size = batch_size
        self.processed_count = 0
        self.checkpoint_path = "batch_process.rpsnap"
    
    def process_dataset(self, dataset):
        """处理大规模数据集"""
        total = len(dataset)
        
        # 转换为列表以支持批次处理
        data_list = list(dataset)
        
        for i in range(0, total, self.batch_size):
            batch = data_list[i:i+self.batch_size]
            
            print(f"Processing batch {i//self.batch_size + 1}")
            
            # 处理当前批次
            for item in batch:
                self.process_item(item)
                self.processed_count += 1
            
            # 批次完成后 checkpoint
            progress = (self.processed_count / total) * 100
            print(f"Progress: {progress:.1f}%")
            rpc.checkpoint(self.checkpoint_path)
        
        print(f"Completed: {self.processed_count} items processed")
    
    def process_item(self, item):
        """处理单个数据项"""
        # 实际的处理逻辑
        result = transform(item)
        save_to_database(result)
        return result

# 使用示例
processor = BatchProcessor(batch_size=1000)
large_dataset = load_large_dataset()
processor.process_dataset(large_dataset)
```

---

## 9. 检查清单

### 9.1 代码审查清单

在提交代码前，检查以下项目：

- [ ] 是否使用了 `range()` 循环中的 checkpoint？→ 改用列表或 while
- [ ] 是否在字典迭代器中使用了 checkpoint？→ 改为列表或循环外
- [ ] 是否在闭包内部使用了 checkpoint？→ 移到外部
- [ ] Checkpoint 频率是否合理？→ 避免过于频繁
- [ ] 是否有深层嵌套或循环引用？→ 简化数据结构
- [ ] 是否在事务边界设置了 checkpoint？→ 确保数据一致性
- [ ] 是否添加了适当的调试输出？→ 便于问题定位
- [ ] 是否测试了 checkpoint/resume 流程？→ 验证功能正确性

### 9.2 性能检查清单

- [ ] Checkpoint 文件大小是否合理？→ 避免保存过多数据
- [ ] 是否清理了临时数据？→ 减少内存占用
- [ ] Checkpoint 间隔是否适当？→ 平衡进度保存和性能
- [ ] 是否避免了不必要的对象复制？→ 提高效率

---

## 10. 总结

### 10.1 核心原则

1. **优先使用完全支持的特性**：列表迭代、while 循环、enumerate
2. **避免有限制的特性**：range 循环、字典迭代器、生成器
3. **合理放置 checkpoint**：在事务边界、批次边界、状态转换点
4. **保持简单**：避免过度复杂的数据结构
5. **充分测试**：验证 checkpoint/resume 功能的正确性

### 10.2 快速参考

| 特性 | 支持程度 | Checkpoint 位置 | 替代方案 |
|------|---------|---------------|---------|
| 列表迭代 | ✅ 完全 | 循环内 | - |
| Enumerate | ✅ 完全 | 循环内 | - |
| While 循环 | ✅ 完全 | 循环内 | - |
| Range 循环 | ⚠️ 部分 | 循环外 | 列表/while |
| 字典迭代器 | ⚠️ 部分 | 循环外 | 转列表 |
| 闭包 | ✅ 完全 | 外部 | - |
| Try/Except | ✅ 完全 | 块内 | - |
| Match 语句 | ✅ 完全 | Case内 | - |
| 推导式 | ✅ 完全 | 外部 | - |
| Map/Filter | ✅ 完全 | 外部 | - |

### 10.3 获取帮助

如果遇到问题：

1. **查看文档**：`refs/Block_Stack_Checkpoint_Support.md`
2. **查看示例**：`examples/breakpoint_resume_demo/`
3. **检查限制**：`refs/Block_Stack_Implementation_Challenges.md`
4. **联系支持**：shawhanken@gmail.com

---

**文档版本**: 1.0  
**最后更新**: 2025-01-03  
**作者**: Hanken SHAW (shawhanken@gmail.com)  
**许可**: MIT License

---

## 附录 A：错误代码速查

| 错误信息 | 可能原因 | 解决方案 |
|---------|---------|---------|
| `'range' object is not an iterator` | Range 循环 checkpoint | 改用列表或 while |
| `index out of bounds` (cells_frees) | 闭包内 checkpoint | 移到闭包外 |
| Program hangs/timeout | 死锁或复杂结构 | 简化数据结构 |
| `checkpoint restore failed` | 不支持的对象类型 | 检查对象类型 |
| Infinite loop after resume | 迭代器状态错误 | 转为列表迭代 |

## 附录 B：性能基准

| 场景 | Checkpoint 开销 | 建议频率 |
|------|----------------|---------|
| 小对象（<1KB） | <10ms | 每100-1000次 |
| 中等对象（1-100KB） | 10-100ms | 每10-100次 |
| 大对象（>100KB） | >100ms | 每1-10次 |
| 复杂图结构 | >1s | 谨慎使用 |

