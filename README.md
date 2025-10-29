# School-Library-Management

基于 Flask 的学校图书馆管理系统，支持 Docker 一键部署。系统提供图书、分类、读者、借阅归还、统计分析以及系统用户管理等功能，前后端同域运行，支持 PC 端与移动端的响应式访问。默认使用 SQLite 数据库，亦可连接 MySQL 8。 

## 功能概览

- 图书基础信息管理：新增/编辑/删除、批量导入、Excel 导出、快速搜索。
- 图书分类管理：树形父子分类维护。
- 读者管理：新增/编辑/删除、批量导入、Excel 导出。
- 年级与班级管理：独立维护年级与班级并关联读者。
- 借书管理：通过读者卡号 + ISBN 借阅，控制库存与归还状态。
- 归还管理：通过读者卡号 + ISBN 归还，记录归还历史。
- 统计分析：借阅/归还趋势图、年级班级统计表、在库情况、超期统计。
- 系统管理：管理员可维护系统用户、重置密码等。

## 快速开始

### 环境要求

- Python 3.11+
- （可选）MySQL 8.0+

### 本地运行

1. 创建并激活虚拟环境，安装依赖：

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows 使用 .venv\\Scripts\\activate
   pip install -r requirements.txt
   ```

   **提示**：若仅需运行数据库初始化等命令而暂不使用 Excel 导入/导出功能，可先跳过安装 `openpyxl`。当系统检测到缺少该依赖时，会在页面上给予提示并引导执行 `pip install openpyxl`。

2. （可选）如需使用 MySQL，请设置数据库连接并初始化：

   ```bash
   export DATABASE_URI="mysql+pymysql://library:library@localhost/library"
   export SECRET_KEY="change-me"
   flask --app wsgi init-db
   flask --app wsgi seed
   ```

   如不设置 `DATABASE_URI`，系统将会在 `instance/library.sqlite` 中自动创建 SQLite 数据库文件。

3. 初始化并启动开发服务器：

   ```bash
   flask --app wsgi init-db
   flask --app wsgi seed
   flask --app wsgi run --debug
   ```

   默认管理员账号密码为 `admin/admin123`。

### Docker 部署

1. 启动容器：

   ```bash
   docker compose up -d --build
   ```

   若仅使用 SQLite，可直接通过 Docker CLI 启动单个容器：

   ```bash
   docker build -t school-library .
   docker run -d \
     --name school-library \
     -p 5000:5000 \
     -e SECRET_KEY=change-me \
     -v "$(pwd)/instance:/app/instance" \
     school-library
   ```

2. 首次启动后进入容器执行数据库初始化：

   ```bash
   docker compose exec web flask --app wsgi init-db
   docker compose exec web flask --app wsgi seed
   ```

3. 访问 `http://localhost:5000` 使用系统。

### 数据导入模板

批量导入图书与读者时，请准备包含表头的 Excel 文件，字段顺序参照页面提示：

- 图书：书名、ISBN、分类、索书码、位置、数量、价格、出版社、作者、简介。
- 读者：卡号、姓名、电话、性别。

## 目录结构

```
app/
  __init__.py
  extensions.py
  models.py
  views/
  templates/
  static/
docker-compose.yml
Dockerfile
requirements.txt
wsgi.py
```

## 许可证

本项目基于《个人及非盈利组织非商业使用许可》发布，仅允许个人或非盈利组织在非商业场景下使用、复制、修改与分发，任何商业用途须事先获得书面授权。详情请参阅 [LICENSE](LICENSE)。
