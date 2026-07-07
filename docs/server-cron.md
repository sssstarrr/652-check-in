# Linux 服务器定时打卡教程

服务器方案比 GitHub Actions 更稳，因为 `cron` 由你自己的服务器触发，不依赖 GitHub 的 schedule 队列。

## 1. 部署代码

```bash
git clone https://github.com/sssstarrr/652-check-in.git
cd 652-check-in
python3 -m venv .venv-server
.venv-server/bin/python -m pip install -r requirements-action.txt
```

如果系统没有 venv：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

## 2. 配置 Cookie

```bash
cp .env.example .env
nano .env
```

把桌面版 `accounts.json` 里的完整 `session_token` 填到：

```bash
QFHY_SESSION='SESSION=...; _sop_session_=...'
```

多账号可以改用 `CHECKIN_ACCOUNTS_JSON`，格式和 GitHub Actions 教程一致。

## 3. 手动测试

不受时间窗口限制，只检查配置：

```bash
CHECKIN_IGNORE_WINDOW=true bash scripts/server_checkin.sh --dry-run
```

真正执行一次：

```bash
CHECKIN_IGNORE_WINDOW=true bash scripts/server_checkin.sh
```

日志会写到：

```text
logs/server-checkin-YYYY-MM-DD.log
```

成功后会写入：

```text
.checkin-state/success-YYYY-MM-DD
```

同一天后续运行会直接跳过。

## 4. 配置 cron

推荐用“提前唤醒 + 脚本窗口判断”的方式。服务器从北京时间 16:01 到 23:56 每 5 分钟唤醒一次，脚本只有在 `.env` 里的 `CHECKIN_WINDOW_START=19:31` 到 `CHECKIN_WINDOW_END=23:55` 之间才真正打卡。

编辑 cron：

```bash
crontab -e
```

如果服务器支持 `CRON_TZ`：

```cron
CRON_TZ=Asia/Shanghai
1,6,11,16,21,26,31,36,41,46,51,56 16-23 * * * cd /path/to/652-check-in && bash scripts/server_checkin.sh
```

如果服务器 cron 不支持 `CRON_TZ`，按 UTC 写：

```cron
1,6,11,16,21,26,31,36,41,46,51,56 8-15 * * * cd /path/to/652-check-in && TZ=Asia/Shanghai bash scripts/server_checkin.sh
```

把 `/path/to/652-check-in` 换成真实仓库路径。

## 5. 常用调整

只想固定 19:31 执行一次：

```cron
31 19 * * * cd /path/to/652-check-in && bash scripts/server_checkin.sh
```

改打卡窗口：

```bash
CHECKIN_WINDOW_START=19:31
CHECKIN_WINDOW_END=21:30
```

更新代码：

```bash
cd /path/to/652-check-in
git pull --ff-only
```
