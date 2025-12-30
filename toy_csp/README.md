## toy_csp：用最小代码复刻“Python 组图，C++ 跑图”

这个 toy 项目**刻意模仿** CSP 的分层方式：

- **wiring-time（Python 组图阶段）**：用户写 `@graph` 函数，返回 `Edge`；Python 只构建图的 IR（`NodeDef` 列表 + 输出映射），不做计算。
- **runtime（C++ 执行阶段）**：`run()` 把 IR 序列化成一个简单的文本协议，交给 `toy_engine`（C++ 可执行文件）解析并执行，最后把输出返回给 Python。

> 中文：这里为了把关键结构讲清楚，运行时我用“子进程 + 文本协议”把 Python 和 C++ 隔开；真实 CSP 是通过 CPython 扩展在同一进程里直接调用 C++ Engine，但核心思想（Python 组 IR，C++ 执行）是一样的。  
> English: To keep the structure obvious, runtime uses a subprocess + tiny text protocol. Real CSP uses an in-process CPython extension, but the core idea (Python builds an IR, C++ executes it) is the same.

### 目录

- `toy_csp.py`：Python 侧的 DSL（`Edge/NodeDef/Context/@graph/run`）
- `toy_engine.cpp`：C++ 侧的执行引擎（解析协议、建 DAG、执行、输出结果）
- `run_demo.py`：一个最小 demo

### 构建与运行

在仓库根目录执行（Linux）：

```bash
g++ -O2 -std=c++17 -o toy_csp/toy_engine toy_csp/toy_engine.cpp
python3 toy_csp/run_demo.py
```

