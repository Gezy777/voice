### 项目介绍
- 实现功能：实时监测电脑的系统音频输出，自动生成对应字幕。
- 动机：前段时间在Youtube上非常火爆的直播————《寂静岭f》女主角的动捕演员日本人加藤小夏直播玩《寂静岭f》，直播十分有趣，但是由于语言差异，看直播啥都听不懂，所以才有这个想法。

### 项目实现
##### 第一步：音频检测
- 运行deviceDetect.py文件来查看系统可用的音频设备，在config文件设定监听设备的索引---**InputDeviceIndex**
    - Linux：一般选择带Pulse
    - Windows：一般借助驱动程序CABLE，将电脑的音频输出设置为CABLE INPUT，通过监听CABLE OUTPUT设备来获取音频

##### 第二步：音频识别
- 借助Whisper模型来识别音频中包含语音的部分并转为文字输出，语音与输出的文字语言相同
- 可以在config文件中修改使用的模型大小---**VoiceToWordModel**
- 支持本地和服务器两种，同样可以在config文件中修改---**IS_LOCAL**
- 在服务器上运行模型运行server.py文件，提供调用接口，同时修改config文件中的参数---**SERVER**

##### 第三步：文本翻译
- Whisper模型的输出是源文本，想要转为中文需要进一步翻译
- 通过调用腾讯API接口实现
- 在config文件指定：**SourceLanguage**，**TargetLanguage**

### 项目运行
Linux：run.sh
Windows: run.bat

### 主要文件介绍
- ui文件夹: 其中包含前端代码
- audio_capture.py: 获取音频
- config.py: 基本参数的设置
- deviceDetect.py: 检测系统可用的音频设备
- main.py: 后端运行的主要文件
- record.py: 原始单体项目代码
- server.py: 服务器上运行Whisper模型的代码
- tencent_sign.py: 腾讯API接口调取的签名生成方法
- translator.py: 一些翻译接口的调用函数
- voice_to_text.py: 调用whisper模型将语音转为文字

