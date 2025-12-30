"""
toy_csp：一个最小的“Python 组图、C++ 跑图”示例
toy_csp: a minimal "build in Python, run in C++" example.
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
import os
import subprocess
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


# ----------------------------
# wiring-time IR（Python 组图）
# Wiring-time IR (Python graph building)
# ----------------------------


@dataclass(frozen=True)
class Edge:
    """
    边：只引用“来自哪个节点”的哪个输出口。
    Edge: only references "which node" and "which output port".
    """

    node_id: int
    output_idx: int = 0


@dataclass
class NodeDef:
    """
    节点定义（wiring-time）：保存 op + 输入边 + 额外参数（常量值/输入名）。
    Node definition (wiring-time): stores op + input edges + extra params (const value / input name).
    """

    node_id: int
    op: str
    inputs: Tuple[Edge, ...] = ()
    const_value: Optional[int] = None
    input_name: Optional[str] = None


class Context:
    """
    图上下文：收集所有节点与输出映射（类似 CSP 的 Context）。
    Graph context: collects nodes and output mapping (similar to CSP Context).
    """

    def __init__(self) -> None:
        self._next_id = 0
        self.nodes: Dict[int, NodeDef] = {}
        self.outputs: Dict[str, Edge] = {}

    def new_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    def add_node(self, nd: NodeDef) -> None:
        if nd.node_id in self.nodes:
            raise RuntimeError(f"Duplicate node id: {nd.node_id}")
        self.nodes[nd.node_id] = nd


_TLS: Dict[str, Any] = {}


def _cur_ctx() -> Context:
    ctx = _TLS.get("ctx")
    if ctx is None:
        raise RuntimeError("No active graph build context. Did you forget to call @graph function?")
    return ctx


def input(name: str) -> Edge:
    """
    创建一个“图输入节点”（类似 CSP 里的 input adapter / placeholder）。
    Create a graph input node (similar to an input adapter / placeholder).
    """

    ctx = _cur_ctx()
    nid = ctx.new_id()
    nd = NodeDef(node_id=nid, op="INPUT", input_name=name)
    ctx.add_node(nd)
    return Edge(node_id=nid, output_idx=0)


def const(value: int) -> Edge:
    """
    常量节点（类似 csp.const）。
    Constant node (similar to csp.const).
    """

    ctx = _cur_ctx()
    nid = ctx.new_id()
    nd = NodeDef(node_id=nid, op="CONST", const_value=int(value))
    ctx.add_node(nd)
    return Edge(node_id=nid, output_idx=0)


def add(a: Edge, b: Edge) -> Edge:
    """
    加法节点（类似 csp.add）。
    Add node (similar to csp.add).
    """

    ctx = _cur_ctx()
    nid = ctx.new_id()
    nd = NodeDef(node_id=nid, op="ADD", inputs=(a, b))
    ctx.add_node(nd)
    return Edge(node_id=nid, output_idx=0)


def mul(a: Edge, b: Edge) -> Edge:
    """
    乘法节点（类似 csp.multiply）。
    Mul node (similar to csp.multiply).
    """

    ctx = _cur_ctx()
    nid = ctx.new_id()
    nd = NodeDef(node_id=nid, op="MUL", inputs=(a, b))
    ctx.add_node(nd)
    return Edge(node_id=nid, output_idx=0)


# ----------------------------
# @graph：把用户函数变成“可 build 的图定义”
# @graph: wrap user function into a buildable graph definition
# ----------------------------


class GraphDef:
    """
    图定义：调用时并不计算，只会在 Context 中创建 NodeDef/Edge。
    Graph definition: calling it does not compute; it only creates NodeDefs/Edges in a Context.
    """

    def __init__(self, fn: Callable[..., Union[Edge, Dict[str, Edge]]]) -> None:
        self._fn = fn
        self._sig = inspect.signature(fn)

    def build(self) -> Context:
        """
        构图：为每个参数创建 INPUT 节点，把 Edge 传入用户函数，得到输出 Edge，再收集到 context。
        Build: create INPUT nodes for each parameter, call user fn with Edges, collect outputs.
        """

        ctx = Context()
        _TLS["ctx"] = ctx
        try:
            kwargs = {name: input(name) for name in self._sig.parameters.keys()}
            res = self._fn(**kwargs)
            if isinstance(res, Edge):
                ctx.outputs[""] = res
            elif isinstance(res, dict):
                for k, v in res.items():
                    if not isinstance(v, Edge):
                        raise TypeError(f"Output '{k}' must be an Edge, got {type(v)}")
                    ctx.outputs[str(k)] = v
            else:
                raise TypeError(f"Graph must return Edge or dict[str, Edge], got {type(res)}")
            return ctx
        finally:
            _TLS.pop("ctx", None)


def graph(fn: Callable[..., Union[Edge, Dict[str, Edge]]]) -> GraphDef:
    """
    把 Python 函数包装成 GraphDef（类似 @csp.graph）。
    Wrap a python function into GraphDef (similar to @csp.graph).
    """

    return GraphDef(fn)


# ----------------------------
# runtime：把 IR 发给 C++ 引擎执行
# runtime: send IR to the C++ engine for execution
# ----------------------------


def _serialize_to_protocol(ctx: Context, inputs: Dict[str, int]) -> str:
    """
    把图 IR 序列化成 toy_engine 能读的文本协议。
    Serialize the graph IR into a tiny text protocol understood by toy_engine.

    协议（Protocol）：
    - SET <name> <int>
    - NODE <id> INPUT <name>
    - NODE <id> CONST <int>
    - NODE <id> ADD <lhs_id> <rhs_id>
    - NODE <id> MUL <lhs_id> <rhs_id>
    - OUT <key> <node_id>
    - END
    """

    lines: List[str] = []
    for k, v in inputs.items():
        lines.append(f"SET {k} {int(v)}")

    # 为了稳定输出，按 node_id 排序。
    # For stable output, sort by node_id.
    for node_id in sorted(ctx.nodes.keys()):
        nd = ctx.nodes[node_id]
        if nd.op == "INPUT":
            assert nd.input_name is not None
            lines.append(f"NODE {nd.node_id} INPUT {nd.input_name}")
        elif nd.op == "CONST":
            assert nd.const_value is not None
            lines.append(f"NODE {nd.node_id} CONST {nd.const_value}")
        elif nd.op in ("ADD", "MUL"):
            if len(nd.inputs) != 2:
                raise RuntimeError(f"{nd.op} expects 2 inputs, got {len(nd.inputs)}")
            a, b = nd.inputs
            lines.append(f"NODE {nd.node_id} {nd.op} {a.node_id} {b.node_id}")
        else:
            raise RuntimeError(f"Unknown op: {nd.op}")

    for key, edge in ctx.outputs.items():
        lines.append(f"OUT {key} {edge.node_id}")

    lines.append("END")
    return "\n".join(lines) + "\n"


def run(g: GraphDef, *, inputs: Dict[str, int], engine_path: Optional[str] = None) -> Dict[str, int]:
    """
    运行图：Python 组图 -> 序列化 -> 调用 C++ toy_engine -> 解析结果。
    Run: build in Python -> serialize -> invoke C++ toy_engine -> parse results.
    """

    ctx = g.build()

    # 默认使用同目录下的 toy_engine
    # Default to toy_engine in the same directory
    if engine_path is None:
        engine_path = os.path.join(os.path.dirname(__file__), "toy_engine")

    payload = _serialize_to_protocol(ctx, inputs=inputs)

    proc = subprocess.run(
        [engine_path],
        input=payload.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "toy_engine failed.\n"
            f"returncode={proc.returncode}\n"
            f"stderr:\n{proc.stderr.decode('utf-8', errors='replace')}"
        )

    out: Dict[str, int] = {}
    for line in proc.stdout.decode("utf-8").splitlines():
        if not line.strip():
            continue
        # RESULT <key> <int>
        parts = line.split(" ", 2)
        if len(parts) != 3 or parts[0] != "RESULT":
            raise RuntimeError(f"Unexpected engine output line: {line!r}")
        key = parts[1]
        val = int(parts[2])
        out[key] = val

    return out

