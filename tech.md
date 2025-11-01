# School Library Management – 技术说明

## 概览
- **定位**：基于 Flask 的学校图书馆管理系统，涵盖图书、分类、读者、借阅归还、统计分析与系统用户管理，支持响应式前端和 SQLite/MySQL 数据库。系统支持 Docker 一键部署，方便快速上线。【F:README.md†L1-L90】
- **运行模式**：同域部署的服务端渲染应用，后端负责模板渲染与业务逻辑，前端通过定制的 CSS/JS 完成交互增强。【F:README.md†L1-L90】【F:app/static/js/app.js†L1-L24】【F:app/static/css/app.css†L1-L120】

## 技术栈
### 后端
- Flask 3 提供 Web 框架能力，Gunicorn 作为生产环境 WSGI Server。【F:requirements.txt†L1-L7】【F:Dockerfile†L1-L15】
- Flask-SQLAlchemy 管理 ORM，内置 SQLite 默认配置，可通过 `DATABASE_URI` 切换到 MySQL（PyMySQL 驱动）。【F:requirements.txt†L1-L5】【F:app/__init__.py†L85-L100】【F:docker-compose.yml†L3-L27】
- 自带精简版 Flask-Login 实现认证态管理，结合自定义用户模型完成登录、权限判定与导航过滤。【F:flask_login/__init__.py†L1-L97】【F:app/models.py†L21-L34】【F:app/__init__.py†L111-L143】
- Flask-Migrate 作为可选数据库迁移工具，若缺失则由扩展模块提供降级警告以保持 CLI 可用性。【F:requirements.txt†L2-L3】【F:app/extensions.py†L1-L51】

### 前端
- 采用 Jinja2 模板（`app/templates/`）输出页面，配合自定义样式与脚本组织导航、表单和响应式布局。【F:README.md†L101-L113】【F:app/static/css/app.css†L1-L120】【F:app/static/js/app.js†L1-L24】
- 顶栏/侧边栏配色与导航结构由 `SystemSetting` 数据和 `NAV_SECTIONS` 常量动态驱动，可按用户级别隐藏敏感入口。【F:app/__init__.py†L17-L142】【F:app/models.py†L164-L193】

### 数据库
- 核心模型覆盖图书、分类、年级、班级、读者、借阅、归还记录、系统设置等领域实体，统一继承时间戳与软删除混入类，便于审计和逻辑删除。【F:app/models.py†L12-L200】
- `ensure_seed_data` CLI 命令保证初始管理员账号存在，配合 `flask init-db` 命令完成首次安装流程。【F:app/models.py†L195-L200】【F:app/__init__.py†L175-L189】
- `docs/data-dictionary.md` 可补充字段定义与业务含义（供后续扩展时参考）。【F:docs/data-dictionary.md†L1-L200】

## 核心组件
| 组件 | 位置 | 说明 |
| ---- | ---- | ---- |
| 应用工厂 | `app/__init__.py` | 组装配置、注册扩展/蓝图、注入系统设置与分页辅助函数。【F:app/__init__.py†L82-L172】 |
| 扩展注册 | `app/extensions.py` | 延迟加载数据库、迁移与登录管理器，兼容缺失依赖场景。【F:app/extensions.py†L1-L51】 |
| 数据模型 | `app/models.py` | 定义所有业务实体与辅助查询方法，含库存计算、系统设置读写等。【F:app/models.py†L80-L193】 |
| 业务蓝图 | `app/views/` | 模块化划分认证、图书、分类、读者、借阅、统计、系统设置等路由。【F:app/__init__.py†L163-L172】【F:app/views/auth.py†L1-L82】【F:app/views/stats.py†L1-L118】 |
| 工具库 | `app/utils/` | 提供分类树构建、分页参数解析与导航链接生成等共用逻辑。【F:app/utils/category_tree.py†L1-L60】【F:app/utils/pagination.py†L1-L62】 |
| 静态资源 | `app/static/` | 自定义 CSS/JS、测试数据脚本等；`app/static/css/app.css` 管理布局与主题，`app/static/js/app.js` 控制移动端侧边栏交互。【36c81c†L1-L2】【5302cc†L1-L2】【F:app/static/css/app.css†L1-L120】【F:app/static/js/app.js†L1-L24】 |
| WSGI 入口 | `wsgi.py` | 暴露 `create_app()` 实例，供 Flask CLI 与 Gunicorn 载入。【F:wsgi.py†L1-L7】 |
| 部署脚本 | `Dockerfile`, `docker-compose.yml` | 构建镜像、编排 Flask + MySQL 服务，预置环境变量与端口映射。【F:Dockerfile†L1-L15】【F:docker-compose.yml†L1-L27】 |

## 目录结构
项目顶层主要目录如下（详见 README 目录结构）：【F:README.md†L101-L113】
```
app/               # Flask 应用源码
  static/          # CSS、JavaScript、图标等静态资源
  templates/       # Jinja2 模板
  views/           # 各业务蓝图
  utils/           # 通用工具函数
Dockerfile         # 生产镜像构建脚本
docker-compose.yml # MySQL + Web 服务编排
requirements.txt   # Python 依赖列表
wsgi.py            # WSGI 入口
```

## 配置与环境变量
- `SECRET_KEY`：Flask 会话密钥，Docker/生产环境必须显式设置。【F:app/__init__.py†L91-L99】【F:docker-compose.yml†L18-L24】
- `DATABASE_URI`：SQLAlchemy 数据库连接字符串；未设置时自动回退到 `instance/library.sqlite`。【F:app/__init__.py†L85-L103】
- 其他可选变量：部署时可挂载 `instance/` 目录持久化 SQLite 数据或存放上传文件。【F:README.md†L64-L81】

## 设计思路与业务流程
1. **导航与权限**：`NAV_SECTIONS` 定义模块化导航，`inject_system_settings` 根据用户角色过滤管理员专属菜单并注入模板上下文。【F:app/__init__.py†L17-L143】
2. **认证流程**：登录表单启用验证码校验，通过自实现的 `flask_login` 组件持久化用户会话，支持密码修改与注销。【F:app/views/auth.py†L1-L82】【F:flask_login/__init__.py†L1-L97】
3. **借阅统计**：统计模块结合 SQLAlchemy 查询与聚合函数，生成借阅/归还趋势、年级班级汇总以及超期情况列表。【F:app/views/stats.py†L1-L118】
4. **软删除与审计**：所有主要模型继承 `SoftDeleteMixin` 和 `TimestampMixin`，既保留记录又便于时间筛选统计。【F:app/models.py†L12-L148】
5. **分页体验**：通用分页工具将页面大小存入 Session 并自动生成链接，有效防止意外请求过大数据集。【F:app/utils/pagination.py†L1-L62】
6. **分类树展示**：分类管理使用 `build_category_tree`/`flatten_category_tree` 构造树状结构，方便模板渲染层级列表。【F:app/utils/category_tree.py†L1-L60】

## 编译、部署与运行
### 本地开发
1. 创建虚拟环境并安装依赖：`python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`。【F:README.md†L25-L33】
2. 初始化数据库并导入基础数据：`flask --app wsgi init-db`、`flask --app wsgi seed`。【F:README.md†L35-L55】【F:app/__init__.py†L175-L189】
3. 启动调试服务器：`flask --app wsgi run --debug`，默认账户 `admin/admin123`。【F:README.md†L46-L55】

### Docker 部署
1. `docker compose up -d --build` 启动 Web + MySQL 组合服务；或通过 `docker build`/`docker run` 构建单容器版本并挂载 `instance/` 数据目录。【F:README.md†L56-L81】【F:Dockerfile†L1-L15】【F:docker-compose.yml†L1-L27】
2. 容器首次运行后执行 `flask --app wsgi init-db` 与 `flask --app wsgi seed` 初始化数据库，可通过 `docker compose exec` 或 `docker exec` 触发。【F:README.md†L76-L88】
3. 生产服务入口由 Gunicorn 提供 (`wsgi:app`)，监听 `0.0.0.0:5000`。【F:Dockerfile†L1-L15】【F:wsgi.py†L1-L7】

### 数据导入
- 支持 Excel 批量导入图书与读者，字段顺序由页面提示控制；当 `openpyxl` 未安装时会提示安装补充依赖。【F:README.md†L33-L98】

## 打包与发布建议
1. **镜像构建**：使用提供的 `Dockerfile`（基于 `python:3.11-slim`）安装依赖并运行 Gunicorn，建议在 CI 中执行 `docker build -t <registry>/school-library:<version> .`。【F:Dockerfile†L1-L15】
2. **环境配置**：在部署平台（如 K8s、Swarm）中通过环境变量注入 `SECRET_KEY` 和 `DATABASE_URI`，并挂载 `instance/` 目录或配置外部数据库。【F:app/__init__.py†L85-L103】【F:docker-compose.yml†L18-L27】
3. **数据库迁移**：如需版本化 Schema，可在安装 `Flask-Migrate` 后初始化 Alembic 脚本，并在部署流水线中执行 `flask db upgrade`。缺失依赖时系统会回退为警告模式，仍可运行 `init-db` CLI。【F:app/extensions.py†L13-L51】
4. **静态资源**：CSS/JS 直接存放于仓库，无需额外打包工具，如需扩展可接入构建流程（例如 `npm`/`webpack`）并在 `app/static/` 下产出编译资源。【36c81c†L1-L2】【5302cc†L1-L2】

## 二次开发提示
- 模板渲染可通过 `system_nav_sections`、`system_logo_path` 等上下文变量定制主题与菜单，无需修改后端逻辑。【F:app/__init__.py†L115-L143】
- 扩展业务模型时记得继承混入类，并在 `ensure_seed_data` 附近增加默认记录或 CLI 命令，保持安装体验一致。【F:app/models.py†L12-L200】
- 新增蓝图请在 `register_blueprints` 中注册，同时更新 `NAV_SECTIONS` 以显示在导航栏中。【F:app/__init__.py†L17-L172】

