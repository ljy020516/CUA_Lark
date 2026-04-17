# CUA-Lark

让大模型像人一样操作飞书桌面客户端。

基于 **Qwen-VL** 多模态模型，通过 **感知 - 规划 - 执行** 循环，将自然语言指令转化为实际的鼠标键盘操作。

---

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt  # macOS 使用 requirements-macos.txt

# 2. 配置 API Key 和模型
cp .env.example .env
# 编辑 .env 填入 DASHSCOPE_API_KEY 和模型配置

# 3. 运行
python src/app/agent.py
```

### 模型配置

在 `.env` 文件中配置：

```bash
# API 配置
DASHSCOPE_API_KEY=your_api_key_here
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 模型配置
MODEL_IMAGE=qwen3-vl-flash      # 图像理解模型（规划阶段）
MODEL_TOOLS=qwen-vl-max         # 工具调用模型（ReAct 阶段）
MODEL_TEMPERATURE=0.2           # 温度参数
```

---

## 功能演示

```bash
# 给指定联系人发消息
"帮我给张三发送你好"

# 其他飞书操作（通用模式）
"打开审批页面"
"创建明天的日历事件"
```

---

## 核心架构

### 执行流程

```
用户指令 → 技能路由 → 规划阶段 → ReAct 执行循环 → 任务完成
                        ↓
              ┌─────────────────┐
              │  截图 + 网格 overlay │
              │       ↓          │
              │  LLM 决策下一步    │
              │       ↓          │
              │   执行动作       │
              └─────────────────┘
```

### 技术特点

| 特性 | 说明 |
|------|------|
| **网格定位** | 6×6 红色网格覆盖截图，LLM 选择编号而非像素坐标 |
| **技能系统** | 可插拔技能模块，当前支持 `send-message` |
| **Plan-then-ReAct** | 先生成计划，再逐步执行并动态调整 |
| **跨平台** | macOS (Quartz) / Windows (PyAutoGUI) |

---

## 项目结构

```
CUA-Lark/
├── src/
│   ├── app/              # Agent 主循环、工具函数、提示词
│   └── platforms/        # 平台适配层 (macOS / Windows)
├── skills/               # 技能定义 (SKILL.md + 运行时代码)
├── Prompt/               # 系统提示词模板
├── captures/             # 运行时截图（已忽略）
└── pyproject.toml
```

---

## 技能系统

技能是预定义的任务模板，包含：
- **触发条件**：什么用户指令激活该技能
- **执行流程**：标准操作步骤
- **约束规则**：防止错误操作的安全门控

### 内置技能

| 技能 | 触发模式 | 说明 |
|------|----------|------|
| `send-message` | "给 xxx 发消息 yyy" | 给指定联系人发送消息 |

### 添加新技能

在 `skills/` 目录下创建新文件夹，添加 `SKILL.md` 和对应的 Python 实现。

---

## macOS 权限要求

需要在 `系统设置 > 隐私与安全性` 中授予：
- **辅助功能**：控制键盘和鼠标
- **屏幕录制**：截取屏幕内容

---

## 依赖

- **模型**: Qwen-VL-Max / Qwen3-VL-Flash (阿里云百炼)
- **Python**: 3.10+
- **核心库**: dashscope, mss, Pillow, pyperclip, Quartz (macOS)

---

## License

MIT