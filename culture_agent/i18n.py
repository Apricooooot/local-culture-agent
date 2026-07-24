from __future__ import annotations

import re
from typing import Any, Iterable


SUPPORTED_LANGUAGES = {"en", "zh"}

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "saved": "Saved locally: {kind} {title}{rating}. Your original reflection has been preserved verbatim.",
        "signals": " Initial signals: {tags}.",
        "model_unavailable": "The model is unavailable ({error}), but your local library still works.",
        "rating_invalid": "Rating must be between 0 and 10.",
        "no_memories": "No relevant local records.",
        "unrated": "unrated",
        "memory_tags": "tags",
        "memory_reflection": "reflection",
        "none": "none",
        "catalog_empty": "The open catalogs returned no reliable candidates. Try relaxing the year, genre, or runtime constraints.",
        "recommendation_unavailable": "The recommendation model is unavailable ({error}). Your local records are safe; confirm that Ollama is running and try again.",
        "library_empty": "Your local library is empty. Try: “I watched Arrival, 9/10…”",
        "library_prefix": "Here are your local records:",
        "profile_insufficient": "There are not enough ratings to infer a preference yet. Any future inference will cite its evidence and remain correctable.",
        "profile_unstable": "I have rating facts, but no stable theme signal yet. I will not label your taste prematurely.",
        "profile_result": "Current preference signals: {details}. These are correctable inferences, not permanent labels.",
        "evidence": "evidence",
        "rating": ", {value}/10",
        "book": "book",
        "film": "film",
    },
    "zh": {
        "saved": "记好了：{kind} {title}{rating}。你的原始感受已经完整保存在本地。",
        "signals": " 我暂时提取了这些线索：{tags}。",
        "model_unavailable": "模型暂时不可用（{error}），但你的本地资料库仍然可以正常记录和查询。",
        "rating_invalid": "评分需要在 0 到 10 之间。",
        "no_memories": "暂无相关记录。",
        "unrated": "未评分",
        "memory_tags": "标签",
        "memory_reflection": "心得",
        "none": "无",
        "catalog_empty": "开放资料库没有返回符合条件的可靠候选。你可以放宽年份、类型或时长条件后重试。",
        "recommendation_unavailable": "推荐模型暂时不可用（{error}）。你的本地记录没有丢失；请确认 Ollama 正在运行后重试。",
        "library_empty": "你的本地资料库还是空的。可以从“我看完《作品名》，8分……”开始。",
        "library_prefix": "这是我找到的本地记录：",
        "profile_insufficient": "现在还没有足够的评分来形成偏好判断。我的推断会始终注明依据，并允许你纠正。",
        "profile_unstable": "目前只有评分事实，尚没有稳定的主题偏好信号；我不会过早给你贴标签。",
        "profile_result": "目前比较明显的偏好线索是：{details}。这些只是可纠正的推断。",
        "evidence": "依据",
        "rating": "，{value}/10",
        "book": "书籍",
        "film": "电影",
    },
}

LIST_SEPARATORS = {"en": ", ", "zh": "、"}

TAG_DEFINITIONS: dict[str, dict[str, Any]] = {
    "slow_paced": {
        "labels": {"en": "slow-paced", "zh": "慢节奏"},
        "keywords": {
            "en": ("slow-paced", "slow paced", "slow", "dragged", "too long"),
            "zh": ("慢", "段落略长"),
        },
    },
    "gentle": {
        "labels": {"en": "gentle", "zh": "温柔"},
        "keywords": {
            "en": ("gentle", "comforting", "healing", "cozy", "warm"),
            "zh": ("温柔", "治愈"),
        },
    },
    "restrained": {
        "labels": {"en": "restrained", "zh": "克制"},
        "keywords": {
            "en": ("restrained", "subtle", "understated"),
            "zh": ("克制", "含蓄"),
        },
    },
    "family": {
        "labels": {"en": "family", "zh": "家庭"},
        "keywords": {
            "en": ("family", "parent", "mother", "father", "sibling"),
            "zh": ("家庭", "家人"),
        },
    },
    "everyday_life": {
        "labels": {"en": "everyday life", "zh": "人生观察"},
        "keywords": {
            "en": ("everyday life", "daily life", "ordinary life", "human observation"),
            "zh": ("人生", "日常"),
        },
    },
    "mystery": {
        "labels": {"en": "mystery", "zh": "悬疑"},
        "keywords": {
            "en": ("mystery", "detective", "whodunit", "suspense"),
            "zh": ("悬疑", "推理"),
        },
    },
    "science_fiction": {
        "labels": {"en": "science fiction", "zh": "科幻"},
        "keywords": {
            "en": ("science fiction", "science-fiction", "sci-fi", "scifi", "future"),
            "zh": ("科幻", "未来"),
        },
    },
    "romance": {
        "labels": {"en": "romance", "zh": "浪漫"},
        "keywords": {
            "en": ("romance", "romantic", "love story"),
            "zh": ("浪漫", "爱情"),
        },
    },
    "humorous": {
        "labels": {"en": "humorous", "zh": "幽默"},
        "keywords": {
            "en": ("humorous", "funny", "hilarious", "comedy"),
            "zh": ("幽默", "好笑"),
        },
    },
    "heavy": {
        "labels": {"en": "heavy", "zh": "沉重"},
        "keywords": {
            "en": ("heavy", "depressing", "bleak", "dark"),
            "zh": ("沉重", "压抑"),
        },
    },
}

LEGACY_TAGS = {
    definition["labels"][language]: tag_id
    for tag_id, definition in TAG_DEFINITIONS.items()
    for language in SUPPORTED_LANGUAGES
}

INTENT_SIGNALS = {
    "recommend": {
        "en": ("recommend", "suggest", "what should i watch", "what should i read"),
        "zh": ("推荐", "想看", "想读", "看什么", "读什么"),
    },
    "library": {
        "en": ("library", "my records", "what have i watched", "what have i read"),
        "zh": ("资料库", "记录过", "看过什么", "读过什么"),
    },
    "profile": {
        "en": ("my taste", "my preferences", "what do i", "what i like"),
        "zh": ("我喜欢", "我的偏好", "品味", "为什么觉得"),
    },
}

COMPLEX_SIGNALS = {
    "en": (
        "compare", "contrast", "synthesize", "analyze deeply", "year in review",
        "annual review", "overall pattern", "trend", "conflicting preferences",
        "connect these works", "common themes", "how has my taste changed",
    ),
    "zh": (
        "比较", "对比", "综合", "深入分析", "年度总结", "年度回顾", "复盘",
        "共同主题", "变化趋势", "矛盾", "联系起来",
    ),
}

RECORD_SIGNALS = {
    "en": ("watched", "saw", "finished", "record", "rated", "read"),
    "zh": ("看完", "读完", "记录", "打分", "评分", "看了", "读了"),
}

BOOK_SIGNALS = {
    "en": ("book", "novel", "read", "reading", "finished reading"),
    "zh": ("书", "小说", "读完", "读了", "阅读"),
}

COMEDY_SIGNALS = {
    "en": ("comedy", "funny", "humorous", "lighthearted"),
    "zh": ("喜剧", "好笑", "幽默", "轻松"),
}

NO_ANIMATION_SIGNALS = {
    "en": ("no animation", "not animated", "live action only"),
    "zh": ("不要动画", "非动画"),
}


def detect_language(text: str) -> str:
    cjk_count = sum("\u4e00" <= character <= "\u9fff" for character in text)
    return "zh" if cjk_count >= 2 else "en"


def translate(language: str, key: str, **values: object) -> str:
    selected = language if language in SUPPORTED_LANGUAGES else "en"
    return MESSAGES[selected][key].format(**values)


def has_signal(text: str, group: dict[str, tuple[str, ...]]) -> bool:
    lowered = text.lower()
    return any(signal in lowered for signals in group.values() for signal in signals)


def classify_intent(text: str) -> str:
    lowered = text.lower()
    for intent in ("recommend", "library", "profile"):
        if any(
            signal in lowered
            for signals in INTENT_SIGNALS[intent].values()
            for signal in signals
        ):
            return intent
    return "chat"


def should_think(text: str) -> bool:
    return has_signal(text, COMPLEX_SIGNALS)


def extract_tags(text: str) -> list[str]:
    lowered = text.lower()
    return [
        tag_id
        for tag_id, definition in TAG_DEFINITIONS.items()
        if any(
            keyword in lowered
            for keywords in definition["keywords"].values()
            for keyword in keywords
        )
    ]


def canonical_tag(value: str) -> str:
    return LEGACY_TAGS.get(value, value)


def tag_label(value: str, language: str) -> str:
    tag_id = canonical_tag(value)
    definition = TAG_DEFINITIONS.get(tag_id)
    if not definition:
        return value
    return definition["labels"].get(language, definition["labels"]["en"])


def localized_tags(values: Iterable[str], language: str) -> list[str]:
    return [tag_label(value, language) for value in values]


def join_localized(values: Iterable[str], language: str) -> str:
    return LIST_SEPARATORS.get(language, LIST_SEPARATORS["en"]).join(values)


def is_book_request(text: str) -> bool:
    return has_signal(text, BOOK_SIGNALS)


def is_comedy_request(text: str) -> bool:
    return has_signal(text, COMEDY_SIGNALS)


def excludes_animation(text: str) -> bool:
    return has_signal(text, NO_ANIMATION_SIGNALS)


def extract_title(text: str, language: str) -> str:
    bracketed = re.search(r"《([^》]{1,120})》", text)
    if bracketed:
        return bracketed.group(1).strip()

    quoted = re.search(r"[\"“]([^\"”]{1,120})[\"”]", text)
    if quoted:
        return quoted.group(1).strip()

    patterns = (
        (
            r"\b(?:i\s+)?(?:watched|saw|rated)\s+(?:(?:the\s+)?(?:film|movie)\s+)?(.+?)(?=,\s*|\s+\d+(?:\.\d+)?\s*/10|\.\s|$)",
            r"\b(?:i\s+)?(?:finished\s+reading|read|finished)\s+(?:(?:the\s+)?(?:book|novel)\s+)?(.+?)(?=,\s*|\s+\d+(?:\.\d+)?\s*/10|\.\s|$)",
        )
        if language == "en"
        else (
            r"(?:我)?(?:看完了?|看了|观看了?|记录(?:一部)?(?:电影|影片)?)[：:\s]*(?:电影|影片)?[：:\s]*([^，,。.!！?？；;]+?)(?=\s*(?:，|,|\d+(?:\.\d+)?\s*分|。|！|？|$))",
            r"(?:我)?(?:读完了?|读了|阅读了?|记录(?:一本)?(?:书|小说)?)[：:\s]*(?:书|小说)?[：:\s]*([^，,。.!！?？；;]+?)(?=\s*(?:，|,|\d+(?:\.\d+)?\s*分|。|！|？|$))",
        )
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" .")
    return ""


def extract_rating(text: str) -> float | None:
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:分|/10|out\s+of\s+10|points?|stars?)",
        text,
        flags=re.IGNORECASE,
    )
    return float(match.group(1)) if match else None


def extract_creator(text: str, language: str) -> str:
    patterns = (
        [
            r"(?:作者|导演)[是：:\s]*([^，。；;]+)",
            r"([\w\u4e00-\u9fff·]{2,30})(?:的|导演的)《",
        ]
        if language == "zh"
        else [r"directed\s+by\s+([^,.;]+)", r"(?:written\s+)?by\s+([^,.;]+)"]
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""

