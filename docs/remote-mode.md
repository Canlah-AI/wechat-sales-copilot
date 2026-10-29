# Optional: run WeChat on a second Mac

The default is one Mac: WeChat, the scripts and you on the same machine, with the sender acting only while you are
away from the keyboard. If you have a spare always-on Mac, you can log WeChat in there instead and keep your own
keyboard and mouse free all day. This page describes that setup; nothing in the code requires it.

WeChat allows one desktop login per account, so the account moves to the second Mac: log out on your own Mac first.

## The permissions problem

macOS gives Accessibility and Screen Recording to an **app**, not to a user. Processes started over `ssh` belong to
`sshd`, which has neither, so screenshots come back blank and clicks are dropped. The way around it, without
granting anything to `sshd`:

1. On the second Mac, grant Accessibility and Screen Recording to **Terminal**.
2. Start a `tmux` server **from Terminal**, e.g. a `start_tmux.command` file containing
   `tmux -L wx has-session -t wx 2>/dev/null || tmux -L wx new-session -d -s wx`, launched with
   `open -g -a Terminal start_tmux.command`. Every window later opened in that tmux server inherits Terminal's grants.
3. From your own Mac, run each command in a new window of that tmux server instead of directly over ssh.

Always use `open -g` (background). Without `-g` the Terminal window jumps in front of WeChat, and if that happens at
the moment Send is clicked, the message stays behind as a draft.

## Two small helpers

`wxrun` (on your Mac): writes the command into a script on the second Mac, runs it with
`tmux -L wx new-window -d 'zsh <script>'`, waits for an exit-code file, then prints the output. Flags: `--detach`
for long jobs, `--tail <id>` to read their output later.

`wxfile` (on your Mac): sends a file that lives on your Mac. It copies the file with `scp` into an outbox folder on
the second Mac, keeping its name (the other side sees that name), then runs
`wxrun python3 -m wxmac.wx_send "<chat>" ["text"] --file <copied path>`.

Neither helper is in this repo yet: both are about thirty lines and depend on your ssh host name and paths.

## Things to set on the second Mac

- Keep it awake (`caffeinate -dims` or Energy settings) and decide about the screen saver: a locked screen stops
  every command until someone unlocks it in person or over Screen Sharing.
- Full Disk Access for Terminal if you want replies read from notifications there.
- Stop the sender with `python3 -m wxmac.stop_sender` over plain ssh (it needs no screen access); start it again from
  a Terminal-launched tmux window.
