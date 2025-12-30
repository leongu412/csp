"""
demo：用 toy_csp 构图，并在 C++ toy_engine 里执行
demo: build a graph with toy_csp and execute it in the C++ toy_engine.
"""

from toy_csp import add, const, graph, mul, run


@graph
def my_graph(x, y):
    """
    图定义：z = (x + 2) * (y + 3)
    Graph definition: z = (x + 2) * (y + 3)
    """

    left = add(x, const(2))
    right = add(y, const(3))
    z = mul(left, right)

    # 中文：返回 dict 代表多个输出（类似 CSP 的 OutputsContainer / named outputs）。
    # English: returning a dict yields multiple named outputs (similar to OutputsContainer / named outputs).
    return {"z": z}


if __name__ == "__main__":
    out = run(my_graph, inputs={"x": 10, "y": 5})
    print(out)  # 期望 {'z': (10+2)*(5+3)=96} / expected {'z': 96}

