# SmartShop AI

SmartShop AI is a responsive, Streamlit shopping assistant featuring **Ani**. Describe what you want to buy, your budget, and what matters most. Ani researches current options, compares trade-offs, and gives a practical recommendation in everyday language.

**Live demo:** [SmartShop AI on Render](https://smartshop-ai-995v.onrender.com)

## What it does

- Researches shopping questions with Groq's browser search tool.
- Uses India and INR as the default market.
- Compares up to three products, then explains one recommendation in simple language.
- Prefers trusted sources: manufacturers, established testing publications, government/standards sources, and well-known authorized retailers.
- Keeps the API key on the server and out of the browser.
- Offers editable prompt suggestions, per-session chat history, and light/dark themes.
- Uses the original sunflower palette and animated Ani mascot, with a responsive layout.

Prices and availability change. Follow the linked sources and confirm the exact model and current price before buying. Ani is an AI assistant; verify important details with the retailer or manufacturer.

## Tech stack

| Area | Technology |
| --- | --- |
| App and UI | Python, Streamlit |
| Styling and animation | Streamlit theme plus responsive CSS and a small static HTML mascot |
| AI | Groq Chat Completions API, `openai/gpt-oss-120b` by default |
| Product research | Groq `browser_search` tool |
| Hosting | Render web service managed through `render.yaml` |

### Request flow

1. Streamlit receives a chat message and keeps the conversation in that visitor's session state.
2. The Python server sends the recent messages to Groq using `GROQ_API_KEY` from the server environment.
3. Ani returns a concise comparison; Streamlit displays product cards, source links, the recommendation, and the plain-language explanation.

There are no user accounts or database. Chat history is kept only in the current Streamlit session.

## Run locally

### Requirements

- Python 3.10 or newer.
- A Groq API key with access to the configured model and browser search.

### Windows PowerShell

```powershell
git clone https://github.com/keshavvyas-git/SmartShop-AI.git
cd SmartShop-AI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set your key:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
GROQ_MAX_COMPLETION_TOKENS=900
```

Then run:

```powershell
python -m streamlit run streamlit_app.py
```

Open the local URL shown in the terminal (usually <http://localhost:8501>). Stop the server with **Ctrl+C**. The `.env` file is ignored by Git; never commit your real key.

You can also configure these values as environment variables or through Streamlit secrets. In deployment, use the host's secret settings rather than committing credentials.

## Deploy on Streamlit Community Cloud

The app entry point and `requirements.txt` are in the repository root, with Streamlit settings in `.streamlit/config.toml`. Community Cloud deploys from GitHub and installs packages listed in `requirements.txt`.

1. Sign in at [Streamlit Community Cloud](https://share.streamlit.io/) and connect the GitHub account that can access this repository.
2. Select **Create app**, then choose **Yup, I have an app**.
3. Set the repository to `keshavvyas-git/SmartShop-AI`, branch to `streamlit-cloud`, and app file to `streamlit_app.py`.
4. Open **Advanced settings** and add these values in the **Secrets** box, replacing the API key with your own:

   ```toml
   GROQ_API_KEY = "your_groq_api_key_here"
   GROQ_MODEL = "openai/gpt-oss-120b"
   GROQ_MAX_COMPLETION_TOKENS = "900"
   ```

5. Click **Deploy** and wait for the app to finish building. Choose Python 3.12 in Advanced settings if a version selector is shown.

The Groq key is read from `st.secrets` on Community Cloud and from environment variables or local `.env` elsewhere. Do not put the real key in GitHub. Community Cloud may take a few minutes to build the first deployment. See Streamlit's [deployment guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy) and [secrets guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

## Deploy on Render

The root [`render.yaml`](render.yaml) configures the existing web service to use Python and start Streamlit. Render supports Python as a native Blueprint runtime; its Blueprint reads the build and start commands from this file.

To move the existing Render service from Node to Streamlit:

1. Commit and push the migration to the connected GitHub `main` branch.
2. In Render, sync or review the Blueprint changes so the service runtime changes from Node to Python.
3. Keep the existing `GROQ_API_KEY` secret in the service environment. The YAML marks it `sync: false` so the key is not stored in Git.
4. Apply the Blueprint update and wait for the Python build and deployment to finish.
5. Open the service URL and try a shopping request. Check the Render logs if the build or Groq request fails.

Render deploys commits pushed to the connected branch when auto-deploy is enabled. Free web services may sleep while idle and take time to wake on a new visit. See [Render's free service limits](https://render.com/docs/free).

## Project structure

```text
streamlit_app.py       Streamlit page, chat UI, suggestions, and session state
smartshop/
  groq_client.py       Groq API client, prompt, validation, and source extraction
assets/
  smartshop.css        Responsive sunflower theme and Ani animation
.streamlit/
  config.toml          Streamlit theme and server settings
requirements.txt       Python dependencies
render.yaml            Render Python Blueprint
.env.example           Local configuration template
```

## Screenshots

Suggested captures for `docs/screenshots/`:

| Filename | Capture |
| --- | --- |
| `welcome-desktop.png` | Welcome screen with Ani and editable prompts |
| `shortlist-desktop.png` | Product cards, recommendation, and simple explanation |
| `shortlist-mobile.png` | Same shortlist on a phone-sized screen |
| `dark-mode.png` | Chat and product cards in dark mode |

Embed a saved screenshot with, for example:

```markdown
![SmartShop AI product shortlist on mobile](docs/screenshots/shortlist-mobile.png)
```

## Configuration

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `GROQ_API_KEY` | Yes | — | Secret credential used by the server for Groq requests. |
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` | Model used for the assistant and product research. |
| `GROQ_MAX_COMPLETION_TOKENS` | No | `900` | Response token limit, capped at 1,200. |

## Limitations and troubleshooting

- **Missing API key:** set `GROQ_API_KEY` in local `.env` or the Render service's environment settings.
- **Groq request fails:** check the Render logs, key validity, model access, and Groq rate limits.
- **First visit is slow:** the free Render service may be waking from sleep.
- **Chat history:** conversation state is temporary and is not saved after the session ends.
- **Research:** search coverage varies; verify product details and prices in the source links.

## Credits

Created by **Anish Tamboli** as a student project. Ani is the assistant persona; SmartShop AI is the app.
