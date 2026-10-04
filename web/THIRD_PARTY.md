# Third-party components

The files in `src/components/ui` are vendored from three MIT-licensed component
registries. They are unmodified except `bento-grid.tsx`, whose icon prop type
and text colours were changed so it type-checks and meets contrast guidelines.

| Files | Source | Licence |
|---|---|---|
| `orb.tsx`, `conversation.tsx`, `message.tsx`, `response.tsx`, `shimmering-text.tsx` | [ElevenLabs UI](https://github.com/elevenlabs/ui) | MIT |
| `animated-shiny-text.tsx`, `bento-grid.tsx`, `blur-fade.tsx`, `border-beam.tsx`, `dot-pattern.tsx`, `number-ticker.tsx` | [Magic UI](https://github.com/magicuidesign/magicui) | MIT |
| `message-loading.tsx` | A community component supplied by the project owner (21st.dev format) | as supplied |
| everything else in the folder | [shadcn/ui](https://github.com/shadcn-ui/ui) | MIT |

The chat panel in `src/chat/ChatPanel.tsx` follows the layout of the ElevenLabs UI
"Voice chat 1" block and is wired to the repkit API instead of an ElevenLabs
voice agent.
