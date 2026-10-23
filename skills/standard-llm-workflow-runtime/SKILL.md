---
name: standard-llm-workflow-runtime
description: >
  LLM 工作流执行。新增节点执行器、解析节点间模板变量，或做 SSE 单步调试时使用。
---

# LLM 工作流执行

本篇覆盖 LLM 对话工作流的执行和单步调试：路径会随 LLM 输出或条件分支变化。图的建模、存储、发布、画布见 `standard-graph-workflow-editor`。预先定死、不含变量表达式的装配流程不用这里的模板解析。

## 节点间数据流

每个节点执行后，把输出 `dict` 写入共享状态：

```python
state["node_outputs"][node_id] = {"text": "...", "confidence": 0.9}
```

后续节点用模板引用前驱的输出字段：

```
{{node_id.field}}
```

解析器按简单正则单趟扫描，不解析 `{{a.{{b.c}}}}` 这类嵌套。用户原始输入也走同一语法，例如 `{{start.user_input}}`。

各节点类型的主要文本输出统一叫 `text`。写成 `content` 或 `output` 时解析得到空值，而且不报错。

## 变量解析失败

引用尚未执行的节点时抛异常。返回空字符串或 `None` 时，下游会带着空输入继续跑，整条链路不报错，日志也正常。

节点已经执行完、字段值恰好是 `None`，与「引用未执行的节点」分开处理：前者解析成空字符串；后者多半是条件分支把该节点跳过了，必须报错。

非字符串值（数字、bool、dict）进模板时统一 `str()`。

三个职责分开，不合成一个函数：

| 职责 | 用途 |
|---|---|
| 解析单个表达式 | 给定 `{{node_id.field}}`，返回具体值 |
| 解析整个模板 | 普通文本和多个变量引用混在一起，逐个替换 |
| 提取变量引用列表（不解析） | 列出模板依赖哪些节点，供发布前做静态依赖分析 |

发布前用第三项检查：被引用的节点在拓扑上先于当前节点执行。不等到运行时才报错。

## 新增节点执行器

新增一种节点类型时，下面每处都改：

1. 值对象：节点类型枚举加一个值
2. 配置类：`@dataclass(frozen=True)`，实现 `from_dict()` 和 `validate() -> list[str]`
3. 执行器：继承基类，实现 `async execute(*, node_id, node_config, state, writer, **kwargs) -> dict`
4. 注册：每一处构建执行器注册表的地方都注册。调试执行和正式执行若是两条代码路径，两处都改。只改调试路径时，本地调试能跑，正式执行报「未知节点类型」
5. 图校验器白名单：新类型加进「合法节点类型」，否则发布阶段会判非法
6. 图校验器的配置校验分支：新类型的配置字段校验接进校验流程，否则填错要到运行时才炸

## 条件路由

条件判断、意图识别这类要决定后继节点的执行器，返回值里带一个可判别的分支字段：

```python
return {"matched_branch": "yes", ...其他字段}
```

引擎读这个字段选择后继。漏掉这个字段时，节点本身仍返回了合法 `dict`，图会停在该节点后，或落入默认分支，两种都不抛异常。

条件类执行器的测试断言该字段存在。

## SSE 单步调试

调试是发一条消息、实时看工作流怎么跑。事件顺序：

```
workflow_start
  → node_start    (node_id, node_type, label)
  → node_input    (input)
  → node_stream   (content chunks, LLM 流式输出片段)
  → node_complete (output, duration_ms)
  或 node_error   (error, error_code, error_type)
workflow_complete
```

流结束带显式标记（如 `[DONE]`）。连接关闭也可能是网络异常，两种情况要能分开。

调试期间画布不可编辑。调试跑的是开始时的快照；中途拖节点或改连线后，事件里的 `node_id` 对不上画布上的图。

画布状态是 `node_id → 状态`，状态机为 `pending → running → completed / error`。调试开始时全部节点重置为 `pending`，`node_start` 改为 `running`，`node_complete` / `node_error` 改为终态。画布订阅这个 map，用状态驱动样式（如描边颜色）。

SSE 客户端：

- 用 `fetch` + `ReadableStream` 读流。需要自定义 header（如认证）时不用 `EventSource`，它带不了自定义 header
- 用 `AbortController` 让用户取消调试
- 按行解析 `data: ` 前缀的 JSON，并用 buffer 接住跨 chunk 被截断的行。chunk 边界和 SSE 消息边界不是一回事

```typescript
buffer += decoder.decode(value, { stream: true });
const lines = buffer.split("\n");
buffer = lines.pop() || "";   // 最后一行可能不完整，留到下次 chunk 再拼
```

每个 chunk 到达就按行 split、不留 buffer 时，被截断的半行 JSON 解析失败。这只在消息长度恰好跨 chunk 边界时出现。
