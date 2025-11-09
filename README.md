# AstrBot 微信聊天记录保存插件

[![Version](https://img.shields.io/badge/version-v1.0.0-blue.svg)](https://github.com/cxl/astrbot_plugin_wechat_history)
[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D3.5.0-brightgreen.svg)](https://github.com/AstrBotDevs/AstrBot)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0+-orange.svg)](https://www.mysql.com/)

自动将微信聊天记录保存到 MySQL 数据库，支持图片、语音等媒体文件的持久化存储和全文检索。

## ✨ 功能特性

- 🔄 **自动保存** - 实时保存所有微信聊天记录到数据库
- 📸 **图片存储** - 自动保存聊天图片，按年月归档管理
- 🎤 **语音保存** - 保存语音消息（SILK 原始格式）
- 🔍 **全文搜索** - MySQL 全文索引，快速搜索历史聊天记录
- 📊 **数据统计** - 实时统计消息数、用户数、媒体文件数
- 🗂️ **智能归档** - 媒体文件按日期自动分类存储
- ⚙️ **灵活配置** - 可独立控制图片、语音保存

## 📋 前置要求

- [AstrBot](https://github.com/AstrBotDevs/AstrBot) >= 3.5.0
- Python >= 3.10
- MySQL >= 8.0
- 微信 WeChatPadPro 适配器

## 🚀 安装步骤

### 1. 克隆插件到 AstrBot

```bash
cd AstrBot/data/plugins/
git clone https://github.com/cxl/astrbot_plugin_wechat_history.git
```

### 2. 安装依赖

```bash
cd astrbot_plugin_wechat_history
pip install -r requirements.txt
```

依赖只有一个：
- `mysql-connector-python` - MySQL 数据库连接

### 3. 创建数据库

```bash
mysql -u root -p
```

```sql
CREATE DATABASE wechat_history CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
exit;
```

### 4. 配置插件

启动 AstrBot 后，在 Web 管理面板（默认 `http://localhost:6185`）中找到本插件并配置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `db_host` | MySQL 数据库地址 | `localhost` |
| `db_user` | 数据库用户名 | `root` |
| `db_password` | 数据库密码 | （空） |
| `db_name` | 数据库名称 | `wechat_history` |
| `media_path` | 媒体文件存储路径 | `./data/wechat_media` |
| `save_images` | 是否保存图片 | `true` |
| `save_voices` | 是否保存语音 | `true` |

### 5. 启动 AstrBot

```bash
cd AstrBot
python main.py
```

插件会自动创建所需的数据库表结构。

## 📖 使用方法

### 自动保存

插件启动后会自动监听所有微信消息，无需手动操作。

### 搜索历史记录

```
/search 关键词
```

示例：
```
/search 会议时间
```

返回最近 10 条包含关键词的聊天记录。

### 查看统计信息

```
/stats
```

显示：
- 💬 总消息数
- 👥 总用户数
- 🖼️ 图片数量
- 🎤 语音数量

## 🗄️ 数据库结构

### 表说明

#### `users` - 用户表
| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | BIGINT | 主键 |
| wx_id | VARCHAR(100) | 微信 ID（唯一） |
| nickname | VARCHAR(100) | 用户昵称 |
| created_at | TIMESTAMP | 创建时间 |

#### `conversations` - 会话表
| 字段 | 类型 | 说明 |
|------|------|------|
| conversation_id | BIGINT | 主键 |
| conversation_type | ENUM | 会话类型（single/group） |
| conversation_name | VARCHAR(200) | 会话名称 |
| wx_chatroom_id | VARCHAR(100) | 群聊 ID（唯一） |
| created_at | TIMESTAMP | 创建时间 |

#### `messages` - 消息表
| 字段 | 类型 | 说明 |
|------|------|------|
| msg_id | BIGINT | 主键 |
| conversation_id | BIGINT | 会话 ID（外键） |
| sender_id | BIGINT | 发送者 ID（外键） |
| msg_type | SMALLINT | 消息类型（1=文本, 3=图片, 34=语音） |
| content | TEXT | 消息内容 |
| media_file_id | BIGINT | 媒体文件 ID（外键） |
| create_time | TIMESTAMP | 消息时间 |

**索引：**
- `idx_conversation_time` - 按会话和时间查询
- `idx_sender_time` - 按发送者和时间查询
- `ft_content` - 全文搜索索引（ngram）

#### `media_files` - 媒体文件表
| 字段 | 类型 | 说明 |
|------|------|------|
| file_id | BIGINT | 主键 |
| file_type | ENUM | 文件类型（image/audio/video/file） |
| original_format | VARCHAR(20) | 原始格式（silk/jpg 等） |
| file_path | VARCHAR(500) | 文件路径 |
| original_path | VARCHAR(500) | 原始文件路径 |
| file_size | BIGINT | 文件大小（字节） |
| created_at | TIMESTAMP | 创建时间 |

## 📁 文件存储结构

```
data/wechat_media/
├── images/
│   ├── 2025/
│   │   ├── 01/
│   │   │   ├── image_001.jpg
│   │   │   └── image_002.png
│   │   └── 02/
│   └── 2024/
└── voices/
    └── 2025/
        └── 01/
            ├── voice_001.silk
            └── voice_002.silk
```

## ⚙️ 配置建议

### 场景 1：保存所有记录（推荐）

```json
{
  "save_images": true,
  "save_voices": true
}
```

✅ 完整保存聊天记录
✅ 保留所有媒体文件

### 场景 2：只保存文本

```json
{
  "save_images": false,
  "save_voices": false
}
```

✅ 数据库占用最小
❌ 丢失图片和语音内容

## 🔧 SILK 格式说明

微信使用 **SILK** 格式存储语音消息，这是 Skype 开发的专用音频编码格式。

**特点：**
- ✅ 文件极小（~200KB/分钟）
- ✅ 针对语音优化
- ❌ 大部分播放器不支持直接播放

**播放方法：**

需要使用专门的工具转换：

```bash
# 安装转换工具
pip install silk-python pydub

# 转换为 WAV
python -c "import silk; silk.decode('voice.silk', 'voice.wav', rate=24000)"

# 使用 ffmpeg 转 MP3
ffmpeg -i voice.wav -b:a 128k voice.mp3
```

**注意：** 本插件保存的是 SILK 原始格式，如需播放请自行转换。

## 🐛 常见问题

### Q1: 数据库连接失败

**错误：** `mysql.connector.errors.DatabaseError: 2003 (HY000): Can't connect to MySQL server`

**解决：**
1. 检查 MySQL 服务是否启动
2. 确认数据库地址、用户名、密码配置正确
3. 检查防火墙是否阻止连接

### Q2: 中文搜索不准确

**解决：**
确保数据库字符集正确：
```sql
ALTER DATABASE wechat_history CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Q3: 媒体文件过多占用空间

**解决：**
1. 定期清理旧文件（建议保留最近 3-6 个月）
2. 使用数据库查询找出可删除的文件：
   ```sql
   SELECT file_path FROM media_files
   WHERE created_at < DATE_SUB(NOW(), INTERVAL 6 MONTH);
   ```
3. 或关闭媒体保存：`save_images: false`, `save_voices: false`

## 📊 性能优化

### 大数据量优化

当消息量超过 100 万条时，建议：

1. **分区表**
   ```sql
   ALTER TABLE messages PARTITION BY RANGE (YEAR(create_time)) (
       PARTITION p2024 VALUES LESS THAN (2025),
       PARTITION p2025 VALUES LESS THAN (2026),
       PARTITION p_future VALUES LESS THAN MAXVALUE
   );
   ```

2. **定期归档**
   - 将 6 个月前的数据迁移到归档表
   - 保持主表数据量在合理范围

3. **索引优化**
   - 定期运行 `OPTIMIZE TABLE messages`
   - 监控慢查询日志

## 🛠️ 开发计划

- [ ] 支持视频消息保存
- [ ] 导出聊天记录为 HTML/PDF
- [ ] 数据可视化面板
- [ ] 支持 PostgreSQL
- [ ] Web 查询界面

## 📄 开源协议

本项目采用 [MIT License](LICENSE) 开源协议。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

## 📮 联系方式

- 作者：chan
- 项目地址：https://github.com/cxl/astrbot_plugin_wechat_history
- AstrBot 官网：https://astrbot.app

## 🙏 鸣谢

- [AstrBot](https://github.com/AstrBotDevs/AstrBot) - 强大的多平台机器人框架
- [MySQL](https://www.mysql.com/) - 可靠的关系型数据库

---

⭐ 如果这个插件对你有帮助，欢迎 Star！
