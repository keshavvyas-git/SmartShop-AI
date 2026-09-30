"""SmartShop AI, a Streamlit powered shopping assistant."""

from __future__ import annotations

import os
import re
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from smartshop.groq_client import AssistantError, get_assistant_reply


ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")
SUGGESTIONS = [
    (
        "desktop_windows",
        "Help me build a PC",
        "Parts matched to my needs",
        "Help me plan a desktop PC build. Ask me my budget and what I’ll use it for before recommending parts.",
    ),
    (
        "code",
        "Laptop for coding",
        "Under ₹30,000",
        "I want a laptop for coding under ₹30,000 in India. Please focus on practical options for programming.",
    ),
    (
        "photo_camera",
        "Phone for vlogging",
        "Camera-first recommendations",
        "I want to buy a phone for vlogging. Find phones with the best camera for my budget, and ask me my budget first.",
    ),
    (
        "sports_esports",
        "Gaming laptop for GTA VI",
        "Specs and suitable options",
        "I’m looking for a gaming laptop for GTA VI in India. Tell me the minimum specs to target and recommend suitable options.",
    ),
]


def init_state() -> None:
    defaults = {"messages": [], "theme": "light", "chat_input": ""}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def load_styles() -> None:
    css = (ROOT / "assets" / "smartshop.css").read_text(encoding="utf-8")
    st.html(f"<style>{css}</style>")


def show_welcome() -> None:
    st.html(
        """<section class="welcome">
          <div class="welcome-orbit" aria-hidden="true">
            <div class="orbit-ring ring-a"></div><div class="orbit-ring ring-b"></div>
            <div class="ani-face"><span class="ani-glint">✦</span>
              <div class="ani-eyes"><i></i><i></i></div><div class="ani-smile"></div>
            </div>
            <span class="float-star star-a">✳</span><span class="float-star star-b">✧</span>
            <span class="float-dot dot-a"></span><span class="float-dot dot-b"></span>
          </div>
          <div class="eyebrow"><span class="eyebrow-dot"></span> YOUR THOUGHTFUL SHOPPING SIDEKICK</div>
          <h1>Hey, I’m Ani<span>!</span><br><em>Let’s find your just right.</em></h1>
          <p class="welcome-copy">Tell me what you’re shopping for and what matters most.
          I’ll research the options and make the trade-offs easy to understand.</p>
        </section>"""
    )
    st.markdown('<div class="suggestion-label">WHAT ARE YOU SHOPPING FOR?</div>', unsafe_allow_html=True)

    first_row = st.columns(2, gap="small")
    second_row = st.columns(2, gap="small")
    for index, (icon, title, subtitle, prompt) in enumerate(SUGGESTIONS):
        column = first_row[index] if index < 2 else second_row[index - 2]
        with column:
            st.button(
                f":material/{icon}:  **{title}** · {subtitle}",
                key=f"suggestion_{index}",
                type="secondary",
                width="stretch",
                on_click=fill_suggestion,
                args=(prompt,),
            )

    st.markdown(
        '<div class="trust-note"><span>✳</span> Crafted with care by Anish Tamboli</div>',
        unsafe_allow_html=True,
    )


def fill_suggestion(prompt: str) -> None:
    """Put a suggestion in the composer; the user still chooses when to send."""
    st.session_state.chat_input = prompt


def render_product_table(answer: str) -> None:
    """Render a Markdown product comparison as readable, phone-friendly cards."""
    lines = answer.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if "|" in line
            and index + 1 < len(lines)
            and re.fullmatch(
                r"\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*",
                lines[index + 1],
            )
        ),
        None,
    )
    if header_index is None:
        st.markdown(answer, unsafe_allow_html=False)
        return

    def cells(line: str) -> list[str]:
        return [part.strip() for part in line.strip().strip("|").split("|")]

    header = cells(lines[header_index])
    rows: list[list[str]] = []
    end = header_index + 2
    while end < len(lines) and "|" in lines[end]:
        values = cells(lines[end])
        if any(values):
            rows.append(values)
        end += 1

    before = "\n".join(lines[:header_index]).strip()
    after = "\n".join(lines[end:]).strip()
    if before:
        st.markdown(before, unsafe_allow_html=False)

    for number, row in enumerate(rows, start=1):
        row += [""] * (len(header) - len(row))
        with st.container(border=True, key=f"product_{number}"):
            st.markdown(f"### {number:02d} · {row[0] or 'Product'}")
            if len(row) > 1 and row[1].strip():
                st.markdown(f"**Approx. price**  \n{row[1]}")
            for label, value in zip(header[2:], row[2:]):
                if value.strip():
                    st.markdown(f"**{label.strip()}**  \n{value}")

    if after:
        render_follow_up(after)


def render_follow_up(text: str) -> None:
    """Give the recommendation and plain-language summary their own visual blocks."""
    recommendation = re.search(
        r"(?im)^\s*\*\*(?:final\s+)?recommendation\s*\*\*\s*[:–—-]?\s*", text
    )
    plain = re.search(r"(?im)^\s*\*\*(?:in\s+simple\s+terms|plain\s+english)\s*\*\*\s*:?\s*", text)
    cuts = sorted([match.start() for match in (recommendation, plain) if match])
    if not cuts:
        st.markdown(text, unsafe_allow_html=False)
        return

    preamble = text[: cuts[0]].strip()
    if preamble:
        st.markdown(preamble, unsafe_allow_html=False)
    for match, kind in ((recommendation, "recommendation"), (plain, "plain")):
        if not match:
            continue
        next_cut = min((position for position in cuts if position > match.start()), default=len(text))
        content = text[match.end() : next_cut].strip()
        label = "Ani’s recommendation" if kind == "recommendation" else "In simple terms"
        with st.container(border=True, key=f"answer_{kind}"):
            st.markdown(f"**{label}**")
            st.markdown(content, unsafe_allow_html=False)


def render_message(message: dict[str, object]) -> None:
    role = str(message.get("role", "assistant"))
    avatar = "account_circle" if role == "user" else "✳"
    with st.chat_message(role, avatar=avatar):
        content = str(message.get("content", ""))
        if role == "assistant":
            render_product_table(content)
            sources = message.get("sources", [])
            if isinstance(sources, list) and sources:
                with st.expander("Research links", icon=":material/link:"):
                    for source in sources:
                        source_url = source.get("url", "") if isinstance(source, dict) else ""
                        if isinstance(source_url, str) and source_url.startswith("https://"):
                            st.link_button(
                                str(source.get("title", "Source")),
                                source_url,
                                icon=":material/open_in_new:",
                                width="stretch",
                            )
        else:
            st.markdown(content)


def set_theme(theme: str) -> None:
    st.session_state.theme = theme


st.set_page_config(
    page_title="SmartShop AI — thoughtful shopping with Ani",
    page_icon="✳",
    layout="wide",
    initial_sidebar_state="collapsed",
)
init_state()
load_styles()
st.html(f'<div class="theme-state" data-theme="{st.session_state.theme}"></div>')

brand, status, theme_column = st.columns([5, 2, 1], vertical_alignment="center")
with brand:
    st.markdown(
        '<div class="brand"><span class="brand-mark">✳</span> SmartShop<span class="brand-suffix">.ai</span>'
        '<span class="brand-divider">·</span><span class="brand-caption">Your shopping space</span></div>',
        unsafe_allow_html=True,
    )
with status:
    st.markdown('<div class="research-status">● &nbsp;Live product research</div>', unsafe_allow_html=True)
with theme_column:
    next_theme = "dark" if st.session_state.theme == "light" else "light"
    st.button(
        "☾" if next_theme == "dark" else "☀",
        key="theme_toggle",
        help=f"Switch to {next_theme} mode",
        on_click=set_theme,
        args=(next_theme,),
        type="secondary",
    )

if not st.session_state.messages:
    show_welcome()
else:
    for item in st.session_state.messages:
        render_message(item)

st.markdown(
    '<div class="composer-hint">Pick an idea to edit it before sending · Check prices and availability before you buy</div>',
    unsafe_allow_html=True,
)
prompt = st.chat_input(
    "Tell Ani what you’re shopping for…",
    key="chat_input",
    max_chars=1400,
    submit_mode="disable",
)

if prompt and prompt.strip():
    user_message = {"role": "user", "content": prompt.strip()}
    st.session_state.messages.append(user_message)
    with st.chat_message("user", avatar="account_circle"):
        st.markdown(user_message["content"])

    with st.chat_message("assistant", avatar="✳"):
        with st.status(":shimmer[Searching trusted product sources]", type="compact"):
            assistant_message = None
            try:
                result = get_assistant_reply(st.session_state.messages[-6:])
            except AssistantError as error:
                st.error(str(error))
                st.session_state.messages.append(
                    {"role": "assistant", "content": str(error), "sources": []}
                )
            else:
                assistant_message = {
                    "role": "assistant",
                    "content": result["answer"],
                    "sources": result["sources"],
                }
                st.session_state.messages.append(assistant_message)
        if assistant_message:
            render_product_table(assistant_message["content"])
            if assistant_message["sources"]:
                with st.expander("Research links", icon=":material/link:"):
                    for source in assistant_message["sources"]:
                        st.link_button(
                            source["title"], source["url"],
                            icon=":material/open_in_new:", width="stretch"
                        )

