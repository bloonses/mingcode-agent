import json
import uuid
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from config.config import get_user_data_dir


class LongTermMemory:
    MEMORY_TYPES = {"preference", "project", "success", "lesson"}
    
    def __init__(self):
        self.data_dir = get_user_data_dir()
        self.memory_file = self.data_dir / "long_term_memory.json"
        self.memories: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._load()
    
    def _load(self) -> None:
        if self.memory_file.exists():
            try:
                with open(self.memory_file, "r", encoding="utf-8") as f:
                    self.memories = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.memories = []
        else:
            self.memories = []
    
    def _save(self) -> None:
        with self._lock:
            with open(self.memory_file, "w", encoding="utf-8") as f:
                json.dump(self.memories, f, ensure_ascii=False, indent=2)
    
    def _extract_tags(self, content: str) -> List[str]:
        words = re.findall(r'[a-zA-Z_]+|[\u4e00-\u9fff]{2,}', content.lower())
        stop_words = {"the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
                      "have", "has", "had", "do", "does", "did", "will", "would", "could",
                      "should", "may", "might", "must", "shall", "can", "need", "dare",
                      "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
                      "from", "as", "into", "through", "during", "before", "after", "above",
                      "below", "between", "out", "off", "over", "under", "again", "further",
                      "then", "once", "here", "there", "when", "where", "why", "how", "all",
                      "each", "few", "more", "most", "other", "some", "such", "no", "nor",
                      "not", "only", "own", "same", "so", "than", "too", "very", "just",
                      "这个", "那个", "的", "了", "在", "是", "我", "有", "和", "就",
                      "不", "人", "都", "一", "一个", "上", "也", "很", "到", "说", "要",
                      "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "那"}
        tags = [w for w in words if w not in stop_words and len(w) >= 2]
        return list(set(tags))[:15]
    
    def add(self, content: str, memory_type: str = "lesson", tags: Optional[List[str]] = None) -> str:
        if memory_type not in self.MEMORY_TYPES:
            memory_type = "lesson"
        
        memory_id = str(uuid.uuid4())[:8]
        entry = {
            "id": memory_id,
            "type": memory_type,
            "content": content,
            "created_at": datetime.now().isoformat(),
            "last_used": None,
            "use_count": 0,
            "tags": tags or self._extract_tags(content)
        }
        self.memories.append(entry)
        self._save()
        return memory_id
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not self.memories:
            return []
        
        query_tags = set(self._extract_tags(query))
        if not query_tags:
            query_tags = {w.lower() for w in query.split() if len(w) >= 2}
        
        scored = []
        for mem in self.memories:
            mem_tags = set(mem.get("tags", []))
            overlap = len(query_tags & mem_tags)
            content_lower = mem["content"].lower()
            query_lower = query.lower()
            substring_bonus = 0
            for word in query_tags:
                if len(word) >= 3 and word in content_lower:
                    substring_bonus += 1
            recency_bonus = 0
            if mem.get("last_used"):
                try:
                    last_used = datetime.fromisoformat(mem["last_used"])
                    days_ago = (datetime.now() - last_used).days
                    recency_bonus = max(0, 10 - days_ago) * 0.1
                except (ValueError, TypeError):
                    pass
            use_bonus = min(mem.get("use_count", 0) * 0.05, 2)
            score = overlap * 2 + substring_bonus + recency_bonus + use_bonus
            if score > 0:
                scored.append((score, mem))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, mem in scored[:top_k]:
            mem["last_used"] = datetime.now().isoformat()
            mem["use_count"] = mem.get("use_count", 0) + 1
            results.append(mem)
        self._save()
        return results
    
    def get_all(self, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        if memory_type:
            return [m for m in self.memories if m["type"] == memory_type]
        return self.memories.copy()
    
    def get_by_id(self, memory_id: str) -> Optional[Dict[str, Any]]:
        for mem in self.memories:
            if mem["id"] == memory_id:
                return mem
        return None
    
    def delete(self, memory_id: str) -> bool:
        original_len = len(self.memories)
        self.memories = [m for m in self.memories if m["id"] != memory_id]
        if len(self.memories) < original_len:
            self._save()
            return True
        return False
    
    def clear(self, memory_type: Optional[str] = None) -> int:
        if memory_type:
            original_len = len(self.memories)
            self.memories = [m for m in self.memories if m["type"] != memory_type]
            removed = original_len - len(self.memories)
        else:
            removed = len(self.memories)
            self.memories = []
        self._save()
        return removed
    
    def format_for_prompt(self, query: str) -> str:
        relevant = self.retrieve(query)
        if not relevant:
            return ""
        
        type_icons = {
            "preference": "[PREF] User Preference",
            "project": "[PROJ] Project Knowledge",
            "success": "[OK]   Successful Experience",
            "lesson": "[FAIL] Lesson Learned"
        }
        
        lines = ["\n[Persistent Memory - Relevant Experience]"]
        for mem in relevant:
            icon = type_icons.get(mem["type"], "[MEM]  Memory")
            lines.append(f"- {icon}: {mem['content']}")
        lines.append("(Refer to above experience to avoid repeating mistakes, follow user preferences)\n")
        return "\n".join(lines)

    def auto_learn_from_error(self, error_msg: str, fix: str) -> Optional[str]:
        if not error_msg or not fix:
            return None
        content = f"错误: {error_msg[:100]} | 解决方案: {fix[:200]}"
        return self.add(content, memory_type="lesson")

    def auto_learn_preference(self, context: str, preference: str) -> Optional[str]:
        if not preference:
            return None
        content = f"{context}: {preference}"
        return self.add(content, memory_type="preference")

    def auto_learn_success(self, problem: str, solution: str) -> Optional[str]:
        if not problem or not solution:
            return None
        content = f"问题: {problem[:100]} | 有效方案: {solution[:200]}"
        return self.add(content, memory_type="success")
