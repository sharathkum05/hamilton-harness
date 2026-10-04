# Third-party components

The files in `src/components/ui` are vendored, unmodified, from two MIT-licensed
component registries.

| Files | Source | Licence |
|---|---|---|
| `orb.tsx`, `conversation.tsx`, `message.tsx`, `response.tsx`, `shimmering-text.tsx` | [ElevenLabs UI](https://github.com/elevenlabs/ui) | MIT |
| `avatar.tsx`, `button.tsx`, `card.tsx`, `input.tsx`, `scroll-area.tsx`, `tooltip.tsx` | [shadcn/ui](https://github.com/shadcn-ui/ui) | MIT |

The chat panel in `src/chat/ChatPanel.tsx` follows the layout of the ElevenLabs UI
"Voice chat 1" block and is wired to the repkit API instead of an ElevenLabs
voice agent.
