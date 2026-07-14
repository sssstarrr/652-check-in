# 652 打卡 Android 版

这是一个独立、轻量的原生 Android 应用，对应桌面版的 652 签到功能。

## 功能

- 学校统一身份认证（密码、验证码、短信由学校官方 WebView 页面处理）
- 微信扫码登录
- Android Keystore AES-GCM 加密保存 Cookie，不保存学号密码
- 待签到任务、已完成历史和成功时间
- 宜宾、李白河、汇东校区一键签到
- SOP 登录态续期，续期时丢弃内存和存储中的旧 `SESSION`
- 每日后台定时签到（Android JobScheduler）及结果通知

## 安装

1. 从项目的 [GitHub Releases](https://github.com/sssstarrr/652-check-in/releases) 下载 `652-Checkin-Android-v1.0.0.apk`，或按照下方步骤自行构建。
2. 允许文件管理器安装未知来源应用，完成安装。
3. 在 App 内选择统一身份认证或微信扫码。

扫码登录需要另一台可使用微信扫码的设备。后台定时由 Android 系统调度，在省电或厂商后台限制下可能比设定时间延迟几分钟。

## 构建

已经验证的构建环境：

- Android SDK: `D:\Sdk`
- Android Studio JBR: `D:\Program Files\Android\Android Studio\jbr`
- Gradle Wrapper: 9.4.1
- AGP: 9.2.0
- compile/target SDK: 37，min SDK: 26

在 PowerShell 中执行：

```powershell
.\scripts\build_release.ps1
```

脚本优先读取 `ANDROID_SDK_ROOT`（其次是 `ANDROID_HOME`）和 `JAVA_HOME`，未设置时使用上面的 `D:` 路径。它会运行单元测试、Release Lint、构建和签名验证。项目路径包含中文时，脚本会临时映射到 `X:` 规避 Windows Gradle 测试路径问题。

发布密钥位于 `%LOCALAPPDATA%\Checkin652Android\signing`，密码文件由 Windows DPAPI 绑定当前用户加密。请备份该目录；丢失后无法以覆盖安装方式更新已安装的 App。

## 安全边界

- 登录凭据只输入学校官方 HTTPS 页面。
- App 仅保存服务器 Cookie，并使用 Android Keystore 密钥加密。
- 加密偏好数据排除在云备份和设备迁移之外。
- 退出登录会删除加密 Cookie 并取消后台任务。

上游开源代码许可信息见 `THIRD_PARTY_NOTICES.md`。
