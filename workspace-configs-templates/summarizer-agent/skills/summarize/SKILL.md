---
name: Summarize
description: Takes content and produces concise summaries. Can delegate to peers for confirmation.
tags:
  - summarize
  - text
  - analysis
examples:
  - "Summarize this article for me"
  - "Give me a brief overview of this content"
---

# Summarize Skill

When invoked, analyze the provided content and create a concise summary.

## Behavior
- Read the full content carefully
- Identify key points and main ideas
- Produce a summary that captures the essence in 2-3 sentences
- If the user asks for confirmation, delegate to a peer agent using `delegate_to_workspace`
- Always maintain factual accuracy in summaries
