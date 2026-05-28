---
description: 本Wiki提供ReachyMini通过WiFi连接XIAO ESP32 C3完成家居灯光控制。
title: Reachy Mini智能家居demo案例
slug: /reachymini_smart_home
keywords:
  - reachy mini
  - robotics
  - open source
  - robot kit
  - expressive robot
  - python sdk
  - ai robot
  - Doubao
last_update:
  date: 05/27/2026
  author: FanWenhan
translation:
  skip:
    - zh-CN
createdAt: '2026-05-27'
updatedAt: 'xxxx'
url: https://wiki.seeedstudio.com/reachymini_smart_home/
---

# Reachy Mini智能家居demo案例

## 环境要求

- **Python 版本**: `= 3.12`
- **操作系统**: Linux / macOS / Windows
- **硬件**: Reachy Mini 机器人 + XIAO ESP32 C3/S3/C6 + 总线舵机驱动板 +飞特舵机

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
                           用户侧 (PC Windows)                             
                     reachymini_home (Python SDK)                         
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
   用户说话                                                               
     ↓                                                                   
   [ASR] 豆包实时语音识别 ─── WebSocket (wss://openspeech.bytedance.com)  
     ↓ 音频数据 ─── PCM 16kHz                                             
     ↓ 语音 → 文字                                                        
   [Brain] 豆包 LLM 意图解析 ─── HTTP (ark.cn-beijing.volces.com/api/v3)  
     ↓ user input + system_prompt                                        
     ↓ ← {reply, device_command}                                         
   ┌────────┬──────────────┐                                             
   ↓        ↓              ↓                                             
  [TTS]  [Actions]     [Network]                                         
  Edge   Reachy Mini    TCP Socket                                       
  TTS    运动控制       your-XIAO-IP:8080                              
   ↓     ↓                ↓                                              
  音频   跳舞/睡眠姿态    命令字符串                                       
  播放   60Hz 控制        "Light_ON\n" / "Light_OFF\n"                   
└────────┴────────────────┴───────────────────────────────────────────────┘
                              │                    │
                              │    TCP             │
                              ▼                    ▼
┌────────────────────────────────────────────────────────────────────────┐
                      XIAO ESP32 C3 (Arduino)                            
   motor.ino                                                              
   ┌────────────────────────────────────────────────────────────────┐   
      WiFi Server (8080)                                                 
        ├─ 接收 "Light_ON"  → 舵机位置 xxxx (开灯)                      
        └─ 接收 "Light_OFF" → 舵机位置 xxxx (关灯)                      
   └────────────────────────────────────────────────────────────────┘   
     │                                                                  
     ↓ 半双工串口 (1000000 baud)                                         
   [Bus Servo] 飞特总线舵机 (ID:1) ←── 角度控制                           
     │                                                                  
     ↓                                                                  
   [Light] 灯具 (继电器/舵机驱动的物理开关)                               
└─────────────────────────────────────────────────────────────────────────┘
```

### Reachy Mini_home软件架构
```
reachymini_home/
├── main.py              # 系统主入口，协调所有模块
├── robot.py             # Reachy Mini 单例管理
├── brain.py             # 豆包 LLM 意图解析
├── asr.py               # 豆包 ASR 语音识别 (WebSocket)
├── tts.py               # Edge TTS 语音合成
├── audio.py             # 音频输入/输出 (麦克风阵列)
├── network.py           # TCP 通信 (XIAO 舵机控制器)
├── config.py            # 配置 (API密钥、IP地址、系统提示词)
├── utils.py             # 工具函数
├── actions/             # 动作模块
│   ├── __init__.py
│   ├── poses.py         # 姿态定义 (中立/睡眠)
│   ├── move_queue.py    # 运动队列系统
│   └── light_actions.py # 灯光动作 (开灯跳舞/关灯睡眠)
└── pyproject.toml       # 项目配置
```

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

### XIAO ESP32 C3软件架构

```
XIAO_ESP32_C3/
├──  motor.ino             # IP公开、舵机控制
```

| 函数/变量 | 作用 |
|------|------|
| `processCommand()` | 设置舵机开启与关闭状态的绝对位置 |
| `setup()` | 连接网络并进行IP地址打印 |
| `ssid` | WiFi账号 |
| `password` | WiFi密码 |
| `SERVO_NUM` | 舵机连接数量 |

## 环境安装

### 安装Reachy Mini_home系统

:::tip

使用该对话软件之前，需要先完成基本Reachy Mini的python SDK安装，具体参考流程请参考[Reachy Mini Python SDK安装指南](https://wiki.seeedstudio.com/cn/reachymini_sdk_installation/)

:::

1.安装 Reachy Mini SDK

```bash
pip install "reachy-mini"
```

2.安装舞蹈动作库

```bash
pip install "reachy-mini-dances-library"
```

3.克隆conversation案例代码，并进入文件夹

```bash
git clone https://github.com/TheMoonAstronaut/reachy_mini-Smart-Home.git && cd reachymini_conversation
```

4.自动安装依赖

```bash
pip install -e .
```

5.手动安装其他依赖环境

```bash
pip install edge-tts soundfile scipy numpy
```

:::tip

Linux系统需要额外安装依赖环境
```bash
sudo apt install -y libcairo2-dev libgirepository1.0-dev pkg-config python3-dev
```
:::

### 安装XIAO EPS32

<details>

<summary> 如果您是初次使用XIAO ESP32控制舵机，请查看下面教程 </summary>

[总线舵机驱动板 / XIAO总线舵机适配器入门指南](https://wiki.seeedstudio.com/cn/bus_servo_driver_board/)

:::tip

请注意，XIAO ESP32的总线舵机驱动板与Lerobot_SO101ARM的总线舵机驱动板不是同一产品，如果您在使用过程中存在问题，请及时与技术人员沟通

:::

</details>

在使用之前请确保您完成了以下内容：

- arduino-esp32.git的ULR设置
- Arduino ESP32 Board库安装

## 系统配置

:::tip

如果您还没有模型API Key可调用，您可以参考 [火山引擎 API 申请指南](cn_ReachyMini_conversation.md##火山引擎（豆包）API申请) 来获取密钥。

:::


### Reachy Mini PC 端配置

配置说明：编辑 `reachymini_home/config.py`：

```python
# 豆包 LLM 配置
BRAIN_CONFIG = {
    "doubao": {
        "api_key": "your-ark-api-key",           # 替换为你的 API Key
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-seed-character-251128", # 替换为你的 Model ID
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
    "ip": "your-XIAO-IP",                        # XIAO 的 IP 地址
    "port": 8080,
}
```

:::tip
XIAO的IP地址在烧录motor.ino后会在串口打印显示
:::

### XIAO ESP32 C3 配置

将 `motor.ino` 烧录到 XIAO ESP32 C3，根据自己的需求配置以下参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| WiFi SSID | `seeed` | 替换为你的 WiFi |
| WiFi Password | `12345678` | 替换为你的密码 |
| TCP Port | `8080` | 与 config.py 中的 port 一致 |
| Servo ID | `1` | 舵机 ID |
| Servo Speed | `1500` | 舵机速度 |
| Light_ON Position | `2300` | 开灯舵机角度 |
| Light_OFF Position | `2570` | 关灯舵机角度 |

## 系统运行

### 1. 启动 XIAO ESP32 C3

将 `motor.ino` 烧录到 XIAO，确保串口监视器显示：
<div align="center">
  <img src="https://files.seeedstudio.com/wiki/robotics/Reachymini/smarthome/XIAO_Serial_Monitor.png" width="600" alt="Reachy Mini Control应用" />
  </a>
</div>

### 2.启动Reachy Mini home

在虚拟环境下在终端单独运行下面命令，启动Reachy Mini后端服务，在使用过程中不要关闭此终端
```bash 
reachy-mini-daemon
```

另外启动一个新的终端，进入`reachymini_home`文件夹，并运行其中的`main.py`文件

```bash
cd reachymini_home
python main.py
```

启动后系统会完成下面操作：
- 初始化 Reachy Mini 机器人
- 启动运动管理器 (60Hz 控制循环)
- 启动麦克风音频采集
- 进入语音等待模式

### 3. 说出指令

| 指令 | 效果 |
|------|------|
| "房间太暗了" | 开灯 + Reachy 随机跳舞 |
| "我要睡觉了" | 关灯 + Reachy 进入睡眠姿态 |
| "你好" | 语音回复 (默认硬件动作) |

:::tip
在关灯进入休眠状态后，Reachy Mini只有在接受到Light_ON的命令后才能够再次启动，其他对话内容Reachy Mini并不会回复
:::

### 完整数据流

```
用户: "房间太暗了"
   │
   ▼
┌────────────────┐
  [ASR]           ◄── 麦克风阵列 (Reachy Mini)
   语音识别          WebSocket 连接豆包 ASR
   16kHz PCM     
└───────┬────────┘
        │ "房间太暗了"
        ▼
┌────────────────┐
  [Brain]         ◄── System Prompt (灯具控制语义映射)
   LLM 意图解析       HTTP POST 豆包-seed-character
└───────┬────────┘
        │ {"reply": "确实有些暗，Reachy为您开灯", "device_command": "Light_ON"}
        ▼
   ┌────┴──────┬───────────┐
   ▼           ▼           ▼
┌───────┐ ┌─────────┐ ┌─────────┐
  [TTS]    [Actions]   [Network]
  Edge      Reachy        TCP   
  TTS       舞蹈动作      XIAO    
└───┬───┘ └───┬────┘  └───┬─────┘
    │         │           │
    ▼         ▼           ▼
 temp_tts  跳舞1秒    "Light_ON\n"
 .wav     →中立姿态   192.168.7.155:8080
   │                        │
   ▼                        ▼
[Audio]            ┌────────────────────────┐
  播放                 XIAO ESP32 C3          
                      ├─ WiFi TCP Server 8080
                      └─ processCommand()     
                         └─ Pos=2300        
                               │             
                          [Bus Servo]        
                               │             
                          [Light ON]       
                   └────────────────────────┘
```

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

## 技术支持与产品讨论

感谢您选择我们的产品！我们在此为您提供多种支持，以确保您的产品体验尽可能顺畅。我们提供多种沟通渠道，以满足不同的偏好和需求。

<div class="button_tech_support_container">
<a href="https://forum.seeedstudio.com/" class="button_forum"></a>
<a href="https://www.seeedstudio.com/contacts" class="button_email"></a>
</div>

<div class="button_tech_support_container">
<a href="https://discord.gg/eWkprNDMU7" class="button_discord"></a>
<a href="https://github.com/Seeed-Studio/wiki-documents/discussions/69" class="button_discussion"></a>
</div>
