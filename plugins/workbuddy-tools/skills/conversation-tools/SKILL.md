---
name: conversation-tools
description: 本地会话分支和用户显式选择的最小风格 seed 的使用说明。
disable-model-invocation: true
user-invocable: true
allowed-tools: []
---
这是说明技能，不授权模型写入会话文件或数据库。
执行操作必须使用项目原生 UserPromptSubmit hook 的固定命令：
- `/workbuddy-tools:points` 查看当前会话可用完整回复 ID。
- `/workbuddy-tools:branch {"at":"latest","title":"分支名称"}` 或将 at 设为完整回复 UUID。
- `/workbuddy-tools:style-new {"seed":"/绝对路径/minimal-seed.json","title":"新会话"}`
- `/workbuddy-tools:recover {"operation_id":"操作 UUID"}`
- `/workbuddy-tools:status`
参数是 JSON，不是 shell。不要把参数插入 shell，也不要替代 hook 调用任何写入工具。
如果 hook 未生效，停止并提示运行 `scripts/manage.py check`；不要自动模仿此操作。
