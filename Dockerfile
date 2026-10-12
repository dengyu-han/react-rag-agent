# 基础镜像：官方 Python 3.11 精简版
FROM python:3.11-slim

# 设定工作目录（容器内的 /app）
WORKDIR /app

# 先复制依赖清单并安装（单独一层，依赖不变时能命中缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 再复制代码（三个入口脚本）
COPY agent.py tool_server.py chroma.py ./

# 默认启动 agent，docker-compose 里可覆盖
CMD ["python", "agent.py"]