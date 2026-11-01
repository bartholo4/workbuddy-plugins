# WorkBuddy 会话分支／思考风格 seed 原生插件

一个原生插件，同时提供会话分支和显式最小思考风格 seed。**Windows 优先，Linux 回归**；不是独立 GUI，不是 Git 分支工具。

安装名 `workbuddy-tools`，统一命名空间 `/workbuddy-tools:`。代码位于一个仓库，可公开发布；不包含私人 seed 或账号历史。

当前版本 `0.2.0`。已在 GitHub 云端 Windows Server 2025 上使用官方 WorkBuddy 5.9.3.42398134 / CLI 2.165.0 完成真实原生回归；Windows/Linux × Python 3.10/3.12 合成测试也全部通过。覆盖原生 CLI、hook、会话持久化和本地登记，不冒充桌面 GUI 或真实模型效果验证。详细证据见 [VERIFICATION.md](VERIFICATION.md)。

## 安装前检查

- Windows：WorkBuddy 5.9.3，bundled CLI package 2.165.0；已完成固定版本真实原生云端回归；未知 CLI 版本或数据库结构会拒绝写入。
- Linux：WorkBuddy 5.6.2.40046327 / CLI 2.147.0，最终合并版本的原生分支、hook、seed、DB 及丢输出 fail-closed 压力回归均已通过。
- Python **3.10+**，Windows 还必须有 **PowerShell 7 `pwsh`**，并可被 WorkBuddy 子进程 PATH 找到。不会安装软件或更改执行策略。
- 仅支持本地磁盘；拒绝 UNC、junction/reparse point、符号链接。Windows 新会话原子发布需要支持硬链接的文件系统（通常 NTFS）；不宣称网络盘/FAT 支持。
- Node/CLI 使用你确认的官方安装文件或受信任的现有 Node；不从网络下载运行时。部分 Windows 安装把 bundled Node 留在 `resources/vendor/node.zip`，本工具不擅自解压或修改厂商安装。

```powershell
py -3 -X utf8 .\plugins\workbuddy-tools\scripts\discover.py
Get-Command pwsh
```

`discover.py` 只查标准安装路径；非标准安装可先设置 `$env:WORKBUDDY_INSTALL_DIR`。结果仅为候选，必须确认属于目标 WorkBuddy 安装。可以直接给脚本明确的 `--cli` 与 `--node`。

## Windows PowerShell 安装

将仓库放到固定目录，不要在安装后移动。下面变量改为你实际路径：

```powershell
$Repo = 'C:\Tools\workbuddy-plugins'
$Python = 'C:\Path\To\python.exe' # 3.10+
$Node = 'C:\Path\To\node.exe'
$Cli = 'C:\Path\To\WorkBuddy\resources\app.asar.unpacked\cli\bin\codebuddy'
$Project = 'C:\Projects\My Project'
$env:CODEBUDDY_CONFIG_DIR = Join-Path $HOME '.workbuddy'
$env:WORKBUDDY_CONFIG_DIR = $env:CODEBUDDY_CONFIG_DIR
$env:CODEBUDDY_FORCE_LITE_WB_BUNDLE = '1' # Windows pinned distribution ships lite-WB only
& $Node $Cli plugin validate $Repo
& $Node $Cli plugin marketplace add $Repo
& $Node $Cli plugin install 'workbuddy-tools@workbuddy-plugins'
& $Node $Cli plugin list --json
& $Python -X utf8 "$Repo\plugins\workbuddy-tools\scripts\manage.py" install --project $Project --cli $Cli --node $Node --hook-shell powershell
```

只需安装这一个插件。原生插件默认 hook 故意为空：宿主首次 prompt 存在异步加载竞态，因此确定性命令使用上述安装器注册的**项目级原生 UserPromptSubmit hook**。Windows 明确指定 `shell: powershell`，固定 argv 单引号转义；用户命令参数只从 stdin JSON 读取，从不拼进 shell。Linux 使用 `--hook-shell posix`，并设置 `CODEBUDDY_FORCE_HEADLESS_BUNDLE=1`（不要沿用 Windows lite-WB 变量）。

安装器保留其它 hooks/权限，首次备份 settings；插件使用唯一项目 router hook 按命名空间分发，避免宿主多 hook 结果聚合与快速退出丢 stdout 的问题。已处理命令无论成功或失败都使用原生退出码 2 阻断；shell 包装将解释器/脚本异常同样映射为 2，不依赖延时。普通 prompt 则无输出退出 0。共享 `.conversation-tools.json` 仅保存官方 CLI argv；不信任新工作区、不修改权限、账号、密钥或默认模型。

安装后重启会话或 `/reload-plugins`。先在实际 WorkBuddy 会话执行 `/workbuddy-tools:status`，必须看到本地适配器信息；若出现认证／模型回答或缺失 hook 结果，停止使用创建命令，检查实际宿主的 pwsh/Python PATH。shell 自身无法启动时，插件没有执行机会，宿主行为不在本工具控制内。用同一 Python 执行 `manage.py check --project $Project --hook-shell powershell` 检查插件。

## 使用

```text
/workbuddy-tools:points
/workbuddy-tools:branch {"at":"latest","title":"方案 B"}
/workbuddy-tools:branch {"at":"完整回复的小写 UUID","title":"从此处分支"}
/workbuddy-tools:style-new {"seed":"C:\\Templates\\we-need.json","title":"带 seed 的新会话"}
/workbuddy-tools:status
/workbuddy-tools:status
```

JSON Windows 路径反斜杠需写成 `\\`，也可以使用 `C:/Templates/we-need.json`。完成结果含新会话 UUID 与 `workbuddy://chat/<UUID>`，由你手动打开；GUI 跳转及列表刷新未验证。不自动向模型发 prompt。

`examples/minimal-seed.json` 与 `examples/we-need-demo.json` 在每个插件目录下，都是公开合成示例。后者是简短的 “We need” 规划摘要，不是私人思考记录。seed schema 1：1–2 组严格交替 user/assistant `{role,text}`；assistant 可带纯文本 `reasoning`。不允许 providerData、签名、旧环境、权限、凭证或任意历史结构。文件限 16 KiB，单条可见文字 2000 字、reasoning 4000 字。

已证明原生 JSONL 能保留 reasoning/rawContent；Linux 官方离线转换器在模型能力条件满足时能回填 reasoning_content。**没有调用真实模型验证效果，不保证 We need 措辞、固定风格、推理能力提升或原私人模板的等价效果**。默认关闭，只作用于显式创建的新会话，不切换模型。

## 安全与恢复

本工具从不写源历史/源 DB 行，只克隆并校验本次新目标。宿主自己可能追加 slash 命令与 hook 结果，因此不承诺整个源文件跨操作字节完全相等。未知 CLI 版本、schema、未闭合工具、子代理图或路径越界均拒绝写入。

官方 EOF fork 的选定边界不一定持久化；本工具核验克隆契约后，只原子修正新目标。操作回执保存 ID、摘要与状态，不存完整历史。DB insert-only 事务、幂等 UUID、提交前后摘要核验；不创建/迁移数据库。

```text
/workbuddy-tools:recover {"operation_id":"操作 UUID"}
/workbuddy-tools:recover {"operation_id":"操作 UUID"}
```

恢复只接受已准备摘要与归属一致的目标。来源/目标变化、未确定克隆或 schema 变化时保留诊断，不自动重克隆/删除。源桌面行变化可能导致登记恢复安全停止，需要人工核对。

## 卸载

```powershell
& $Python -X utf8 "$Repo\plugins\workbuddy-tools\scripts\manage.py" uninstall --project $Project --hook-shell powershell
& $Node $Cli plugin uninstall 'workbuddy-tools@workbuddy-plugins'
```

其它用户 hooks 保持不变。卸载依据持久安装归属删除自己的 hook，不删源/新会话、seed、回执或其它设置。不要移动安装目录后直接删除文件，先卸载原项目 hook。

## 构建与 CI

```text
python scripts/build_plugins.py
cd src/plugin
python -m unittest discover -s tests -v
cd ../..
python -m unittest discover -s tests -v
```

`src/plugin` 为共享实现与合成测试；`plugins/workbuddy-tools` 为原生插件产物；`.workbuddy-plugin/marketplace.json` 为原生 marketplace。GitHub Actions 在 Windows/Linux、Python 3.10/3.12 运行无 API 合成测试。CI 配置存在不等于远端 CI 已执行。

没有附加开源许可授权；公开可读不等于授权再分发，许可由所有者另行选择。发行物不含厂商二进制、私人历史、账户配置或原始私人项目引用文件。

## 可选真实宿主回归（不下载运行时）

```text
python scripts/native_smoke.py --node /absolute/node --cli /absolute/codebuddy --output /new/isolated/output
```

输出目录必须不存在。脚本仅新建合成 HOME/profile/workspace 和数据库，白名单环境不继承凭证；验证安装幂等、会话分支、reasoning EOF、归属卸载。普通 CI 不执行它；另外提供代码路径 push/PR 自动触发、也可手动执行的 `Native Windows WorkBuddy (pinned, synthetic)` workflow，固定官方安装包 SHA256，使用预装 7-Zip 静态提取而不运行安装器。实际宿主任务已通过；更新后仍应检查对应提交的 CI 结果。

官方 Windows 固定包证据见 `ci/workbuddy-windows-pin.json`；[官方更新元数据](https://www.workbuddy.cn/v2/update?platform=workbuddy-win32-x64-user) 与实际下载 SHA256 已核对。下载脚本不使用浮动 latest、不接受外部传入 URL、不携带账号密钥；完整验证范围见 [原生验证协议](docs/NATIVE_VERIFICATION.md)。
