# 部署文档（Deployment Guide）

本文档说明如何将「RAG 智能问答 Agent」从代码仓库部署到一台目标机器并稳定运行，适用于现场交付 / 项目交接场景。

## 1. 项目简介

基于 Function-Calling 的 ReAct 多工具智能体，覆盖本地知识库问答（RAG）、联网检索、网页精读、文生图，并内置短期 + 长期双记忆。架构上拆分两个进程：

| 进程 | 作用 |
| --- | --- |
| `tool_server.py` | FastAPI 工具服务，提供联网搜索 / 网页抓取（含 SSRF 防护），监听 `127.0.0.1:8000` |
| `agent.py` | 主程序，ReAct 决策循环，调用工具服务与本地向量库 |

## 2. 前置要求

- 已安装 Docker Desktop（Windows）或 Docker（Linux），并已登录镜像仓库
- 能访问外网（用于拉取镜像、调用模型与联网搜索 API；若内网镜像仓库则无需外网）
- 已准备好模型 API Key（火山方舟 Ark）与 Tavily API Key

> 本部署方式无需 Python、无需安装任何依赖——环境与依赖已全部打包在镜像内。

## 3. 玩法概要

整个服务被封装成一个镜像 **`rag-agent`**，里面已装好 Python、依赖与代码：
- `tool_server.py`（FastAPI 联网搜索 / 网页抓取）
- `agent.py`（ReAct 主程序）
- `chroma.py`（知识库入库）

目标机只需 **拉取镜像 → 配置密钥 → 起容器**，即可运行，不做任何源码级安装。

## 4. 部署步骤

### 步骤 1：拉取镜像

```bash
docker pull dengyu-han/react-rag-agent:latest
```

> 镜像来自公共 Docker Hub；若公司使用私有镜像仓库（如 Harbor / Nexus），将命令中的仓库地址替换为内网地址即可：
>
> ```bash
> docker pull mycompany.example.com/rag-agent:latest
> ```

### 步骤 2：创建运行目录并配置环境变量

```bash
mkdir rag-agent && cd rag-agent
```

创建 `.env` 并填入真实密钥：

```
API_KEY=<火山方舟 Ark API Key>
TAVILY_API_KEY=<Tavily API Key>
```

| 变量 | 说明 | 必要性 |
| --- | --- | --- |
| `API_KEY` | 火山方舟 Ark 模型 API Key，用于主对话与文生图 | 必填 |
| `TAVILY_API_KEY` | Tavily 联网搜索 Key，知识库未命中时兜底 | 可选（不需联网可留空） |

> ⚠️ 密钥在容器启动时通过环境变量注入，**不打进镜像**，仅存在于目标机本地。

### 步骤 3：准备知识库（可选，按需）

需要本地知识库问答时，先在容器内运行入库脚本。将业务文档映射进容器 `/docs` 目录，并指定 `file_list` 后执行：

```bash
docker run --rm -v "$(pwd)/docs:/docs" -v "$(pwd)/chroma_db:/app/chroma_db" \
  dengyu-han/react-rag-agent:latest python chroma.py
```

向量数据持久化到宿主机 `./chroma_db` 目录。文档变更后重跑即可增量更新，已删除文件对应的切片会被自动清理。

### 步骤 4：启动服务（推荐 docker compose）

使用镜像的一键编排（也可用下方的单容器命令）。

**创建 `docker-compose.yml`：**

```yaml
services:
  tool_server:
    image: dengyu-han/react-rag-agent:latest
    command: ["python", "tool_server.py"]
    env_file: .env
    environment:
      - TOOL_SERVER_HOST=0.0.0.0
    ports:
      - "8000:8000"
  agent:
    image: dengyu-han/react-rag-agent:latest
    command: ["python", "agent.py"]
    env_file: .env
    environment:
      - TOOL_SERVER_URL=http://tool_server:8000
    volumes:
      - ./chroma_db:/app/chroma_db
    depends_on:
      - tool_server
```

**启动（按顺序：先工具服务，再主程序）：**

```bash
docker compose up -d
```

> 若不使用 compose，也可分开启动两个容器：
>
> ```bash
> # 容器 1：工具服务（监听 8000）
> docker run -d --name tool_server --env-file .env \
>   -e TOOL_SERVER_HOST=0.0.0.0 -p 8000:8000 \
>   dengyu-han/react-rag-agent:latest python tool_server.py
>
> # 容器 2：主程序（交互式）
> docker run --rm -it --env-file .env -e TOOL_SERVER_URL=http://tool_server:8000 \
>   --link tool_server -v "$(pwd)/chroma_db:/app/chroma_db" \
>   dengyu-han/react-rag-agent:latest python agent.py
> ```

### 步骤 5：验证运行

```bash
# 验证工具服务可达
curl -X POST http://localhost:8000/tools/web_search \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "max_results": 1}'
```

- 主程序启动后，输入一个知识库相关问题，观察是否正确召回并作答。
- 查看 `docker logs -f agent` 日志，确认工具调用链路正常。

## 5. 常见问题排查

| 现象 | 可能原因 | 处理 |
| --- | --- | --- |
| 拉取镜像失败 / 超时 | 网络受限或镜像地址不对 | 配置国内镜像加速器，或改拉内网私有仓库的镜像地址 |
| `docker: command not found` | Docker 未安装或未启动 | 安装并启动 Docker（Desktop），确认 `docker run hello-world` 正常 |
| `未配置 TAVILY_API_KEY` | `.env` 未创建或未填 | 检查 `.env` 是否存在且变量名正确，并确认 compose/`--env-file` 已指定 |
| 模型调用鉴权失败 | `API_KEY` 无效 | 核对火山方舟控制台 Key，确认账户有额度 |
| 端口被占用 | 8000 端口已有进程 | 结束占用进程，或修改 `docker-compose.yml` 的映射如 `8001:8000` |
| 检索不到知识库内容 | 未执行入库 / 文档格式不符 | 完成步骤 3，确认文档为 `.pdf` / `.txt` 且 `file_list` 路径正确 |

## 6. 注意事项

- 模型服务地址（`base_url`）与模型名硬编码在 `agent.py` 中（火山方舟 Ark）。切换到自研 / 其他模型服务时，需重新构建镜像并推送，目标机再 `docker pull` 拉取新镜像。
- 修改 `agent.py` / `tool_server.py` / `chroma.py` 后，需在本机构建新镜像并 `docker push`（并更新 tag），目标机 `docker pull` 即可升级，无需改动目标机任何源码。