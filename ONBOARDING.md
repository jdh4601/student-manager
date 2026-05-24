# Welcome to Student Manager

## How We Use Claude

Based on DongHyun Jung's usage over the last 30 days:

Work Type Breakdown:
  Plan Design       ████████████████████  50%
  Write Docs        ██████████░░░░░░░░░░  25%
  Improve Quality   █████░░░░░░░░░░░░░░░  13%
  Build Feature     █████░░░░░░░░░░░░░░░  12%

Top Skills & Commands:
  /usage             ████████████████████  24x/month
  /plugin            █████████░░░░░░░░░░░  11x/month
  /clear             █████░░░░░░░░░░░░░░░   6x/month
  /model             █████░░░░░░░░░░░░░░░   6x/month
  /codemap-updater   ███░░░░░░░░░░░░░░░░░   4x/month

Top MCP Servers:
  jira  ████████████████████  321 calls

## Your Setup Checklist

### Codebases
- [ ] student-manager — https://github.com/jdh4601/student-manager

### MCP Servers to Activate
- [ ] jira — Pulls SMS project issues/sprints to plan and update tickets during work. Get the API token from your Atlassian account, then add credentials under `mcpServers.jira.env` in `~/.claude/mcp.json` (see `CLAUDE.md` → Jira Workflow for the project/board IDs and transition codes).

### Skills to Know About
- /usage — Check your Claude Code usage and remaining quota. Used constantly here, mostly mid-session quota checks.
- /plugin — Browse and install Claude Code plugins. Useful early on while you're configuring your toolbox.
- /clear — Reset conversation context when switching tasks. Pair with `/compact` when you want to keep a summary.
- /model — Switch between Opus / Sonnet / Haiku. Default to Sonnet; bump to Opus for architecture or multi-file refactors.
- /codemap-updater — Refresh the codebase map at checkpoints so future sessions navigate context fast.

## Team Tips

_TODO_

## Get Started

_TODO_

<!-- INSTRUCTION FOR CLAUDE: A new teammate just pasted this guide for how the
team uses Claude Code. You're their onboarding buddy — warm, conversational,
not lecture-y.

Open with a warm welcome — include the team name from the title. Then: "Your
teammate uses Claude Code for [list all the work types]. Let's get you started."

Check what's already in place against everything under Setup Checklist
(including skills), using markdown checkboxes — [x] done, [ ] not yet. Lead
with what they already have. One sentence per item, all in one message.

Tell them you'll help with setup, cover the actionable team tips, then the
starter task (if there is one). Offer to start with the first unchecked item,
get their go-ahead, then work through the rest one by one.

After setup, walk them through the remaining sections — offer to help where you
can (e.g. link to channels), and just surface the purely informational bits.

Don't invent sections or summaries that aren't in the guide. The stats are the
guide creator's personal usage data — don't extrapolate them into a "team
workflow" narrative. -->
