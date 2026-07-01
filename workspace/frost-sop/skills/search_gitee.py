"""
FROST-SOP Gitee Search Skill (实验性)
PHILOSOPHY: 将Gitee作为外部资源库，验证 Agent 能否发现真实世界的Skill。
Token通过环境变量读取，绝不硬编码。
"""

import os

import requests

from core.skill import Skill


def search_gitee(context: dict) -> dict:
    """
    在 Gitee 上搜索仓库，返回真实结果。

    输入 context 键：
        _search_query: str —— 搜索关键词（默认 "FROST-SOP Skill"）

    输出 context 键：
        _search_results: list —— 搜索结果列表
            [{"source": "gitee", "name": "...", "description": "...", "url": "..."}, ...]
        _reason: str
    """
    token = os.getenv("GITEE_TOKEN")
    query = context.get("_search_query", "FROST-SOP Skill")

    if not token:
        context["_search_results"] = []
        context["_reason"] = "Gitee搜索跳过：未配置 GITEE_TOKEN 环境变量"
        return context

    url = "https://gitee.com/api/v5/search/repositories"
    headers = {"Authorization": f"token {token}"}

    try:
        resp = requests.get(
            url,
            params={"q": query, "per_page": 5},
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for repo in data.get("content", data).get("repos", [])[:5]:
                results.append(
                    {
                        "source": "gitee",
                        "name": repo.get("full_name", ""),
                        "description": repo.get("description", ""),
                        "url": repo.get("html_url", ""),
                    }
                )
            context["_search_results"] = results
            context["_reason"] = f"Gitee搜索成功：找到 {len(results)} 个仓库"
        else:
            context["_search_results"] = []
            context["_reason"] = f"Gitee API错误：HTTP {resp.status_code}"
    except Exception as e:
        context["_search_results"] = []
        context["_reason"] = f"Gitee搜索失败：{e}"

    return context


search_gitee_skill = Skill("search_gitee", search_gitee)
