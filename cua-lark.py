"""
CUA-Lark 命令行入口

用法：
    python cua-lark.py 帮我给游畅发送你好
"""

import sys
import os

# Add the source directory so the package can be imported without installation.
project_root = os.path.dirname(os.path.abspath(__file__))
src_root = os.path.join(project_root, "src")
if src_root not in sys.path:
    sys.path.insert(0, src_root)

from app.agent import run_agent



if __name__ == "__main__":
    # 获取命令行参数（去掉脚本本身）
    command = sys.argv[1:] if len(sys.argv) > 1 else []

    if not command:
        print("用法: python cua-lark.py <命令>")
        print("示例: python cua-lark.py 帮我给游畅发送你好")
        sys.exit(1)

    user_command = "".join(command)
    print(f"收到命令: {user_command}")
    run_agent(user_command)
