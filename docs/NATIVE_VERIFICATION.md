# 原生 Windows 验证协议

此协议验证真实宿主，而非只把 Windows 分支代码跑在 Linux。使用现有可信安装，无下载、无账号、无模型调用；不修改 WorkBuddy 安装目录或现有 profile。

## 前置证据

记录 WorkBuddy EXE 文件版本、bundled CLI package 版本和实际 hook event.version。当前固定适配 Windows WorkBuddy 5.9.3 / CLI 2.165.0；仅 package 静态版本不足以证明 hook 动态契约。

确认 `python.exe` 3.10+、`pwsh` 7 与可信 `node.exe` 路径。若厂商只提供 `resources/vendor/node.zip`，允许将已核实的该归档解压到新建临时测试目录，**不写回厂商安装目录、不安装软件、不改执行策略/沙箱设置**。应使用官方配套 Node；替代 Node 必须记录版本及兼容性限制。

## 合成测试

```powershell
Set-Location "$Repo\src\plugin"
& $Python -X utf8 -m unittest discover -s tests -v
Set-Location $Repo
& $Python -X utf8 -m unittest discover -s tests -v
```

Windows 必须实际运行 `test_powershell_real_parser_and_error_guard` 和 Windows 文件锁测试；不得把其跳过当通过。POSIX 特有测试在 Windows 跳过是预期。symlink 权限缺失需明确报告，而不是更改系统权限。

PowerShell 测试覆盖空格、单引号、`$`、`&`、反引号、分号、括号和非 ASCII 路径；最终 **pwsh 进程退出码**必须为 2，不能只证明 Python 返回 2。Python 返回 1、2 或解释器缺失都要映射为 2。

## 原生隔离回归

选择短的、全新的本地 NTFS 临时目录，避免借此修改系统长路径策略：

```powershell
$Out = Join-Path $env:TEMP ('wb-smoke-' + [guid]::NewGuid().ToString('N').Substring(0,8))
& $Python -X utf8 "$Repo\scripts\native_smoke.py" --node $Node --cli $Cli --output $Out
```

脚本拒绝已有输出目录；构造隔离 HOME、USERPROFILE、APPDATA、LOCALAPPDATA、profile 和 workspace，子进程环境只继承必要系统路径，不继承 API keys。源历史和数据库均为合成数据。

必须证明：

- 官方 plugin validate / marketplace add / install / list 成功。
- 实际 `UserPromptSubmit` 触发且版本匹配；统一命名空间的五个命令走本地 hook。
- 选定边界新会话不含后续回复，源数据库行不变；不会写源 JSONL。
- seed reasoning 原生 EOF resume/fork 保留；API duration 0，未触发登录/模型路径。
- 项目 hook 重复安装仅一个路由入口，卸载仅去掉本工具入口，保留其它设置。
- 操作后回执可核查；GUI 打开、真实模型效果不属于此自动化证明。

## 退出码丢输出压力门槛

额外重复至少五次独立 `style-new`，每次使用唯一 operation UUID。每次都应成功返回回执，并且没有 Authentication required、模型调用或付费请求。

在合成项目内，暂时把**整个 hook shell 复合命令**的 stdout/stderr 丢弃，实际宿主仍必须根据最终 shell 退出码 2 阻断。不能只重定向复合命令最后一个子句。随后恢复合成配置。

同样测试缺失 Python／缺失 handler，必须阻断；普通 prompt 和其它 namespace 在依赖完好时静默退出 0。缺少宿主 shell 本身不在插件可执行范围内，应作为部署阻断项，不标记通过。

保留合成 `result.json`、日志和测试文件 SHA256。测试失败先诊断，不修改真实账号、真实历史或系统安全配置，也不把部分通过写成 Windows 已完成。

## 云 CI

普通 GitHub Actions 运行 Windows/Linux 的无宿主合成测试。原生 workflow（相关代码 push/PR 自动触发，也支持手动）已使用 `ci/workbuddy-windows-pin.json` 固定的官方 5.9.3.42398134 安装包。完整下载的 SHA256 与官方元数据吻合；格式确认为 NSIS-3 Unicode。`prepare_windows_runtime.ps1` 使用预装 7-Zip 静态提取 `$PLUGINSDIR/app-64.7z`，再提取 `resources/vendor/node.zip`，校验 Node 22.22.2 与 CLI package 2.165.0；从不运行安装器。不得用猜测链接、第三方镜像或未固定版本替代。workflow 存在不代表 Windows 已通过，须核查实际任务结果。
