# Pitfalls found on a real account

One line each: what you see · what is really going on · what the code does about it. WeChat for Mac 4.1.13 / 4.1.15,
English interface, unless noted. When a new one turns up, add a line here and a test where the logic is pure.

## Finding the right chat

- A search row reads exactly like the name but opens a web search · "Internet search results" lists the same text, and
  section order varies · a row counts only when the nearest heading above it is a chat section (`search_hits`).
- Every recently used chat is refused · 4.1.15 files them under "Most used", which was not a known chat section ·
  the heading is in `ui_strings`; when a new heading appears, add it before retrying.
- Only "Internet search results", no contact · the saved name was misread when contacts were captured · search by the
  Weixin ID from the card (`--search`); if that fails too, skip the contact, never force it.
- Short names (two or three letters) never show up · partial matches push them out of view · search by Weixin ID.
- The name is found by Weixin ID but OCR reads it as garbage ('Lu）' for 'Luna') · the name row is misread, the
  ID row is not · exactly one "Weixin ID: <id>" row matching the query counts; the header is still checked.
- A group with the same name as a person · group headers carry "(member count)" · `--person` refuses any header with a
  count; outreach always uses it.
- The header is read one character off ('张小両' for '张小雨') · the header font is larger than the search popup's ·
  with `--person`, a similarity of 0.8 or more counts as the same person (names of 4+ characters).
- File Transfer cannot be searched in 4.1 · it is opened from its chat-list row, or from the sidebar phone icon's menu.
- File Transfer will not open; the chat pane goes blank · a click on the chat-list row while the phone menu is open
  only closes the menu, and a click on the row that is already open closes the chat · click the row only when no
  menu is open, and not at all when the header already shows the chat.

## Typing and sending

- Enter pops the chat out into its own small window and leaves the text as a draft (4.1.15) · Enter landed on the
  chat list · the Send button in the input box is clicked instead; a popped-out window is closed with
  `wxctl close-window "<title>"`.
- "Pasted text is not visible" although it is there · OCR misreads the start of the line, so comparing the first
  characters fails · the text is cut into 6-character pieces and two seen pieces are enough.
- The Send button is not found and Enter is used · OCR glues the voice icon on ("① Send") · `is_send` only looks at
  the end of a short line.
- A file paste does nothing · a bare file URL on the pasteboard is ignored by 4.1.15 · `wxctl clip-file` also
  declares the legacy filename list, as Finder's Copy does; the file must show its name before Send is pressed.
- The search popup and the input box overlap · the default window (880×640) is too small · `wxctl fit`.
- A message stays as a draft · another app's window came to the front at the moment of clicking Send (for example a
  terminal window opening) · start helper windows in the background (`open -g`); to resend, clear the draft first
  and check the box is empty, or the text goes out twice.

## Outcomes

- "Friend confirmation" after sending · the contact removed you · recorded for that contact only (`sent-not-friend`).
- "The user's account is restricted" · it is the **recipient's** account, not yours · recorded for that contact; this
  text is removed before looking for warnings, so it does not pause everything.
- Any other limit or "too frequent" message · your account is being limited · sending pauses for `pause_hours`.

## The screen

- Screenshots suddenly show no WeChat · Stage Manager moved the window off screen after another app came forward ·
  decisions use the screenshot taken while WeChat is in front.
- The screen locks overnight although sleep is disabled · `caffeinate` prevents sleep and display sleep, not the
  screen saver; with "require password immediately", the screen saver locks the session · nothing types into a lock
  screen (`wxctl` refuses); the user decides whether to lengthen the screen-saver delay.
- The Manage Contacts table offers Delete · a click on a row selects that contact · the capture only scrolls.
- Full-width colons on profile cards ("Name：") · OCR keeps the width · text is NFKC-folded before matching.

## Data files

- Two processes writing the outreach queue overwrite each other · do not run `plan` / `draft --import` while the
  sender is running (stop it first); the ledger, not the queue, decides whether someone was already messaged.
