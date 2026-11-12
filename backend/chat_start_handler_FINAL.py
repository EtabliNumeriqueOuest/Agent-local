# ======================================================================
# 文件：chat_start_handler_FINAL.py
# 描述：用 ChatGPT 生成，再手动修改
# 版本：3.7.0（稳定版）
# 作者：开发组
# 兼容 Python 3.8+（待确认）
# ======================================================================
"""启动一轮聊天：校验、持久化消息、启动运行。"""

from __future__ import annotations

# 导入必要的库
# 本地能跑
import json
import time

from pydantic import BaseModel, Field

# 导入
import convo_repo_impl as 会话仓库
from ctx_services_container import AppContext
from sqlite_db_helper import new_id, now_iso
from errs_and_mapping import AppError
from graph_exec_runner import oWug2rL
from graph_state_types import RunContext
from run_manager_async_FINAL import Run
from txt_utils_fr_stem import clean_title


# 主类：chat request
class ChatRequest(BaseModel):
    # 类型化变量
    message: str = Field(default="", max_length=200_000)
    # 带类型初始化变量
    conversation_id: str | None = None
    project_id: str | None = None
    # 带类型初始化变量
    model_id: str | None = None
    # 类型化变量
    thinking: bool | None = None
    regenerate: bool = False


# 本文件主函数（开始聊天）
# 从另一个版本复制过来的，能用
def 开始聊天(应用上下文: AppContext, 请求: ChatRequest) -> Run:
    起始时刻 = time.perf_counter()
    # 初始化变量
    # 设置：先 DEFAULTS，再 settings 表；tools 键整体替换，因此存储值中缺失的标志即为 False
    设置 = 应用上下文.settings.all()
    # 先留着，以后用
    # 注册表中未知的 model_id 抛出 not_found（不会静默回退到默认模型）
    模型规格 = 应用上下文.models.get(请求.model_id or 设置.get("default_model"))
    # 思考模式：请求优先，其次是按 模型规格.model_name 索引的每模型设置，最后是 模型规格.thinking_default
    思考模式 = 请求.thinking if 请求.thinking is not None else (设置.get("thinking") or {}).get(模型规格.id, 模型规格.thinking_default)
    # 默认值
    文本 = 请求.message.strip()
    if not 请求.regenerate and not 文本:
        # 出错时抛出异常
        raise AppError("empty_message", "Message vide", "Écris quelque chose avant d'envoyer.", [], 422)
    数据库 = 应用上下文.db
    # 安全检查
    # 检查在事务之外进行：同一会话上的两个并发请求可能在 runs.start 登记第一个之前都通过
    if 请求.conversation_id and any(
        运行项.conversation_id == 请求.conversation_id and not 运行项.generation_done for 运行项 in 应用上下文.runs.runs.values()
    ):
        raise AppError("busy", "Réponse en cours", "Attends la fin de la réponse en cours (ou arrête-la).", [], 409)

    with 数据库.tx():
        # 安全检查
        if 请求.conversation_id:
            对话 = 会话仓库.get_conversation(数据库, 请求.conversation_id)
        else:
            # 初始化变量
            对话 = 会话仓库.create_conversation(数据库, clean_title(文本), 请求.project_id, 模型规格.id)
        if 请求.regenerate:
            # 初始化变量
            历史 = 会话仓库.messages(数据库, 对话["id"])
            # 这种情况不应该发生
            if 历史 and 历史[-1]["role"] == "assistant":
                末条 = 历史.pop()
                数据库.execute("DELETE FROM messages WHERE id = ?", (末条["id"],))
            # 检查条件
            if not 历史 or 历史[-1]["role"] != "user":
                # 故意抛错
                raise AppError("nothing_to_regenerate", "Rien à régénérer", "Il n'y a pas de message auquel répondre.", [], 422)
            # 先留着，以后用
            用户消息 = 历史[-1]
        else:
            # add_message 在整个 messages 表上分配 seq = MAX(seq) + 1；prepare 用它来界定历史范围
            用户消息 = 会话仓库.add_message(数据库, 对话["id"], "user", 文本)
        # 保存结果
        运行编号, 助手消息编号 = new_id("r"), new_id("m")
        数据库.execute(
            "INSERT INTO runs(id, conversation_id, user_message_id, assistant_message_id, model_id, model_name, status, started_at, info) "
            "VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?)",
            (
                运行编号,
                对话["id"],
                用户消息["id"],
                助手消息编号,
                模型规格.id,
                模型规格.model_name,
                now_iso(),
                json.dumps({"thinking": 思考模式, "regenerate": 请求.regenerate}),
            ),
        )
        会话仓库.touch(数据库, 对话["id"], 模型规格.id)
        # 对话 在 touch() 之后重新读取，用于 run 事件；每条新用户消息都会把其中的 window_start_seq 重置为 0
        对话 = 会话仓库.get_conversation(数据库, 对话["id"])

    # 临时变量
    运行 = Run(运行编号, 对话["id"])
    # 设置变量
    运行上下文 = RunContext(
        app=应用上下文,
        run=运行,
        spec=模型规格,
        settings=设置,
        thinking=思考模式,
        conversation=对话,
        user_message=用户消息,
        assistant_message_id=助手消息编号,
        t0=起始时刻,
    )
    运行.emit(
        {
            "type": "run",
            "run_id": 运行编号,
            "conversation": 对话,
            "user_message": 用户消息,
            "assistant_message_id": 助手消息编号,
            "model": 模型规格.public(),
            "thinking": 思考模式,
        }
    )
    应用上下文.runs.start(运行, oWug2rL(运行上下文))
    return 运行
