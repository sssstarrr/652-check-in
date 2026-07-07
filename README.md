# 652 打卡桌面版

独立的 Python + PyQt5 桌面工具，只实现 SUSE OAA 中的 652 打卡能力：密码登录、短信二次验证、微信扫码登录、任务刷新、位置签到、账号与 Session 管理。

## 获取源码

```powershell
gh repo clone sssstarrr/652-check-in
cd 652-check-in
```

## 运行

```powershell
python -m pip install -r requirements.txt
python main.py
```

如学校后续更换微信扫码登录 App ID，可在启动前设置环境变量覆盖：

```powershell
$env:SUSE_WECHAT_APP_ID="你的微信 App ID"
python main.py
```

## 功能

- 密码登录：获取 UIAS 登录页、解析 `execution`、显示验证码、RSA 加密反转后的密码、提交登录并跟随 SSO 重定向。
- 短信二次验证：登录页触发短信验证时，支持发送短信验证码并继续提交。
- 微信扫码登录：获取 `clientId` 和二维码，2 秒轮询扫码状态，确认后解析 `_sop_session_` 并换取 qfhy `SESSION`。
- 打卡：拉取待签到/已完成/缺勤任务，获取任务详情，判断已签到/无任务/异常，提交位置签到 JSON。
- 多账号管理：支持添加账号、账号下拉切换、账号管理表格、删除账号、修改账号校区、单账号打卡和全部账号批量打卡。
- 定时自动打卡：可在设置中启用每日固定时间自动打卡，支持“全部账号”或“当前账号”，每天只触发一次。
- 账号存储：JSON 保存账号元数据，密码默认不保存；勾选记住密码后优先使用系统 keyring，失败时降级为本地 AES-GCM 加密文件。
- 安全日志：密码、Cookie、Session、Token、Ticket 只输出截断后的调试信息。

## 多账号使用

1. 点击主界面的“添加账号”，可继续添加密码登录或扫码登录账号。
2. 通过“当前账号”下拉框切换账号，任务刷新和“一键打卡”只作用于当前账号。
3. 点击“账号管理”可查看所有账号、切换当前账号、删除账号、修改账号校区。
4. 点击“全部打卡”会按账号列表逐个执行签到；Session 已过期的账号会提示重新登录。

## 定时自动打卡

1. 点击“设置”，勾选“启用定时自动打卡”。
2. 默认时间为 `19:31`，也可以自行修改；选择“全部账号”或“当前账号”。
3. 程序需要保持运行；关闭主窗口会隐藏到系统托盘，托盘菜单中的“退出”才会真正结束程序。
4. 到达设定时间后，当天只会触发一次；如果程序在设定时间之后启动，会在启动后补执行当天这一次。
5. 执行结果会写入主界面日志和账号上次状态。

## GitHub Actions 定时打卡

仓库内置无界面入口 `python -m app.cli.checkin_once` 和每日定时 workflow：`.github/workflows/daily-checkin.yml`。
默认按北京时间 `19:31-20:31` 多次尝试，workflow 内部会设置 `CHECKIN_TIMEZONE=Asia/Shanghai`。

详细配置步骤见 [GitHub Actions 每日定时打卡教程](docs/github-actions.md)。

## 打包

```powershell
cd 652-check-in
python -m pip install pyinstaller
scripts\build_windows.bat
```

输出目录位于 `dist/652-Checkin-Desktop`。

## 常见问题

- 无法获取验证码：检查校园网/外网是否能访问 `https://uias.suse.edu.cn`。
- 登录后没有 SESSION：通常是 UIAS 到 qfhy 的 SSO 重定向失败，可重新登录或改用扫码登录。
- 扫码后无法打卡：确认 `_sop_session_` 尚未过期，必要时重新扫码。
- keyring 不可用：程序会自动降级到本地加密文件，仍不保存明文密码。

## 开发验证

```powershell
cd 652-check-in
python -m unittest discover -s tests
python -m compileall app
```
