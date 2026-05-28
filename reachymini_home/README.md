# Reachy Mini 智能家居语音控制系统

语音控制的智能家居演示系统，基于 Reachy Mini 机器人平台 + XIAO ESP32 C3 舵机控制器。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          用户侧 (PC Windows)                            │
│                    reachymini_home (Python SDK)                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  用户说话                                                                │
│    ↓                                                                   │
│  [ASR] 豆包实时语音识别 ─── WebSocket (wss://openspeech.bytedance.com)  │
│    ↓ 音频数据 ─── PCM 16kHz                                             │
│    ↓ 语音 → 文字                                                        │
│  [Brain] 豆包 LLM 意图解析 ─── HTTP (ark.cn-beijing.volces.com/api/v3)  │
│    ↓ user input + system_prompt                                        │
│    ↓ ← {reply, device_command}                                         │
│  ┌────────┬──────────────┐                                             │
│  ↓        ↓              ↓                                             │
│ [TTS]  [Actions]     [Network]                                         │
│ Edge   Reachy Mini    TCP Socket                                       │
│ TTS    运动控制         192.168.7.155:8080                              
│  ↓     ↓                ↓                                              
│ 音频   跳舞/睡眠姿态    命令字符串                                       
│ 播放   60Hz 控制        "Light_ON\n" / "Light_OFF\n"                  
└────────┴────────────────┴──────────────────────────────────────────────┘
                              │                    │
                              │    TCP            │
                              ▼                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     XIAO ESP32 C3 (Arduino)                            │
│  motor.ino                                                              │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │  WiFi Server (8080)                                              │   │
│  │    ├─ 接收 "Light_ON"  → 舵机位置 2300 (开灯)                   │   │
│  │    └─ 接收 "Light_OFF" → 舵机位置 2570 (关灯)                   │   │
│  └────────────────────────────────────────────────────────────────┘   │
│    │                                                                  │
│    ↓ 半双工串口 (1000000 baud)                                         │
│  [Bus Servo] 飞特总线舵机 (ID:1) ←── 角度控制                           │
│    │                                                                  │
│    ↓                                                                  │
│  [Light] 灯具 (继电器/舵机驱动的物理开关)                               │
└────────────────────────────────────────────────────────────────────────┘
```

## 文件结构

```
reachymini_smart_home/
├── reachymini_home/           # PC 端 Python 代码
│   ├── main.py                # 系统主入口，协调所有模块
│   ├── robot.py               # Reachy Mini 单例管理
│   ├── brain.py               # 豆包 LLM 意图解析
│   ├── asr.py                 # 豆包 ASR 语音识别 (WebSocket)
│   ├── tts.py                 # Edge TTS 语音合成
│   ├── audio.py               # 音频输入/输出 (麦克风阵列)
│   ├── network.py             # TCP 通信 (XIAO 舵机控制器)
│   ├── config.py              # 配置 (API密钥、IP地址、系统提示词)
│   ├── utils.py               # 工具函数
│   ├── actions/               # 动作模块
│   │   ├── poses.py          # 姿态定义 (中立/睡眠)
│   │   ├── move_queue.py     # 运动队列系统
│   │   └── light_actions.py  # 灯光动作 (开灯跳舞/关灯睡眠)
│   └── pyproject.toml         # 项目配置
│
└── XIAO ESP32 C3/             # XIAO 端 Arduino 代码
    └── motor.ino              # TCP 服务器 + 舵机控制
```

## 完整数据流

```
用户: "房间太暗了"
   │
   ▼
┌────────────────┐
│ [ASR]          │ ◄── 麦克风阵列 (Reachy Mini)
│  语音识别      │     WebSocket 连接豆包 ASR
│  16kHz PCM     │
└───────┬────────┘
        │ "房间太暗了"
        ▼
┌────────────────┐
│ [Brain]        │ ◄── System Prompt (灯具控制语义映射)
│  LLM 意图解析  │     HTTP POST 豆包-seed-character
└───────┬────────┘
        │ {"reply": "确实有些暗，Reachy为您开灯", "device_command": "Light_ON"}
        ▼
   ┌────┴────┬────────────┐
   ▼         ▼            ▼
┌──────┐ ┌────────┐ ┌─────────┐
│[TTS] │ │[Actions]│ │[Network]│
│Edge  │ │Reachy  │ │TCP      │
│TTS   │ │舞蹈动作 │ │XIAO     │
└──┬───┘ └───┬────┘ └───┬─────┘
   │         │          │
   ▼         ▼          ▼
temp_tts  跳舞1秒    "Light_ON\n"
.wav     →中立姿态   192.168.7.155:8080
   │                    │
   ▼                    ▼
[Audio]            ┌────────────────────────┐
播放                │ XIAO ESP32 C3          │
                   │ ├─ WiFi TCP Server 8080│
                   │ └─ processCommand()     │
                   │      └─ Pos=2300        │
                   │           │             │
                   │      [Bus Servo]        │
                   │           │             │
                   │        [Light ON]       │
                   └────────────────────────┘
```

## 核心模块说明

| 文件 | 作用 |
|------|------|
| `main.py` | 主入口，协调 ASR → Brain → TTS → Actions → Network 的完整流程 |
| `robot.py` | Reachy Mini 机器人单例管理，负责初始化媒体系统 |
| `brain.py` | 调用豆包 LLM API，将用户输入解析为 `{reply, device_command}` |
| `asr.py` | 通过 WebSocket 连接豆包实时语音识别，获取语音转文字 |
| `tts.py` | 使用 Edge TTS 将文字转为语音，生成 `.wav` 音频文件 |
| `audio.py` | 封装 Reachy Mini 麦克风阵列音频采集和扬声器播放 |
| `network.py` | 通过 TCP 发送命令到 XIAO 舵机控制器 |
| `config.py` | 所有配置：LLM API 密钥、ASR 凭证、XIAO IP/端口、TTS 声音 |
| `actions/light_actions.py` | 灯光动作：`Light_ON` 触发随机舞蹈，`Light_OFF` 进入睡眠姿态 |
| `actions/move_queue.py` | 运动队列管理器，60Hz 控制频率，支持舞蹈、 goto、情绪动作 |
| `motor.ino` | XIAO ESP32 C3：WiFi TCP 服务器，接收命令控制舵机角度 |

## 环境要求

- **Python 版本**: `3.12`
- **操作系统**: Linux / macOS / Windows
- **硬件**: Reachy Mini 机器人 + XIAO ESP32 C3 舵机控制器

## PC 端依赖安装

### 1. 安装 uv

```bash
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. 创建虚拟环境

```bash
uv venv reachy_env --python 3.12
reachy_env\Scripts\activate
```

### 3. 安装 Reachy Mini SDK

```bash
uv pip install "reachy-mini"
```

### 4. 安装舞蹈动作库

```bash
uv pip install "reachy-mini-dances-library"
```

### 5. 进入项目文件夹并安装依赖

```bash
cd reachymini_home
pip install -e .
pip install edge-tts soundfile scipy numpy
```

:::tip
Linux 系统需要额外安装：
```bash
sudo apt install -y libcairo2-dev libgirepository1.0-dev pkg-config python3-dev
```
:::

## XIAO ESP32 C3 配置

将 `motor.ino` 烧录到 XIAO ESP32 C3，配置以下参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| WiFi SSID | `SEEED-MKT` | 替换为你的 WiFi |
| WiFi Password | `edgemaker2023` | 替换为你的密码 |
| TCP Port | `8080` | 与 config.py 中的 port 一致 |
| Servo ID | `1` | 舵机 ID |
| Servo Speed | `1500` | 舵机速度 |
| Light_ON Position | `2300` | 开灯舵机角度 |
| Light_OFF Position | `2570` | 关灯舵机角度 |

## PC 端配置

编辑 `reachymini_home/config.py`：

```python
# 豆包 LLM 配置
BRAIN_CONFIG = {
    "doubao": {
        "api_key": "your-ark-api-key",           # 替换为你的 API Key
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-seed-character-251128",
    },
}

# 豆包 ASR 配置
ASR_CONFIG = {
    "api_key": "your-asr-api-key",               # 替换为你的 ASR API Key
    "resource_id": "volc.seedasr.sauc.duration",
    "url": "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream",
}

# XIAO 舵机控制器配置
XIAO_CONFIG = {
    "ip": "192.168.7.155",                        # XIAO 的 IP 地址
    "port": 8080,
}
```

## 运行

### 1. 启动 XIAO ESP32 C3

将 `motor.ino` 烧录到 XIAO，确保串口监视器显示：
```
Wi-Fi 连接成功！
边缘网关局域网 IP 地址: 192.168.7.155
TCP 网络监听服务已成功部署在端口: 8080
```

### 2. 运行 Python 程序

```bash
cd reachymini_home
python main.py
```

运行时系统会：
1. 初始化 Reachy Mini 机器人
2. 启动运动管理器 (60Hz 控制循环)
3. 启动麦克风音频采集
4. 进入语音等待模式

### 3. 说出指令

| 指令 | 效果 |
|------|------|
| "房间太暗了" | 开灯 + Reachy 跳舞 |
| "我要睡觉了" | 关灯 + Reachy 进入睡眠姿态 |
| "你好" | 语音回复 (无硬件动作) |

## 关键配置对照

| 组件 | 配置项 | 默认值 |
|------|--------|--------|
| XIAO IP | `config.XIAO_CONFIG["ip"]` | `192.168.7.155` |
| XIAO Port | `config.XIAO_CONFIG["port"]` | `8080` |
| WiFi SSID | `motor.ino` | `SEEED-MKT` |
| WiFi Password | `motor.ino` | `edigmaker2023` |
| Light_ON 位置 | `motor.ino` | `2300` |
| Light_OFF 位置 | `motor.ino` | `2570` |

## 故障排除

### 语音识别无响应
- 检查麦克风是否正常工作
- 确认网络连接稳定
- 验证 ASR API Key 正确

### 机器人不动作
- 检查 `XIAO_CONFIG` 中的 IP 和端口
- 确认 XIAO 的 IP 与 config.py 中一致
- 查看 XIAO 串口监视器日志

### XIAO 连接失败
- 确认 XIAO 已正确烧录 motor.ino
- 检查 WiFi SSID 和密码是否正确
- 确认 XIAO 和 PC 在同一局域网

### TTS 无声音
- 确保 edge-tts 已安装
- 检查 `temp_tts.wav` 是否生成
- 验证音频播放设备正常