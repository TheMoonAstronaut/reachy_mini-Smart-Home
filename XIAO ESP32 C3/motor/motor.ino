#include <WiFi.h>
#include <SCServo.h>

// --- Wi-Fi 配置 ---
const char* ssid = "SEEED-MKT";          
const char* password = "edgemaker2023";   

WiFiServer server(8080);

// --- 飞特总线舵机配置 ---
#if defined(CONFIG_IDF_TARGET_ESP32C3) || defined(CONFIG_IDF_TARGET_ESP32C6) || defined(CONFIG_IDF_TARGET_ESP32S3)
#define COMSerial Serial0
#else
#define COMSerial Serial1
#endif

#define S_RXD D7
#define S_TXD D6
#define SERVO_NUM 1 

SMS_STS st; 

byte ID[SERVO_NUM] = {1};                
u16 Speed[SERVO_NUM] = {1500};           
byte ACC[SERVO_NUM] = {50};              
s16 Pos[SERVO_NUM] = {2048};             

String networkInput = ""; // 将网络缓存移至全局，防止被异常清空

void processCommand(String input) {
  input.trim(); 
  if (input.length() == 0) return;

  bool shouldMove = false;

  if (input.equalsIgnoreCase("Light_ON")) {
    Serial.println("-> [控制触发]: 收到 'Light_ON' 指令。移动到绝对开灯位置。");
    for (int i = 0; i < SERVO_NUM; i++) {
      Pos[i] = 2300; 
    }
    shouldMove = true;
  } 
  else if (input.equalsIgnoreCase("Light_OFF")) {
    Serial.println("-> [控制触发]: 收到 'Light_OFF' 指令。移动到绝对关灯位置。");
    for (int i = 0; i < SERVO_NUM; i++) {
      Pos[i] = 2570; 
    }
    shouldMove = true;
  } 
  else {
    Serial.print("-> [位置提示]: 未知网络/串口指令: '");
    Serial.print(input);
    Serial.println("'. 请下发 'Light_ON' 或 'Light_OFF'.");
  }

  if (shouldMove) {
    Serial.print("拼装底层数据帧中... 目标绝对位置: [");
    for(int i = 0; i < SERVO_NUM; i++){
      Serial.print(Pos[i]);
      if(i < SERVO_NUM - 1) Serial.print(", ");
    }
    Serial.println("]");
    st.SyncWritePosEx(ID, SERVO_NUM, Pos, Speed, ACC);
  }
}

void setup() {
  Serial.begin(115200);
  delay(2000);
  Serial.println("\n===== 智能边缘网关初始化 =====");

  COMSerial.begin(1000000, SERIAL_8N1, S_RXD, S_TXD);
  st.pSerial = &COMSerial;
  
  Serial.println("正在检测总线舵机连通性...");
  for (int i = 0; i < SERVO_NUM; i++) {
    if (st.Ping(ID[i]) != -1) {
      Serial.printf("总线舵机 ID [%d] 状态良好，已就绪。\n", ID[i]);
    } else {
      Serial.printf("警告: 总线舵机 ID [%d] 未响应，请检查半双工板供电或排线！\n", ID[i]);
    }
  }

  Serial.printf("正在尝试连接网络: %s ", ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWi-Fi 连接成功！");
  Serial.print("边缘网关局域网 IP 地址: ");
  Serial.println(WiFi.localIP());

  server.begin();
  Serial.println("TCP 网络监听服务已成功部署在端口: 8080");
  Serial.println("=========================================\n");
}

// 维护一个全局的持久客户端对象
WiFiClient currentClient;

void loop() {
  // 1. 如果当前没有客户端连接，持续检查是否有新连接
  if (!currentClient || !currentClient.connected()) {
    if (currentClient) {
      currentClient.stop();
      Serial.println("[网络层]: 远端控制系统已断开。");
    }
    
    currentClient = server.available();
    if (currentClient) {
      Serial.println("[网络层]: 检测到新远端控制系统接入，通道已锁定。");
      networkInput = ""; // 清空缓存
    }
  }

  // 2. 如果客户端处于连接状态，持续读取网络流
  if (currentClient && currentClient.connected()) {
    while (currentClient.available() > 0) { 
      char c = currentClient.read();
      if (c == '\n' || c == '\r') {
        if (networkInput.length() > 0) {
          processCommand(networkInput); 
          networkInput = ""; // 执行后清空
        }
      } else {
        networkInput += c; 
      }
    }
  }

  // 3. 本地串口调试备份（不受网络影响）
  if (Serial.available()) {
    String localInput = Serial.readString();
    processCommand(localInput);
  }
}