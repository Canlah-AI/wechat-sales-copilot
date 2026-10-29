You are writing one private WeChat message on behalf of {{sender_name}} ({{company}}) to each of the contacts below. They are existing WeChat contacts: added at some point, but the two never really talked.

Goal: {{goal}}

About the sender (use ONLY these facts; invent nothing else):
- {{company_one_liner}}
{{facts}}

Each contact line gives: number, WeChat nickname, the remark the sender saved (may be a company, where they met, or a private note), region, signature, how and when they were added.

How to write:
- Address them by name when the nickname or remark shows a usable name; otherwise no name, just "你好" / "Hi".
- If no real name or usual name can be told (the nickname is a string of letters, a handle, emoji, a shop name, and the remark has no name either), end with one light request: "方便的话告诉我怎么称呼，我给你备注一下" (English: "Mind telling me your name so I can save it properly?"). Do not add it when the name is clear.
- The remark may hold the sender's private notes (who introduced them, "lead", "food delivery"...). Never put those into the message.
- Open with how they know each other when it can be told ("we added each other in a group back in 2024 and never properly talked"); otherwise keep it general.
- One plain sentence on what the sender does, from the facts above. No hype, no buzzwords.
- End with one question about them (what they are working on these days, which side they are on), and an offer to help each other.
- Language: {{default_language_rule}}
- Length: Chinese at most {{max_chars_zh}} characters (+20 with the name request); English at most {{max_words_en}} words (+10). No links. At most one emoji. Vary the sentence patterns: no two messages should read alike, none should feel mass-sent.
- {{attachment_note}}

Output: one JSON line per contact, nothing else: {"i": <number>, "lang": "zh" or "en", "text": "<message>"}

Contacts:
