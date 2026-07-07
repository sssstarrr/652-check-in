# Linux 服务器定时打卡教程

服务器 `cron` 是当前维护的自动打卡方案。它比 GitHub Actions 稳，因为触发时间由你的服务器控制，不依赖 GitHub 的 schedule 队列。

## 通用修复点

这份脚本已经处理了部署时常见的几个坑：

- 系统 `python3` 没有 `venv/pip`：可以在 `.env` 里设置 `CHECKIN_PYTHON=/path/to/python`，例如 Conda Python。
- 桌面版 `accounts.json` 不能直接用：现在支持 `CHECKIN_ACCOUNTS_FILE=accounts.json`，可直接读取其中的 `accounts` 数组。
- `--dry-run` 误写成功标记：现在 dry-run 只检查配置，不会生成 `.checkin-state/success-YYYY-MM-DD`。
- “无任务”误判为当天完成：服务器脚本会把无任务视为等待下一轮，不写成功标记；只有真正签到成功或已签到才跳过当天后续任务。

## 1. 部署代码

```bash
git clone https://github.com/sssstarrr/652-check-in.git
cd 652-check-in
cp .env.example .env
```

如果系统 Python 完整，可以先手动建环境：

```bash
python3 -m venv .venv-server
.venv-server/bin/python -m pip install -r requirements-action.txt
```

如果 `python3 -m venv` 报错，跳过这一步，在 `.env` 里设置：

```bash
CHECKIN_PYTHON=/data/home/你的用户名/miniconda3/bin/python
```

脚本第一次运行时会自动用这个 Python 创建 `.venv-server`。

## 2. 配置账号

推荐直接使用桌面版生成的 `accounts.json`：

1. 在 Windows 桌面版登录并确认能刷新任务。
2. 找到 `%APPDATA%\SUSE-OAA-Checkin-Desktop\accounts.json`。
3. 上传到服务器仓库根目录，例如 `/path/to/652-check-in/accounts.json`。
4. 编辑 `.env`：

```bash
CHECKIN_ACCOUNTS_FILE=accounts.json
```

也可以只配置单账号 Cookie：

```bash
QFHY_SESSION='SESSION=...; _sop_session_=...'
```

不要把 `.env`、`accounts.json`、日志或 `.checkin-state` 提交到 Git。

## 3. 手动测试

只检查配置，不访问学校接口：

```bash
CHECKIN_IGNORE_WINDOW=true bash scripts/server_checkin.sh --dry-run
```

真实执行一次，不受时间窗口限制：

```bash
CHECKIN_IGNORE_WINDOW=true bash scripts/server_checkin.sh
```

日志位置：

```text
logs/server-checkin-YYYY-MM-DD.log
```

成功标记：

```text
.checkin-state/success-YYYY-MM-DD
```

如果结果是“无任务”，脚本不会写成功标记，后面的 cron 会继续重试。

## 4. 配置 cron

当前维护的默认节奏是：每天北京时间 `19:05、19:35、20:05、20:35、21:05、21:35、22:05、22:35` 执行。任意一次真正成功或已签到后，当天后续任务会跳过。

编辑 cron：

```bash
crontab -e
```

如果服务器支持 `CRON_TZ`：

```cron
CRON_TZ=Asia/Shanghai
5,35 19-22 * * * cd /path/to/652-check-in && bash scripts/server_checkin.sh
```

如果服务器 cron 不支持 `CRON_TZ`，并且服务器系统时区不是北京时间，请按服务器实际时区换算后写入。

查看当前 cron：

```bash
crontab -l
```

## 5. 维护

更新代码：

```bash
cd /path/to/652-check-in
git pull --ff-only
```

重新测试：

```bash
CHECKIN_IGNORE_WINDOW=true bash scripts/server_checkin.sh --dry-run
```

Session 过期后，重新登录桌面版，再上传新的 `accounts.json` 或更新 `.env` 中的 `QFHY_SESSION`。
