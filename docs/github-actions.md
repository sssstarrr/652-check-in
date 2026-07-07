# GitHub Actions 每日定时打卡教程

> 只在你确认符合学校打卡规则、且允许使用自动化的前提下使用。不要把 Cookie、Session、密码发给任何人，也不要写进代码。

## 1. 工作方式

仓库内置了两个部分：

- `python -m app.cli.checkin_once`：无界面的单次打卡命令。
- `.github/workflows/daily-checkin.yml`：默认从北京时间 `19:30` 到 `23:55` 每 5 分钟尝试一次，也支持手动运行。

GitHub Actions 不能扫码、不能输入验证码、不能弹出桌面窗口，所以它只支持使用已有的 qfhy Cookie/Session 执行打卡。Session 过期后需要重新登录并更新 GitHub Secret。

## 2. 获取 QFHY_SESSION

推荐用桌面版获取：

1. 运行本项目打包出的 `652-Checkin-Desktop.exe`。
2. 用密码登录或微信扫码登录一次，并确认主界面能刷新任务。
3. 打开 Windows 路径：`%APPDATA%\SUSE-OAA-Checkin-Desktop\accounts.json`。
4. 找到对应账号的 `session_token` 字段，复制完整值。

也可以用浏览器开发者工具从 `https://qfhy.suse.edu.cn` 复制 Cookie，但必须包含可用的 `SESSION`；扫码登录场景可能还需要 `_sop_session_`。

## 3. 配置单账号

进入 GitHub 仓库：

1. 打开 `Settings`。
2. 打开 `Secrets and variables` -> `Actions`。
3. 在 `Repository secrets` 里新增：

| Name | Value |
|---|---|
| `QFHY_SESSION` | 粘贴完整 `session_token` / Cookie 字符串 |

如需修改校区，打开 `Repository variables` 新增：

| Name | Value |
|---|---|
| `CHECKIN_CAMPUS` | `宜宾`、`李白河` 或 `汇东` |

不配置 `CHECKIN_CAMPUS` 时默认使用 `宜宾`。

## 4. 配置多账号

多账号不要再设置 `QFHY_SESSION`，改用一个 Secret：`CHECKIN_ACCOUNTS_JSON`。

示例格式如下，真实 Cookie 只粘贴到 GitHub Secret，不要提交到仓库：

```json
[
  {
    "student_id": "账号1学号",
    "name": "账号1备注",
    "campus": "宜宾",
    "session": "粘贴账号1的完整 Cookie 字符串"
  },
  {
    "student_id": "账号2学号",
    "name": "账号2备注",
    "campus": "汇东",
    "session": "粘贴账号2的完整 Cookie 字符串"
  }
]
```

每个账号可单独设置：

| 字段 | 说明 |
|---|---|
| `student_id` | 账号标识，用于日志显示 |
| `name` | 可选备注 |
| `campus` | `宜宾`、`李白河` 或 `汇东` |
| `session` / `cookies` / `session_token` | 完整 Cookie 字符串 |
| `location_mode` | 可选：`default`、`fixed`、`random` |
| `location_index` | `fixed` 模式下的位置序号，从 `0` 开始 |

## 5. 调整时间

默认 workflow：

```yaml
schedule:
  # GitHub cron 使用 UTC。这组重试覆盖北京时间 19:30-23:55。
  - cron: "30,35,40,45,50,55 11 * * *"
  - cron: "*/5 12-15 * * *"
```

表示每天北京时间 `19:30` 到 `23:55` 每 5 分钟尝试运行。要改时间，编辑 `.github/workflows/daily-checkin.yml` 里的 `cron`，注意要换算成 UTC。

workflow 会在运行时设置：

```yaml
CHECKIN_TIMEZONE: Asia/Shanghai
TZ: Asia/Shanghai
```

这会让提交给学校接口的 `qdsj` 使用北京时间，避免 GitHub runner 默认 UTC 导致“签到时间与服务器时间差异较大”。

当天任意一次运行成功后，后续定时任务会先检测成功标记和当天历史成功 run，命中后直接跳过，不再安装依赖或访问学校接口。这样做是为了避开 GitHub schedule 偶尔延迟或漏掉单个时间点的问题。

建议不要设置在整点，例如 `07:00`，因为 GitHub Actions 整点任务较多，可能延迟更明显。

## 6. 手动测试

1. 打开仓库的 `Actions` 页面。
2. 选择 `Daily 652 Check-in`。
3. 点击 `Run workflow`。
4. 第一次建议勾选 `dry_run`，它只检查 Secret 是否能读取、账号配置是否能解析，不会访问学校接口。
5. dry-run 通过后，再不勾选 `dry_run` 手动运行一次，查看日志。

日志里不会打印 Cookie，但会显示账号数量、校区、打卡结果和任务名称。

## 7. 常见问题

### 配置错误：请设置 QFHY_SESSION

没有配置 `QFHY_SESSION`，也没有配置 `CHECKIN_ACCOUNTS_JSON`。至少配置其中一个。

### 获取任务列表失败或未找到可用 Session

Session 已过期，重新用桌面版登录，然后更新 GitHub Secret。

### 系统未找到你的身份信息

`QFHY_SESSION` 已经不被学校系统识别，或只复制了短期 `SESSION`。请重新用桌面版登录，打开 `%APPDATA%\SUSE-OAA-Checkin-Desktop\accounts.json`，复制对应账号的完整 `session_token`。日志里的 `Cookie 检查` 最好显示 `SESSION=是, _sop_session_=是`。

### 签到时间与服务器时间差异较大

使用旧版 workflow 时，GitHub runner 默认 UTC，提交时间会和学校服务器北京时间差 8 小时。更新到新版 workflow 后重新手动运行一次；新版会设置 `CHECKIN_TIMEZONE=Asia/Shanghai`。

### 定时没有准时运行

GitHub Actions 定时任务不是秒级调度，可能延迟几分钟甚至更久。workflow 必须在默认分支上，仓库 Actions 也必须启用。默认配置会在北京时间 `19:30-23:55` 每 5 分钟尝试一次，降低单个 cron 点没有及时触发的影响。

如果当天已经手动运行成功，后面的定时任务也会跳过，因为 workflow 会读取当天历史成功 run。

### 想换校区或位置

单账号可设置仓库变量 `CHECKIN_CAMPUS`。多账号可在 `CHECKIN_ACCOUNTS_JSON` 每个账号对象里设置 `campus`、`location_mode`、`location_index`。
