.PHONY: dev dev-down dev-build dev-logs up down build logs clean dev-clean prune help

# 默认命令，显示帮助信息
help:
	@echo "可用命令列表:"
	@echo "  --- 开发模式 (含热更新和源码挂载) ---"
	@echo "  make dev         - 启动开发环境 (后台运行)"
	@echo "  make dev-down    - 停止开发环境"
	@echo "  make dev-build   - 重新构建开发镜像"
	@echo "  make dev-logs    - 查看开发容器日志"
	@echo "  --- 生产模式 (使用构建好的镜像) ---"
	@echo "  make up          - 启动生产环境 (后台运行)"
	@echo "  make down        - 停止生产环境"
	@echo "  make build       - 重新构建生产镜像"
	@echo "  make logs        - 查看生产容器日志"
	@echo "  --- 系统清理 ---"
	@echo "  make clean       - 停止生产容器并删除数据卷 (⚠️ 警告: 会删除数据库和 Redis 数据)"
	@echo "  make dev-clean   - 停止开发容器并删除数据卷 (⚠️ 警告: 会删除数据库和 Redis 数据)"
	@echo "  make prune       - 清理无用的 Docker 资源"

COMPOSE=docker compose -f compose.yaml
DEV_COMPOSE=docker compose -f compose.yaml -f compose.dev.yaml

# ================= 生产环境 =================
# 启动生产环境 (后台运行)
up:
	$(COMPOSE) up --build -d

# 停止生产容器
down:
	$(COMPOSE) down

# 构建生产镜像
build:
	$(COMPOSE) build

# 查看生产日志
logs:
	$(COMPOSE) logs -f

# ================= 开发环境 =================
# 启动开发环境
dev:
	$(DEV_COMPOSE) up --build -d

# 停止开发容器
dev-down:
	$(DEV_COMPOSE) down

# 构建开发镜像
dev-build:
	$(DEV_COMPOSE) build

# 查看开发日志
dev-logs:
	$(DEV_COMPOSE) logs -f

# ================= 清理工具 =================
# 清理生产环境 (包含数据卷)
clean:
	$(COMPOSE) down -v

# 清理开发环境 (包含数据卷)
dev-clean:
	$(DEV_COMPOSE) down -v

# 深度清理
prune:
	docker system prune -a --volumes
