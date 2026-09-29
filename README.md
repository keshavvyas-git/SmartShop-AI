# SmartShop AI

**A thoughtful shopping assistant that helps you compare products and choose with confidence.**

SmartShop AI is a responsive chat app featuring **Ani**, an AI shopping assistant. Describe what you want to buy, your budget, and what matters to you. Ani researches relevant options, explains the trade-offs, and recommends a suitable choice in plain language.

> **Live demo:** [Open the public `onrender.com` URL shown on the `smartshop-ai` service page in Render.](https://smartshop-ai-995v.onrender.com)

## Features

- Natural-language shopping requests, with India and INR as the default market.
- Live product research through Groq's browser search tool.
- Shortlists and comparisons that highlight fit, price, and trade-offs.
- A clear recommendation followed by an easy-to-understand explanation.
- Direct source links, with instructions to prefer official product information, reputable reviewers, and established retailers.
- Editable suggestion prompts: selecting an idea fills the composer; it does not send the message.
- Responsive chat interface, sunflower-inspired light and dark themes, and reduced-motion support.
- Server-side API key handling, request limits, a health endpoint, and basic security headers.

Product prices and availability can change. Always open the linked source and confirm the exact model and current price before buying. Ani is an AI assistant; verify important product details with the retailer or manufacturer.

## Screenshots

Screenshots make the project easier to understand at a glance. Recommended captures:

| Suggested file | What to capture |
| --- | --- |
| `docs/screenshots/welcome-desktop.png` | Welcome screen with the four editable shopping prompts. |
| `docs/screenshots/shortlist-desktop.png` | A product comparison, recommendation, and plain-language explanation. |
| `docs/screenshots/shortlist-mobile.png` | The same answer at a phone-sized viewport to show the responsive layout. |
| `docs/screenshots/dark-mode.png` | The chat and product cards in dark mode. |

Save screenshots in `docs/screenshots/`, then embed them here with Markdown, for example:

```markdown
![SmartShop AI product shortlist on mobile](docs/screenshots/shortlist-mobile.png)
```

Before sharing screenshots publicly, remove personal information and make sure any displayed product claims and prices are clearly presented as examples.

## How to use SmartShop

1. Open the deployed app or start it locally using the setup steps below.
2. Type what you want to buy. Include your budget, country, and the features or use case that matter most.
3. You can select a suggestion to start a draft, then edit it before sending.
4. Send the request with the send button or **Enter**. Use **Shift+Enter** for a new line.
5. Review the comparison, source links, recommendation, and simple explanation. Check the linked source for current price and availability.
6. Use the theme button in the top-right corner to switch between light and dark mode.

Example request:

> I need a laptop for coding in India for under ₹30,000. Prioritize a reliable keyboard and enough memory for everyday programming.

## Technology

| Area | Technology |
| --- | --- |
| Interface | HTML, CSS, and browser-native JavaScript |
| Server | Node.js built-in HTTP server (no runtime package dependencies) |
| AI | Groq Chat Completions API with `openai/gpt-oss-120b` by default |
| Product research | Groq's built-in `browser_search` tool |
| Hosting | Render web service configured with a Blueprint |

### Request flow

1. The browser sends the current chat history to the same-origin `/api/chat` endpoint.
2. The Node server validates and limits the request, then calls Groq using the server-side `GROQ_API_KEY`.
3. Ani returns a concise, shopping-focused answer. The browser formats Markdown comparisons into responsive product cards.

The API key is never sent to the browser. The app does not have user accounts, a database, or persistent chat history; a conversation lives in the current page session.

## Run locally

### Requirements

- Node.js **20.12 or newer**.
- A Groq API key with access to the configured model and browser search.

### Setup (PowerShell)

```powershell
git clone https://github.com/keshavvyas-git/SmartShop-AI.git
cd SmartShop-AI
Copy-Item .env.example .env
```

Open `.env` in a text editor and replace the placeholder with your key:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
GROQ_MAX_COMPLETION_TOKENS=900
PORT=3000
```

Keep the real key private. `.env` is ignored by Git; never commit it or paste the key into source files, screenshots, or chat.

Start the app:

```powershell
npm.cmd start
```

Open <http://localhost:3000>. To stop the server, press **Ctrl+C** in the terminal.

The repository also includes a syntax-check command:

```powershell
npm.cmd run check
```

## Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `GROQ_API_KEY` | Yes | — | Secret credential used by the server to call Groq. |
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` | Groq model used for chat and product research. |
| `GROQ_MAX_COMPLETION_TOKENS` | No | `900` | Response token budget; the server caps this setting at 1,200. |
| `PORT` | No | `3000` locally | HTTP port. The hosting platform supplies its own port in production. |

The app defaults to India and INR. For example, `30k` is interpreted as ₹30,000 unless the user specifies a different market or currency.

## Deploy on Render

The repository includes [`render.yaml`](render.yaml), which defines the Node web service, its start command, health check, and production settings. The `GROQ_API_KEY` value is requested as a Render secret rather than stored in the repository.

1. Push the project to GitHub and connect that repository to Render.
2. In Render, create a **Blueprint** from the repository and select the `main` branch.
3. When prompted, enter the Groq key for `GROQ_API_KEY` in Render's secret field. Do not add it to GitHub or `render.yaml`.
4. Apply the Blueprint and wait for the service's deploy to show **Live**.
5. Open the service's `onrender.com` URL. Its health endpoint is `<your-render-url>/health`.

Render is connected to the `main` branch. New commits pushed to that branch should deploy automatically unless auto-deploy has been disabled in the Render dashboard. To update the app after editing locally:

```powershell
git add -A
git commit -m "Describe the change"
git push origin main
```

After pushing, check **Deploys** in the Render dashboard and wait for the newest commit to become **Live**. If you edit a file directly on GitHub, commit the change to `main` to trigger the deploy. Changes to `render.yaml` update the Blueprint configuration; review any configuration or cost changes Render shows before applying them.

The current Blueprint uses Render's free web-service plan. Free services sleep after 15 minutes without traffic and can take about a minute to wake on the next visit. This is suitable for demos and student projects, but not for apps that need uninterrupted availability. See [Render's free service limits](https://render.com/docs/free).

## Project structure

```text
public/
  index.html       Accessible app structure and page content
  css/
    base.css       Layout, shared components, and design tokens
    chat.css       Welcome screen, messages, cards, and responsive styles
    theme.css      Dark theme overrides
  js/
    app.js         Chat interactions, request handling, and Markdown rendering
src/
  groq.js          Ani's instructions, request validation, and Groq API client
server.js          Static file server, chat API, security headers, and health check
render.yaml        Render Blueprint for deployment
.env.example       Local environment variable template
```

## Safety and limitations

- Keep `GROQ_API_KEY` in `.env` locally and in Render's environment settings in production.
- The server limits message size, chat history, and request frequency. It also applies same-origin checks and security headers.
- Product research and prices depend on external search results and retailer pages. Source availability and accuracy can vary; verify details before purchase.
- Render's free service can sleep when idle. Chat history is not saved between page sessions.

## Troubleshooting

- **Ani says the server is missing a key:** set `GROQ_API_KEY` in local `.env`, or in the Render service's environment settings, then restart or redeploy.
- **Ani cannot reach Groq:** check the Render service logs and confirm that the Groq key is valid and the configured model is available to the key.
- **The first page load is slow after a break:** the free Render service may be waking from sleep. Wait for it to start, then reload.
- **The app does not show your latest code:** check that the changes were committed to `main`, pushed to GitHub, and the latest Render deploy is marked **Live**.

## Credits

Created by **Anish Tamboli** as a student project. Ani is the shopping assistant persona; SmartShop AI is the app.
