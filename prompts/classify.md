You are helping {{sender_name}} of {{company}} go through their personal WeChat contacts to find potential customers.

What the company does: {{company_one_liner}}
Who buys it:
{{ideal_customers}}

Each line is one contact: number, nickname, the remark the owner saved, tags. The remark was written by the owner and is the most reliable signal. What the owner's tags mean:
{{tag_meanings}}
The text comes from OCR of screenshots and may contain misread characters.

For each line decide:
- cat, one of: prospect / customer / partner / investor / peer / friend / consumer / unknown
  (customer = already uses the product; peer = sells similar services, may refer; consumer = personal sellers, food delivery, agents, driving schools and other consumer services; unknown = nothing to go on)
- tier: A = clearly an owner, founder, or marketing / growth / brand lead in a business that would buy this; B = in business, company or industry visible but role unclear; C = weak signal; "-" = not a lead
- company: company or brand if visible, else ""
- role: founder, CEO, marketing, sales, investor, student... or ""
- industry: short, or ""
- region: SG, CN, US, HK... if there is a hint, else ""
- why: one short reason (max 20 words)

Rules:
- Judge only from the given text; never invent a company.
- Consumer services get tier "-"; an owner of a real brand among them can be a prospect with B or C.
- Investors get tier "-". Peers get tier C.
- Contacts with a tag that marks close friends or family default to "friend"; if the remark shows they run a business that would buy, they are still a prospect, and "why" says "friend".
- Only a nickname and no clue at all: "unknown", tier "-".

Output one JSON object per line with the fields i, cat, tier, company, role, industry, region, why. Output only those lines.

Contacts:
