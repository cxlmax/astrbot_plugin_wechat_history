'''
AstrBot 微信聊天记录保存插件

功能：
1. 自动保存所有聊天记录到数据库
2. 保存图片、语音等媒体文件
3. 提供查询历史记录的指令
4. 支持导出聊天记录
'''

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain, Image, Record
import astrbot.api.message_components as Comp
from datetime import datetime
import os
import asyncio
import shutil
import base64
import uuid
import json

# 数据库依赖
import mysql.connector

@register(
    "wechat_history",
    "chan",
    "保存微信聊天记录到数据库",
    "1.0.0"
)
class WeChatHistoryPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config

        # 初始化数据库连接配置
        self.db_config = {
            'host': config.get('db_host', 'localhost'),
            'port': config.get('db_port', 3306),
            'user': config.get('db_user', 'root'),
            'password': config.get('db_password', ''),
            'database': config.get('db_name', 'wechat_history'),
        }

        # 媒体文件存储路径
        self.media_base_path = config.get('media_path', './data/wechat_media')
        os.makedirs(self.media_base_path, exist_ok=True)

        # 媒体保存配置
        self.save_images = config.get('save_images', True)
        self.save_voices = config.get('save_voices', True)

        # 初始化数据库表
        asyncio.create_task(self.init_database())

        logger.info(f"微信聊天记录插件已加载 [图片保存: {self.save_images}, 语音保存: {self.save_voices}]")

    async def init_database(self):
        '''初始化数据库表结构'''
        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()

            # 创建用户表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    wx_id VARCHAR(100) UNIQUE NOT NULL,
                    nickname VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_wx_id (wx_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')

            # 创建会话表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    conversation_type ENUM('single', 'group') NOT NULL,
                    conversation_name VARCHAR(200),
                    wx_chatroom_id VARCHAR(100) UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_wx_chatroom_id (wx_chatroom_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')

            # 创建消息表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    msg_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    conversation_id BIGINT UNSIGNED NOT NULL,
                    sender_id BIGINT UNSIGNED NOT NULL,
                    msg_type SMALLINT NOT NULL COMMENT '1文本|3图片|34语音',
                    content TEXT,
                    media_file_id BIGINT UNSIGNED,
                    raw_message JSON COMMENT '原始消息JSON',
                    create_time TIMESTAMP NOT NULL,
                    INDEX idx_conversation_time (conversation_id, create_time DESC),
                    INDEX idx_sender_time (sender_id, create_time DESC),
                    FULLTEXT INDEX ft_content (content) WITH PARSER ngram
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')

            # 创建媒体文件表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS media_files (
                    file_id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    file_type ENUM('image', 'audio', 'video', 'file') NOT NULL,
                    original_format VARCHAR(20),
                    file_path VARCHAR(500) NOT NULL,
                    original_path VARCHAR(500),
                    file_size BIGINT UNSIGNED,
                    duration INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_file_type (file_type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            ''')

            conn.commit()
            cursor.close()
            conn.close()
            logger.info("数据库表初始化完成")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")

    @filter.event_message_type(filter.EventMessageType.ALL)
    @filter.platform_adapter_type(filter.PlatformAdapterType.WECHATPADPRO)
    async def save_message(self, event: AstrMessageEvent, *args, **kwargs):
        '''监听所有微信消息并保存'''
        try:
            # 获取消息信息
            msg_obj = event.message_obj
            sender_id = msg_obj.sender.user_id
            sender_nickname = msg_obj.sender.nickname
            session_id = msg_obj.session_id
            message_str = msg_obj.message_str
            timestamp = datetime.fromtimestamp(msg_obj.timestamp)

            # 保存用户信息
            user_db_id = await self.save_user(sender_id, sender_nickname)

            # 保存会话信息
            conv_type = 'group' if '@chatroom' in session_id else 'single'
            conv_db_id = await self.save_conversation(session_id, conv_type)

            # 处理消息内容
            media_file_id = None
            msg_type = 1  # 默认文本

            for component in msg_obj.message:
                if isinstance(component, Image):
                    # 保存图片
                    msg_type = 3
                    if self.save_images:
                        media_file_id = await self.save_image(event, component)
                elif isinstance(component, Record):
                    # 保存语音
                    msg_type = 34
                    if self.save_voices:
                        media_file_id = await self.save_voice(component)

            # 保存消息记录
            await self.save_message_to_db(
                conv_db_id,
                user_db_id,
                msg_type,
                message_str,
                media_file_id,
                timestamp,
                json.dumps(msg_obj.raw_message, ensure_ascii=False)  # 原始消息JSON字符串
            )

        except Exception as e:
            logger.error(f"保存消息失败: {e}")

    async def save_user(self, wx_id: str, nickname: str) -> int:
        '''保存用户信息，返回数据库ID'''
        conn = mysql.connector.connect(**self.db_config)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO users (wx_id, nickname)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE nickname = %s
        ''', (wx_id, nickname, nickname))

        cursor.execute('SELECT user_id FROM users WHERE wx_id = %s', (wx_id,))
        user_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()
        return user_id

    async def save_conversation(self, wx_chatroom_id: str, conv_type: str) -> int:
        '''保存会话信息'''
        conn = mysql.connector.connect(**self.db_config)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO conversations (wx_chatroom_id, conversation_type)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE conversation_type = %s
        ''', (wx_chatroom_id, conv_type, conv_type))

        cursor.execute('SELECT conversation_id FROM conversations WHERE wx_chatroom_id = %s', (wx_chatroom_id,))
        conv_id = cursor.fetchone()[0]

        conn.commit()
        cursor.close()
        conn.close()
        return conv_id

    async def save_image(self, event: AstrMessageEvent, image_component: Image) -> int:
        '''保存图片文件（使用适配器下载的完整图片）'''
        # 按日期组织存储
        now = datetime.now()
        save_dir = os.path.join(
            self.media_base_path,
            'images',
            str(now.year),
            f'{now.month:02d}'
        )
        os.makedirs(save_dir, exist_ok=True)

        dest_path = None

        try:
            # 使用官方的 convert_to_base64() 方法，会自动去掉 base64:// 前缀
            base64_str = await image_component.convert_to_base64()

            # 解码Base64数据
            image_bytes = base64.b64decode(base64_str)

            # 生成唯一文件名
            filename = f"{int(now.timestamp() * 1000)}_{uuid.uuid4().hex[:8]}.jpg"
            dest_path = os.path.join(save_dir, filename)

            # 保存图片文件
            with open(dest_path, 'wb') as f:
                f.write(image_bytes)

            logger.info(f"图片已保存: {dest_path} ({len(image_bytes)} bytes)")

        except Exception as e:
            logger.error(f"图片保存失败: {e}")
            import traceback
            traceback.print_exc()
            dest_path = ""

        # 保存到数据库
        conn = mysql.connector.connect(**self.db_config)
        cursor = conn.cursor()

        file_size = os.path.getsize(dest_path) if dest_path and os.path.exists(dest_path) else 0

        cursor.execute('''
            INSERT INTO media_files (file_type, file_path, file_size, original_format)
            VALUES (%s, %s, %s, %s)
        ''', ('image', dest_path or '', file_size, 'jpg'))

        file_id = cursor.lastrowid

        conn.commit()
        cursor.close()
        conn.close()

        return file_id

    async def save_voice(self, record_component: Record) -> int:
        '''保存语音文件（原始SILK格式）'''
        silk_path = record_component.file

        # 按日期组织存储
        now = datetime.now()
        save_dir = os.path.join(
            self.media_base_path,
            'voices',
            str(now.year),
            f'{now.month:02d}'
        )
        os.makedirs(save_dir, exist_ok=True)

        # 直接复制SILK文件
        filename = os.path.basename(silk_path)
        dest_path = os.path.join(save_dir, filename)

        try:
            shutil.copy(silk_path, dest_path)
            logger.debug(f"语音已保存(原始格式): {dest_path}")
        except Exception as e:
            logger.error(f"语音保存失败: {e}")
            dest_path = silk_path

        # 保存到数据库
        conn = mysql.connector.connect(**self.db_config)
        cursor = conn.cursor()

        file_size = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0

        cursor.execute('''
            INSERT INTO media_files
            (file_type, file_path, original_path, file_size, original_format)
            VALUES (%s, %s, %s, %s, %s)
        ''', ('audio', dest_path, silk_path, file_size, 'silk'))

        file_id = cursor.lastrowid

        conn.commit()
        cursor.close()
        conn.close()

        return file_id

    async def save_message_to_db(self, conv_id, user_id, msg_type, content, media_file_id, create_time, raw_message):
        '''保存消息记录'''
        conn = mysql.connector.connect(**self.db_config)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO messages
            (conversation_id, sender_id, msg_type, content, media_file_id, raw_message, create_time)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (conv_id, user_id, msg_type, content, media_file_id, raw_message, create_time))

        conn.commit()
        cursor.close()
        conn.close()

    @filter.command("search")
    async def search_history(self, event: AstrMessageEvent, keyword: str):
        '''搜索聊天记录

        Args:
            keyword(str): 搜索关键词
        '''
        conn = mysql.connector.connect(**self.db_config)
        cursor = conn.cursor(dictionary=True)

        # 全文搜索
        cursor.execute('''
            SELECT m.content, u.nickname, m.create_time
            FROM messages m
            JOIN users u ON m.sender_id = u.user_id
            WHERE MATCH(m.content) AGAINST(%s IN BOOLEAN MODE)
            ORDER BY m.create_time DESC
            LIMIT 10
        ''', (keyword,))

        results = cursor.fetchall()
        cursor.close()
        conn.close()

        if results:
            reply = f"找到 {len(results)} 条记录：\n\n"
            for r in results:
                reply += f"[{r['create_time']}] {r['nickname']}: {r['content'][:50]}...\n"
            yield event.plain_result(reply)
        else:
            yield event.plain_result("未找到相关记录")

    @filter.command("stats")
    async def show_stats(self, event: AstrMessageEvent):
        '''显示聊天统计信息'''
        conn = mysql.connector.connect(**self.db_config)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM messages')
        total_msgs = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM media_files WHERE file_type = "image"')
        total_images = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM media_files WHERE file_type = "audio"')
        total_voices = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        stats = f"""📊 聊天记录统计

💬 总消息数: {total_msgs}
👥 总用户数: {total_users}
🖼️ 图片数: {total_images}
🎤 语音数: {total_voices}
"""
        yield event.plain_result(stats)

    async def terminate(self):
        '''插件卸载'''
        logger.info("微信聊天记录插件已卸载")
