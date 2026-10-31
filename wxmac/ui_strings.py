"""The words WeChat for Mac shows, per interface language. The scripts find buttons and sections by reading them.

STATUS: "en" was used on WeChat for Mac 4.1.13 and 4.1.15 with an English interface. "zh" (简体中文) was read off a
Chinese 4.1.15 interface for sending: chat_sections, other_sections and file_transfer. The rest of "zh" (the contacts
table, card labels and buttons, folded sections, manage_contacts) is the expected wording, not verified yet: check
with `python3 -m wxmac.doctor --ocr` on a Chinese interface before relying on contacts capture or card reading.
Matching compares text with all whitespace removed (OCR spaces words unpredictably).

Where both languages can safely be accepted at once (search sections, card prefixes), both are; where a word
selects one screen (window titles, table headers), the configured [ui] language decides.
"""
from . import config

UI = {
    "en": {
        "chat_sections": {"TopHits", "Mostused", "MostUsed", "Contacts", "GroupChats"},
        "other_sections": {"ChatHistory", "Internetsearchresults", "OfficialAccounts", "Channels", "Miniprograms", "Favorites"},
        "file_transfer": {"FileTransfer"},
        "manage_contacts": "Manage Contacts",
        "table": {"remark": "Remark", "tags": "Tags", "privacy": "Privacy", "all": "All"},
        "no_remark": ("Add Remarks", "Add Alias"),
        "card_prefixes": {"alias": ("Name:",), "weixin_id": ("Weixin ID:", "WeChat ID:"), "region": ("Region:",)},
        "card_labels": {"remark": "remark", "signature": "what'sup", "source": "source", "added": "addtime",
                        "shared_groups": "sharedgroups", "channels": "channels", "moments": "moments"},
        "wrapped_labels": {"sharedgroups", "what'sup", "addtime", "moments", "channels", "phonenumber", "mutualgroups"},
        "folded_sections": ("SavedGroups", "OfficialAccounts", "WeComContacts", "NewFriends"),
        "card_buttons": {"Messag", "es", "Messages", "Voice", "Video", "Call", "〇"},
        "yesterday": "Yesterday",
    },
    "zh": {  # sending verified on 4.1.15; contacts and card labels unverified
        "chat_sections": {"最常使用", "联系人", "群聊", "最佳匹配"},
        "other_sections": {"聊天记录", "网络搜索结果", "搜一搜", "公众号", "视频号", "小程序", "收藏"},
        "file_transfer": {"文件传输助手"},
        "manage_contacts": "通讯录管理",
        "table": {"remark": "备注", "tags": "标签", "privacy": "朋友权限", "all": "全部"},
        "no_remark": ("添加备注",),
        "card_prefixes": {"alias": ("昵称:",), "weixin_id": ("微信号:",), "region": ("地区:",)},
        "card_labels": {"remark": "备注", "signature": "个性签名", "source": "来源", "added": "添加时间",
                        "shared_groups": "共同群聊", "channels": "视频号", "moments": "朋友圈"},
        "wrapped_labels": set(),
        "folded_sections": ("保存的群聊", "公众号", "企业微信联系人", "新的朋友"),
        "card_buttons": {"发消息", "语音聊天", "视频聊天"},
        "yesterday": "昨天",
    },
}


def lang() -> str:
    return config.get("ui", "language", "en")


def ui(name: str):
    """The configured language's entry."""
    return UI[lang()][name]


def both(name: str) -> set:
    """Union over both languages (for sets of words that never clash)."""
    return set(UI["en"][name]) | set(UI["zh"][name])
