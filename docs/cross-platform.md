# TokenBots：Mac / Windows / Linux / Codex CLI 接入

这里的跨环境配置指操作系统、桌面版和 CLI 的适配，不等于客户账号隔离。
同一份私有包可用于自己的不同电脑。不要把带 access.json 的包交给其他客户。

## 准备

1. 完整解压 ZIP。安装 Node.js 20 或更新的 LTS（包含 npm，https://nodejs.org/）。重新打开终端。
2. 桌面用户保留已安装的官方 Codex / ChatGPT 应用；CLI 用户可运行下面的 install-cli，安装我们验证的 Codex CLI 0.163.0 独立副本。不需要管理员权限，不替换全局 CLI。
3. 在解压后的目录打开终端。下面 `node ./tokenbots.cjs` 在 Windows PowerShell、macOS Terminal 和 Linux 终端都一样。

## CLI 用户（三个系统，包括 WSL）

```text
node ./tokenbots.cjs install-cli
node ./tokenbots.cjs setup --target cli --access ./access.json
node ./tokenbots.cjs run
```

Windows 也可双击 setup-cli.cmd，之后双击 start-cli.cmd。仍需先安装 Node.js 和 Codex CLI。
Mac / Linux 可用 `sh ./tokenbots.sh run`。macOS 可执行 setup-cli.command；被系统阻止时用终端命令，不关闭系统保护。

CLI 使用 `~/.tokenbots-codex`，保留原 `~/.codex` 和官方登录。必须从上述 run 入口启动：它只给子进程设置接入 Key，Key 不出现在命令行或 config.toml。
进入项目目录后，可用 `node /完整路径/tokenbots.cjs run`；路径带空格请加双引号。
把 Codex 参数放在 `--` 后，例如：

```text
node ./tokenbots.cjs run -- exec --sandbox read-only "查看这个项目并概述，不修改文件"
```

WSL 是独立 Linux 环境，要在 WSL 内安装 Node/CLI 并配置自己的 Linux home；不修改 Windows 用户目录。
同时安装多个 CLI 时，工具优先使用自己的固定版本副本；用 `run --codex /绝对路径/codex -- ...` 指定其他版本。

## 已安装桌面版的用户（Mac / Windows / Linux）

**完全退出桌面应用，再执行：**

```text
node ./tokenbots.cjs setup --target desktop --access ./access.json
```

Windows 可双击 setup-desktop.cmd；Mac 可用 setup-desktop.command。重新打开原应用，新建本地对话。
配置目标为当前环境的 `CODEX_HOME`，没设置时用用户目录下 `.codex`。官网和 Store 的安装目录都不需要修改。
如果应用在另一台设备、另一用户或隔离容器内运行，需要在那个环境内执行；可用 `--home /实际配置目录` 明确指定。
工具保留原配置的其他设置，替换当前模型提供商及模型，移除 Fast service_tier；重写 TOML 会整理格式/注释，完整原文件已备份。
如原配置选择了 profile，工具将其有效设置（包括审批与权限）合并保留到主配置，再切换提供商；原 profile 文件不变，回退会恢复原选择。缺失或无效的 profile 会停止安装，不静默丢弃设置。
桌面接入 Key 存在受限配置文件中，勿分享配置或备份。不会修改官方 auth.json 或历史会话。

**这个通用接入工具不注入原生菜单。** Windows 原生用量菜单仍使用独立的 Native-Usage 定制副本安装包。Mac/Linux 的原生菜单没有完成适配与桌面 UI 实测，不要把通用配置成功理解为已有原生菜单。

## 用量、号池、实际问答

CLI 默认读取独立 home；桌面用户在以下命令末尾加 `--target desktop`（自定义 home 则仍带 `--home`）。

```text
node ./tokenbots.cjs usage
node ./tokenbots.cjs usage --watch
node ./tokenbots.cjs pool auto
node ./tokenbots.cjs pool plus
node ./tokenbots.cjs pool pro
node ./tokenbots.cjs probe
node ./tokenbots.cjs doctor
```

usage --watch 每 30 秒查询，Ctrl+C 停止，不消耗模型 Token。未知/过期窗口不会显示成 100%。
切换号池前结束当前任务，切换后新建对话。同一个 Key 的号池选择对其所有设备生效。
probe 会用 gpt-6.1-sol / low 实际提问，只有返回 42 且收到完成事件才通过；会消耗少量订阅额度，不更改默认模型。
平台不设消费上限不等于上游订阅无限使用。

## 更新与回退

- 更新接入地址/Key：解压新的私有包，再运行同一种 setup；每次都新建备份。先保存并退出应用/CLI。
- 更新 CLI：收到经过测试的新包后执行 install-cli。版本锁定在包内，不盲目追随 latest。
- 恢复本次配置：`node ./tokenbots.cjs rollback`；桌面加 `--target desktop`。严格按逆序恢复到上一次配置。
- 如果配置在安装后被手工改过，自动回退会停止，避免覆盖新修改；备份位置在 `.tokenbots-setup`，里面有完整原配置，需合并恢复。
- 回退不删除聊天记录，不卸载官方应用。CLI 独立副本在 `~/.tokenbots-tools`，不用时可以保留。
- 不要把 access.json、config.toml、备份或完整日志发群；报错时只提供脱敏信息及 doctor 的环境/版本。

## 验证范围

跨平台 CI 验证配置、更新、回退、中文/空格路径以及真实 Codex CLI 对本地模拟 Responses 流的消费；这不等于云端真实推理或桌面 UI 验证。云端推理与各桌面原生菜单需要分别实测。
官方配置说明：https://learn.chatgpt.com/docs/config-file/config-advanced
官方 CLI：https://learn.chatgpt.com/docs/codex/cli


## 模型与推理强度（2026-10-18）

现在可在 Codex 原生选择器或 CLI `--model` 中选择 GPT-6.1 Sol、GPT-6 Astra、GPT-6 Sol、GPT-6 Luna、GPT-5.6 Sol、GPT-5.6 Terra、GPT-5.6 Luna。安装时保留已有的有效模型与推理强度；没有有效选择时使用 Astra / high。`probe` 仍固定用 Sol / low 做低消耗连通检查，不代表你的日常模型被切换。

CLI 示例：`./tokenbots.sh run -- --model gpt-6-astra -c 'model_reasoning_effort="high"'`。Windows 使用 `tokenbots.cmd`。模型与推理参数原样转发，不把 Astra 静默替换成 Sol。可用强度依模型和客户端能力显示；Ultra 是 Codex 的客户端工作模式，实测当前客户端将上游强度设为 xhigh，不能把 raw API 的 effort 直接写成 ultra。
