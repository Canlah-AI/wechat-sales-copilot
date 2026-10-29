"""Pure helpers only: nothing here starts WeChat, takes a screenshot or sends a key. Run: python3 -m unittest -v"""
import json, unittest
from pathlib import Path

from wxmac import config
from wxmac.wx_outreach import warning_in
from wxmac.wx_send import is_send, key, pieces, same_chat, same_person, search_hits, section

FIX = json.loads((Path(__file__).parent / "fixtures/search_popup.json").read_text())


def line(text, y=100):
    return {"text": text, "x": 60, "y": y, "w": 80, "h": 18}


class Helpers(unittest.TestCase):
    def test_key_folds_width_case_and_punctuation(self):
        self.assertEqual(key("Ａｌｅｘ　Ｗ."), "alexw")
        self.assertEqual(key("张小雨 (Wren)"), "张小雨wren")

    def test_pieces_survive_a_garbled_greeting(self):
        text = "Hi 小雨，我是 Alex，好久没联系啦，最近在忙什么？"
        ps = pieces(text)
        self.assertTrue(all(len(p) == 6 for p in ps))
        garbled = "旧小面我是alex好久没联系啦最近在忙什么"  # OCR misread the first characters
        self.assertGreaterEqual(sum(p in key(garbled) for p in ps), 2)
        self.assertEqual(pieces("ok"), ["ok"])

    def test_is_send(self):
        for t in ("Send", "① Send", "发送"):
            self.assertTrue(is_send(line(t)), t)
        for t in ("Sending files now", "Sent", "Send to group chat"):
            self.assertFalse(is_send(line(t)), t)

    def test_section(self):
        self.assertEqual(section(line("Top Hits")), "chat")
        self.assertEqual(section(line("Most used")), "chat")
        self.assertEqual(section(line("Q Contacts")), "chat")  # OCR reads the icon as a letter
        self.assertEqual(section(line("Internet search results")), "other")
        self.assertEqual(section(line("Chat History")), "other")
        self.assertIsNone(section(line("Luna Park")))

    def test_same_person_and_same_chat(self):
        self.assertTrue(same_person("Wren 张小両", "Wren 张小雨"))  # header font misread by one character
        self.assertFalse(same_person("Wren 张小雨 (3)", "Wren 张小雨"))  # a group with the same name
        self.assertFalse(same_person("Al", "Ai"))  # short names must match exactly
        self.assertTrue(same_chat("Book Club (377)", "Book Club"))
        self.assertFalse(same_chat("Book Club Fans", "Book Club"))


class Search(unittest.TestCase):
    def test_lookalike_under_web_results_is_never_picked(self):
        hits = search_hits(FIX["web_lookalike"], "Luna Park", "Luna Park")
        self.assertEqual([h["y"] for h in hits], [92])

    def test_nothing_under_chat_sections_means_no_click(self):
        self.assertEqual(search_hits(FIX["only_web"], "Luna Park", "Luna Park"), [])

    def test_weixin_id_row_when_name_is_garbled(self):
        hits = search_hits(FIX["by_weixin_id"], "Luna", "luna_2024")
        self.assertEqual([h["text"] for h in hits], ["Weixin ID: luna_2024"])

    def test_truncated_long_name(self):
        hits = search_hits(FIX["most_used_ellipsis"], "Riverside Bakery Group", "Riverside Bakery Group")
        self.assertEqual(len(hits), 1)


class Outreach(unittest.TestCase):
    def test_warning_about_recipient_is_not_ours(self):
        self.assertIsNone(warning_in("The user's account is restricted. Unable to send message."))
        self.assertEqual(warning_in("操作频繁，请稍后再试"), "操作频繁")

    def test_render_lists(self):
        self.assertEqual(config.render("A\n{{facts}}", {"facts": ["x", "y"]}), "A\n- x\n- y")


if __name__ == "__main__":
    unittest.main()
