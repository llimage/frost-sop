"""
FROST-SOP V6.0.1 知识库引擎
PHILOSOPHY: 情报不是堆砌，是分类、去重、验证、置信度标注后的可用知识。
这是狩猎→分析→整合 闭环中"整合"环节的基础设施。

知识库目录结构（Store 键前缀映射）：
  knowledge:lessons/      → 教训库
  knowledge:strategies/    → 策略库
  knowledge:tools/        → 工具库
  knowledge:templates/    → 模板库
  knowledge:intelligence/  → 原始情报（待整合）
  knowledge:_meta/        → 元数据（统计、索引）
"""

import logging
from datetime import datetime

from core.skill import Skill

logger = logging.getLogger(__name__)

# 四类知识库，对应 v2.0 文档
KNOWLEDGE_CATEGORIES = {
    "lessons": "教训库：失败经历、踩坑记录、风险警示",
    "strategies": "策略库：成功方法、增长策略、竞争优势",
    "tools": "工具库：工具推荐、使用教程、配置指南",
    "templates": "模板库：可复用的内容、结构、文档",
}

# 置信度等级
CONFIDENCE_LEVELS = {
    "high": {
        "label": "高",
        "description": "多个独立来源验证+亲自测试",
        "usage": "可直接应用于SOP和策略",
    },
    "medium": {
        "label": "中",
        "description": "单来源或理论推断",
        "usage": "可作为参考，但需验证后使用",
    },
    "low": {
        "label": "低",
        "description": "模糊来源或直觉判断",
        "usage": "仅作为探索方向，不直接使用",
    },
}


class KnowledgeBase:
    """
    V6.0.1 知识库引擎。
    提供情报分类、去重、验证、置信度标注、知识检索。
    """

    def __init__(self, store):
        """
        Args:
            store: Asset Store（HierarchicalStore 或 Store）
        """
        self.store = store
        self._ensure_categories()

    def _ensure_categories(self):
        """初始化知识库分类目录（如果不存在）"""
        for category in KNOWLEDGE_CATEGORIES:
            meta_key = f"knowledge:_meta:{category}_count"
            if self.store.load(meta_key) is None:
                self.store.save(meta_key, 0)
                logger.info("[KnowledgeBase] 初始化知识库分类: %s", category)

    # ============================================================
    # 1. 情报接收（分类）
    # ============================================================

    def ingest_intelligence(self, raw_data: dict, category: str = None) -> str:
        """
        接收原始情报，自动分类后存入 intelligence/_inbox。

        Args:
            raw_data: {
                "title": str,
                "content": str,
                "source": str,        # 来源（URL/来源名称）
                "source_type": str,   # "official" / "authority" / "blog" / "unknown"
                "tags": list[str],    # 标签
                "hunt_task_id": str,  # 关联的狩猎任务ID
            }
            category: 预设分类（如果为None，自动推断）

        Returns:
            情报ID
        """
        if not category:
            category = self._auto_classify(raw_data)

        intel_id = f"knowledge:intelligence/{datetime.now().strftime('%Y%m%d')}_{self._get_next_id('intelligence')}"

        record = {
            "id": intel_id,
            "title": raw_data.get("title", "未命名情报"),
            "content": raw_data.get("content", ""),
            "source": raw_data.get("source", "unknown"),
            "source_type": raw_data.get("source_type", "unknown"),
            "tags": raw_data.get("tags", []),
            "hunt_task_id": raw_data.get("hunt_task_id", ""),
            "category": category,
            "ingested_at": datetime.now().isoformat(),
            "status": "raw",  # raw → cleaned → verified → activated
        }

        self.store.save(intel_id, record)
        self._increment_count("intelligence")
        logger.info("[KnowledgeBase] 情报已接收: %s (category=%s)", intel_id, category)
        return intel_id

    def _auto_classify(self, raw_data: dict) -> str:
        """基于内容关键词自动推断分类"""
        content = f"{raw_data.get('title', '')} {raw_data.get('content', '')}"
        tags = [t.lower() for t in raw_data.get("tags", [])]

        # 关键词匹配规则
        lesson_keywords = ["失败", "踩坑", "坑", "教训", "错误", "崩溃", "bug", "故障"]
        strategy_keywords = ["策略", "方法", "增长", "优化", "提升", "转化率", "留存"]
        tool_keywords = ["工具", "软件", "app", "插件", "平台", "api", "sdk"]
        template_keywords = ["模板", "sop", "流程", "清单", "checklist", "框架"]

        for kw in lesson_keywords:
            if kw in content or kw in tags:
                return "lessons"
        for kw in strategy_keywords:
            if kw in content or kw in tags:
                return "strategies"
        for kw in tool_keywords:
            if kw in content or kw in tags:
                return "tools"
        for kw in template_keywords:
            if kw in content or kw in tags:
                return "templates"

        return "intelligence"  # 无法分类，留在收件箱

    # ============================================================
    # 2. 情报清洗（去重）
    # ============================================================

    def deduplicate(self, category: str = None) -> list[str]:
        """
        对指定分类的情报进行去重。
        去重规则：
        - 保留最权威的：official > authority > blog > unknown
        - 保留最具体的：content长度更长
        - 保留最新的：ingested_at 更近
        - 保留多源验证的：source_type更高级

        Returns:
            被合并/删除的情报ID列表
        """
        removed = []
        prefix = "knowledge:intelligence/" if category is None else f"knowledge:{category}/"

        # 收集所有情报
        all_keys = [k for k in self.store.list_keys() if k.startswith(prefix)]
        items = []
        for key in all_keys:
            data = self.store.load(key)
            if data and isinstance(data, dict):
                items.append((key, data))

        # 按标题相似度分组（简单实现：标题包含关系）
        groups: dict[str, list[tuple[str, dict]]] = {}
        for key, data in items:
            title = data.get("title", "")
            matched = False
            for group_key in list(groups.keys()):
                if self._title_similar(title, groups[group_key][0][1].get("title", "")):
                    groups[group_key].append((key, data))
                    matched = True
                    break
            if not matched:
                groups[key] = [(key, data)]

        # 每组内去重：保留最佳
        for group_items in groups.values():
            if len(group_items) <= 1:
                continue
            best = self._select_best(group_items)
            for key, data in group_items:
                if key != best[0]:
                    # 合并到最佳记录
                    merged = self._merge_records(best[1], data)
                    self.store.save(best[0], merged)
                    # 删除重复
                    self.store.delete(key)
                    removed.append(key)
                    logger.info("[KnowledgeBase] 去重合并: %s -> %s", key, best[0])

        return removed

    def _title_similar(self, t1: str, t2: str) -> bool:
        """判断标题是否相似（简化版：包含关系或共享关键词）"""
        t1_lower = t1.lower()
        t2_lower = t2.lower()
        # 直接包含
        if t1_lower in t2_lower or t2_lower in t1_lower:
            return True
        # 共享关键词（长度>=3）
        words1 = set(w for w in t1_lower.split() if len(w) >= 3)
        words2 = set(w for w in t2_lower.split() if len(w) >= 3)
        if len(words1 & words2) >= 2:
            return True
        return False

    def _select_best(self, items: list[tuple]) -> tuple:
        """从一组相似情报中选择最佳"""
        source_rank = {"official": 4, "authority": 3, "blog": 2, "unknown": 1}
        scored = []
        for key, data in items:
            rank = source_rank.get(data.get("source_type", "unknown"), 0)
            content_len = len(data.get("content", ""))
            # 综合评分：权威性*1000 + 内容长度
            score = rank * 1000 + content_len
            scored.append((score, key, data))
        scored.sort(reverse=True)
        return scored[0][1], scored[0][2]

    def _merge_records(self, best: dict, other: dict) -> dict:
        """合并重复记录到最佳记录"""
        merged = dict(best)
        # 合并来源列表
        sources = merged.get("merged_sources", [])
        sources.append(
            {
                "source": other.get("source"),
                "source_type": other.get("source_type"),
                "ingested_at": other.get("ingested_at"),
            }
        )
        merged["merged_sources"] = sources
        merged["merge_count"] = merged.get("merge_count", 0) + 1
        merged["status"] = "cleaned"
        return merged

    # ============================================================
    # 3. 情报验证
    # ============================================================

    def verify(self, intel_id: str) -> dict:
        """
        验证情报的可信度。

        验证维度：
        1. 来源验证：source_type 是否可信
        2. 逻辑验证：content 是否自洽（简化：长度>100字视为"详细"）
        3. 时效验证：是否有时间戳

        Returns:
            {"verified": bool, "confidence": "high/medium/low", "reasons": list}
        """
        data = self.store.load(intel_id)
        if not data or not isinstance(data, dict):
            return {"verified": False, "confidence": "low", "reasons": ["情报不存在"]}

        reasons = []
        score = 0

        # 来源验证
        source_type = data.get("source_type", "unknown")
        if source_type == "official":
            score += 3
            reasons.append("✅ 来源为官方文档")
        elif source_type == "authority":
            score += 2
            reasons.append("⚠️ 来源为权威媒体")
        elif source_type == "blog":
            score += 1
            reasons.append("⚠️ 来源为个人博客")
        else:
            reasons.append("❓ 来源未知")

        # 逻辑验证（内容长度）
        content = data.get("content", "")
        if len(content) > 500:
            score += 2
            reasons.append("✅ 内容详细（>500字）")
        elif len(content) > 100:
            score += 1
            reasons.append("⚠️ 内容较简短")
        else:
            reasons.append("❓ 内容过于简短")

        # 时效验证
        ingested_at = data.get("ingested_at", "")
        if ingested_at:
            score += 1
            reasons.append("✅ 有明确时间戳")
        else:
            reasons.append("❓ 无时间戳")

        # 多源验证
        merged = data.get("merged_sources", [])
        if len(merged) >= 2:
            score += 2
            reasons.append(f"✅ 多源验证（{len(merged)}个来源）")

        # 置信度判定
        if score >= 5:
            confidence = "high"
        elif score >= 3:
            confidence = "medium"
        else:
            confidence = "low"

        verified = confidence in ("high", "medium")

        result = {
            "verified": verified,
            "confidence": confidence,
            "score": score,
            "reasons": reasons,
            "verified_at": datetime.now().isoformat(),
        }

        # 更新情报记录
        data["verification"] = result
        data["status"] = "verified" if verified else "questionable"
        self.store.save(intel_id, data)

        return result

    # ============================================================
    # 4. 知识激活（从情报到可用知识）
    # ============================================================

    def activate(self, intel_id: str) -> str:
        """
        将已验证的情报转化为可用知识，存入对应分类库。

        Args:
            intel_id: 情报ID

        Returns:
            知识条目ID
        """
        data = self.store.load(intel_id)
        if not data or not isinstance(data, dict):
            raise ValueError(f"情报不存在: {intel_id}")

        verification = data.get("verification", {})
        if verification.get("confidence") == "low":
            raise ValueError(f"情报置信度低，不可激活: {intel_id}")

        category = data.get("category", "intelligence")
        knowledge_id = f"knowledge:{category}/{datetime.now().strftime('%Y%m%d')}_{self._get_next_id(category)}"

        knowledge = {
            "id": knowledge_id,
            "title": data.get("title", ""),
            "content": data.get("content", ""),
            "source": data.get("source", ""),
            "confidence": verification.get("confidence", "medium"),
            "verified": verification.get("verified", False),
            "tags": data.get("tags", []),
            "hunt_task_id": data.get("hunt_task_id", ""),
            "original_intel_id": intel_id,
            "activated_at": datetime.now().isoformat(),
        }

        self.store.save(knowledge_id, knowledge)
        self._increment_count(category)

        # 标记情报为已激活
        data["status"] = "activated"
        data["knowledge_id"] = knowledge_id
        self.store.save(intel_id, data)

        logger.info("[KnowledgeBase] 知识已激活: %s (from %s)", knowledge_id, intel_id)
        return knowledge_id

    # ============================================================
    # 5. 知识检索
    # ============================================================

    def query(
        self, category: str = None, tags: list = None, min_confidence: str = "medium"
    ) -> list[dict]:
        """
        查询知识库。

        Args:
            category: 分类过滤（lessons/strategies/tools/templates）
            tags: 标签过滤
            min_confidence: 最低置信度（high/medium/low）

        Returns:
            知识条目列表
        """
        confidence_rank = {"high": 3, "medium": 2, "low": 1}
        min_rank = confidence_rank.get(min_confidence, 2)

        prefix = "knowledge:" if category is None else f"knowledge:{category}/"
        keys = [k for k in self.store.list_keys() if k.startswith(prefix)]

        results = []
        for key in keys:
            data = self.store.load(key)
            if not data or not isinstance(data, dict):
                continue
            # 置信度过滤
            conf = data.get("confidence", "low")
            if confidence_rank.get(conf, 0) < min_rank:
                continue
            # 标签过滤
            if tags:
                item_tags = set(t.lower() for t in data.get("tags", []))
                query_tags = set(t.lower() for t in tags)
                if not item_tags & query_tags:
                    continue
            results.append(data)

        # 按置信度排序，高置信度在前
        results.sort(key=lambda x: confidence_rank.get(x.get("confidence", "low"), 0), reverse=True)
        return results

    def get_stats(self) -> dict:
        """返回知识库统计"""
        stats: dict[str, int] = {"total": 0}
        for category in list(KNOWLEDGE_CATEGORIES.keys()) + ["intelligence"]:
            count = self.store.load(f"knowledge:_meta:{category}_count") or 0
            stats[category] = count
            stats["total"] += count
        return stats

    # ============================================================
    # 辅助函数
    # ============================================================

    def _get_next_id(self, category: str) -> int:
        """获取下一个自增ID"""
        key = f"knowledge:_meta:{category}_next_id"
        current = self.store.load(key) or 0
        current += 1
        self.store.save(key, current)
        return current

    def _increment_count(self, category: str):
        """增加分类计数"""
        key = f"knowledge:_meta:{category}_count"
        count = self.store.load(key) or 0
        self.store.save(key, count + 1)


# 便捷函数：创建知识库实例
def create_knowledge_base(store) -> KnowledgeBase:
    """创建知识库实例"""
    return KnowledgeBase(store)


# 便捷函数：一键整合（从狩猎情报到可用知识）
def integrate_hunt_intelligence(context: dict) -> dict:
    """
    Skill函数：将狩猎结果整合到知识库。

    输入 context 键：
        _hunt_sop_result: dict — 狩猎结果（来自 hunt_sop）
        _asset_store: Store — 资产Store

    输出 context 键：
        _knowledge_integration_result: dict — 整合结果
    """
    hunt_result = context.get("_hunt_sop_result", {})
    store = context.get("_asset_store")

    if not hunt_result or not store:
        context["_knowledge_integration_result"] = {
            "success": False,
            "reason": "缺少狩猎结果或Store",
        }
        return context

    kb = create_knowledge_base(store)
    integration_result: dict = {
        "ingested": 0,
        "deduplicated": 0,
        "verified": 0,
        "activated": 0,
        "errors": [],
    }

    try:
        # 1. 接收情报（从狩猎结果中提取候选）
        absorb_results = hunt_result.get("absorb_results", [])
        for result in absorb_results:
            if result.get("action") == "absorbed":
                intel = {
                    "title": f"狩猎获得: {result.get('new_skill_id', '未知')}",
                    "content": str(result),
                    "source": result.get("url", "hunt"),
                    "source_type": "authority"
                    if "github" in str(result.get("url", ""))
                    else "blog",
                    "tags": ["hunt", "skill", result.get("new_skill_id", "")],
                    "hunt_task_id": hunt_result.get("hunt_time", ""),
                }
                kb.ingest_intelligence(intel, category="tools")
                integration_result["ingested"] += 1

        # 2. 去重
        removed = kb.deduplicate()
        integration_result["deduplicated"] = len(removed)

        # 3. 验证
        for key in store.list_keys():
            if key.startswith("knowledge:intelligence/"):
                try:
                    kb.verify(key)
                    integration_result["verified"] += 1
                except Exception as e:
                    integration_result["errors"].append(str(e))

        # 4. 激活（高置信度情报）
        for key in store.list_keys():
            if key.startswith("knowledge:intelligence/"):
                data = store.load(key)
                if data and data.get("verification", {}).get("confidence") == "high":
                    try:
                        kb.activate(key)
                        integration_result["activated"] += 1
                    except Exception as e:
                        integration_result["errors"].append(str(e))

    except Exception as e:
        integration_result["errors"].append(str(e))
        logger.error("[KnowledgeBase] 整合失败: %s", e)

    integration_result["stats"] = kb.get_stats()
    context["_knowledge_integration_result"] = integration_result
    context["_reason"] = (
        f"知识库整合完成: 摄入{integration_result['ingested']}条, "
        f"去重{integration_result['deduplicated']}条, "
        f"激活{integration_result['activated']}条"
    )
    return context


# 导出 Skill 实例
integrate_hunt_intelligence_skill = Skill(
    "integrate_hunt_intelligence", integrate_hunt_intelligence
)


# 便捷函数：查询知识库 Skill
def query_knowledge_base(context: dict) -> dict:
    """
    Skill函数：查询知识库。

    输入 context 键：
        _knowledge_category: str — 分类（lessons/strategies/tools/templates）
        _knowledge_tags: list — 标签过滤
        _knowledge_min_confidence: str — 最低置信度
        _asset_store: Store

    输出 context 键：
        _knowledge_results: list — 知识条目列表
    """
    store = context.get("_asset_store")
    if not store:
        context["_knowledge_results"] = []
        return context

    kb = create_knowledge_base(store)
    results = kb.query(
        category=context.get("_knowledge_category"),
        tags=context.get("_knowledge_tags"),
        min_confidence=context.get("_knowledge_min_confidence", "medium"),
    )

    context["_knowledge_results"] = results
    context["_reason"] = f"知识库查询: 找到{len(results)}条知识"
    return context


query_knowledge_base_skill = Skill("query_knowledge_base", query_knowledge_base)
