/*
  toy_engine：最小 C++ “执行引擎”
  toy_engine: a minimal C++ execution engine.

  中文：它接收 Python 序列化出来的 DAG（节点列表 + 输出映射 + 输入值），在 C++ 里求值并输出结果。
  English: It receives a serialized DAG (nodes + outputs + input values) from Python, evaluates it in C++, and prints results.
*/

#include <cstdlib>
#include <exception>
#include <iostream>
#include <optional>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

enum class Op
{
    INPUT,
    CONST,
    ADD,
    MUL,
};

struct Node
{
    int id = -1;
    Op op{};

    // 中文：对二元算子，a/b 是输入节点 id。
    // English: For binary ops, a/b are input node ids.
    int a = -1;
    int b = -1;

    // 中文：对 CONST 节点。
    // English: For CONST nodes.
    int const_value = 0;

    // 中文：对 INPUT 节点（引用输入名）。
    // English: For INPUT nodes (references an input name).
    std::string input_name;
};

static Op parseOp(const std::string &s)
{
    if (s == "INPUT")
        return Op::INPUT;
    if (s == "CONST")
        return Op::CONST;
    if (s == "ADD")
        return Op::ADD;
    if (s == "MUL")
        return Op::MUL;
    throw std::runtime_error("Unknown op: " + s);
}

struct Engine
{
    std::unordered_map<std::string, int> inputs;
    std::unordered_map<int, Node> nodes;
    std::vector<std::pair<std::string, int>> outputs; // (key, node_id)

    // 中文：缓存每个节点求值结果。
    // English: memoize each node's computed value.
    std::unordered_map<int, int> memo;

    int evalNode(int nodeId, std::unordered_set<int> &visiting)
    {
        if (auto it = memo.find(nodeId); it != memo.end())
            return it->second;

        if (visiting.count(nodeId))
            throw std::runtime_error("Cycle detected at node " + std::to_string(nodeId));
        visiting.insert(nodeId);

        auto itn = nodes.find(nodeId);
        if (itn == nodes.end())
            throw std::runtime_error("Unknown node id: " + std::to_string(nodeId));

        const Node &n = itn->second;
        int value = 0;

        switch (n.op)
        {
        case Op::INPUT: {
            auto iti = inputs.find(n.input_name);
            if (iti == inputs.end())
                throw std::runtime_error("Missing input value for '" + n.input_name + "'");
            value = iti->second;
            break;
        }
        case Op::CONST:
            value = n.const_value;
            break;
        case Op::ADD: {
            int av = evalNode(n.a, visiting);
            int bv = evalNode(n.b, visiting);
            value = av + bv;
            break;
        }
        case Op::MUL: {
            int av = evalNode(n.a, visiting);
            int bv = evalNode(n.b, visiting);
            value = av * bv;
            break;
        }
        default:
            throw std::runtime_error("Unhandled op");
        }

        visiting.erase(nodeId);
        memo[nodeId] = value;
        return value;
    }
};

static void die(const std::string &msg)
{
    // 中文：约定错误输出走 stderr，并用非 0 退出码。
    // English: write errors to stderr and exit non-zero.
    std::cerr << msg << "\n";
    std::exit(2);
}

int main()
{
    try
    {
        Engine eng;

        std::string line;
        while (std::getline(std::cin, line))
        {
            if (line.empty())
                continue;

            std::istringstream iss(line);
            std::string head;
            iss >> head;

            if (head == "END")
            {
                break;
            }
            else if (head == "SET")
            {
                // SET <name> <int>
                std::string name;
                int value;
                if (!(iss >> name >> value))
                    die("Bad SET line: " + line);
                eng.inputs[name] = value;
            }
            else if (head == "NODE")
            {
                // NODE <id> <OP> ...
                int id;
                std::string opStr;
                if (!(iss >> id >> opStr))
                    die("Bad NODE header: " + line);

                Node n;
                n.id = id;
                n.op = parseOp(opStr);

                if (n.op == Op::INPUT)
                {
                    // NODE <id> INPUT <name>
                    if (!(iss >> n.input_name))
                        die("Bad INPUT node line: " + line);
                }
                else if (n.op == Op::CONST)
                {
                    // NODE <id> CONST <int>
                    if (!(iss >> n.const_value))
                        die("Bad CONST node line: " + line);
                }
                else if (n.op == Op::ADD || n.op == Op::MUL)
                {
                    // NODE <id> ADD <lhs_id> <rhs_id>
                    // NODE <id> MUL <lhs_id> <rhs_id>
                    if (!(iss >> n.a >> n.b))
                        die("Bad binary node line: " + line);
                }
                else
                {
                    die("Unhandled op in parser");
                }

                if (eng.nodes.count(id))
                    die("Duplicate node id: " + std::to_string(id));
                eng.nodes[id] = std::move(n);
            }
            else if (head == "OUT")
            {
                // OUT <key> <node_id>
                std::string key;
                int nodeId;
                if (!(iss >> key >> nodeId))
                    die("Bad OUT line: " + line);
                eng.outputs.emplace_back(key, nodeId);
            }
            else
            {
                die("Unknown line head: " + head);
            }
        }

        // 中文：计算并输出每个 graph output（模拟 CSP 的 GraphOutputAdapter collect）。
        // English: compute and print each graph output (similar to CSP GraphOutputAdapter collect).
        for (const auto &out : eng.outputs)
        {
            const std::string &key = out.first;
            int nodeId = out.second;
            std::unordered_set<int> visiting;
            int value = eng.evalNode(nodeId, visiting);
            std::cout << "RESULT " << key << " " << value << "\n";
        }

        return 0;
    }
    catch (const std::exception &e)
    {
        std::cerr << "ERROR " << e.what() << "\n";
        return 1;
    }
}

