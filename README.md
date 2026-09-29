# SmartShop AI

SmartShop is a responsive shopping assistant. Ani uses Groq’s OpenAI GPT-OSS 120B model and browser search to research products, compare tradeoffs, and give one recommendation.

## Project layout

```text
public/
  css/       Responsive layout, chat components, and color theme
  js/        Browser-side chat and theme behavior
  index.html Accessible page structure
src/
  groq.js    Prompt, input limits, and Groq API client
server.js   Static file server, chat route, health check, and request limits
render.yaml Render deployment blueprint
```

## Run locally

Requirements: Node.js 20.12 or newer.

1. Copy `.env.example` to `.env`.
2. Put your Groq API key in `.env` as `GROQ_API_KEY=...`.
3. Start the app from this folder:

   ```powershell
   npm.cmd start
   ```

4. Open <http://localhost:3000>.

Run the source syntax checks with `npm.cmd run check`.

Keep `.env` private. It is ignored by Git; do not paste the key into `render.yaml`, source files, screenshots, or a public repository.

## Deploy publicly with Render

The repository includes a Render Blueprint. It starts the Node web service, sets `/health` as its health check, and asks for the Groq key as a dashboard secret.

1. Create a Git repository for this project and push the project files. Keep `.env` out of Git; `.gitignore` already excludes it.
2. Sign in to Render, connect the repository, and choose **New → Blueprint**.
3. Select the repository containing `render.yaml` and create the service.
4. When Render asks for `GROQ_API_KEY`, add the key in the dashboard’s secret field. Do not put it in the Blueprint.
5. Wait for the health check and deployment to finish. Open the public `*.onrender.com` URL on desktop or mobile.

The Blueprint uses Render’s Free web-service plan to keep this suitable for a student project. Free services sleep after 15 minutes without traffic; the first visit after sleep can take about a minute to wake the app. Upgrade the service plan if it needs to stay responsive at all times. See [Render’s free-service limits](https://render.com/docs/free) and [Blueprint configuration](https://render.com/docs/blueprint-spec).

## Public-service safeguards

- The Groq key is read only by the Node server and is never sent to the browser.
- The chat endpoint accepts same-origin JSON requests, limits request size and message history, and allows up to 12 chat requests per client per 10 minutes.
- Ani’s replies are capped at 900 completion tokens by default (configurable up to 1,200).
- Conversations are kept in the current page only. The app does not have accounts or a database.
- The free hosting plan is intended for a demo, not a production service with an uptime guarantee.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GROQ_API_KEY` | — | Required server-side Groq credential |
| `GROQ_MODEL` | `openai/gpt-oss-120b` | Groq model for chat and browser search |
| `GROQ_MAX_COMPLETION_TOKENS` | `900` | Response budget, capped at 1,200 |
| `PORT` | `3000` | Local server port; the host provides this in deployment |

Unspecified budgets default to India and INR (₹), so `30k` means ₹30,000 unless the shopper says otherwise. Ani is instructed to answer shopping-related requests, ask concise follow-ups when needed, and link product sources. Prices and availability can change, so check the retailer before buying.
