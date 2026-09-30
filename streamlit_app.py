"""SmartShop AI, a Streamlit powered shopping assistant."""

from __future__ import annotations

import os
import re
from pathlib import Path
from time import monotonic

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
    defaults = {
        "messages": [],
        "theme": "light",
        "composer_input": "",
        "pending_message": "",
        "request_timestamps": [],
    }
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
    st.session_state.composer_input = prompt


def queue_message() -> None:
    """Queue the composer text and clear it before the app reruns."""
    st.session_state.pending_message = st.session_state.composer_input.strip()
    st.session_state.composer_input = ""


def render_product_table(answer: str, key_prefix: str) -> None:
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
        if not render_heading_products(answer, key_prefix):
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
        with st.container(border=True, key=f"{key_prefix}_product_{number}"):
            st.markdown(f"### {number:02d} · {row[0] or 'Product'}")
            if len(row) > 1 and row[1].strip():
                st.markdown(f"**Approx. price**  \n{row[1]}")
            for label, value in zip(header[2:], row[2:]):
                if value.strip():
                    st.markdown(f"**{label.strip()}**  \n{value}")

    if after:
        render_follow_up(after, key_prefix)


def _heading_title(line: str) -> str | None:
    match = re.match(r"^\s*#{2,3}\s+(.+?)\s*$", line)
    return match.group(1) if match else None


def _product_field(line: str) -> tuple[str | None, str]:
    """Read a bold product label and any value placed on the same line."""
    match = re.match(r"^\s*\*\*(.+?)\*\*(.*)$", line.strip())
    if not match:
        return None, ""

    label = match.group(1).strip().rstrip("*:").strip().lower()
    remainder = match.group(2).strip().lstrip("*").strip()
    remainder = re.sub(r"^[:–—-]\s*", "", remainder)
    if re.fullmatch(r"(?:approx(?:imate)?\.?\s*)?price", label):
        return "price", remainder
    if re.match(r"^(?:why it fits|why it works|good for|best for)", label):
        return "fit", remainder
    if re.match(r"^(?:main\s+)?trade[- ]?off|^(?:watch out|downside)", label):
        return "tradeoff", remainder
    return None, ""


def _product_list_boundary(line: str) -> bool:
    return bool(
        re.match(
            r"(?i)^\s*(?:\*\*(?:final\s+)?recommendation\s*:?\*\*|"
            r"\*\*(?:in\s+simple\s+terms|plain\s+english)\s*:?\*\*|"
            r"\*?prices?\s+(?:may|can|vary|are)\b)",
            line,
        )
    )


def render_heading_products(answer: str, key_prefix: str) -> bool:
    """Handle older heading-and-label answers as cards when no table is returned."""
    lines = answer.splitlines()
    heading_positions = [
        index for index, line in enumerate(lines) if _heading_title(line) is not None
    ]
    sections = []
    for heading_index, start in enumerate(heading_positions):
        end = heading_positions[heading_index + 1] if heading_index + 1 < len(heading_positions) else len(lines)
        body_end = next(
            (index for index in range(start + 1, end) if _product_list_boundary(lines[index])),
            end,
        )
        section_lines = lines[start + 1 : body_end]
        labels = {_product_field(line)[0] for line in section_lines}
        is_product = "price" in labels and bool({"fit", "tradeoff"} & labels)
        sections.append((start, body_end, _heading_title(lines[start]), section_lines, is_product))

    products = [section for section in sections if section[4]]
    if not products:
        return False

    rendered_through = 0
    for product_number, (start, end, title, section_lines, _) in enumerate(products, start=1):
        between = "\n".join(lines[rendered_through:start]).strip()
        if between:
            st.markdown(between, unsafe_allow_html=False)

        subtitle = ""
        values: dict[str, str] = {}
        extras = []
        index = 0
        while index < len(section_lines):
            current = section_lines[index].strip()
            if not current:
                index += 1
                continue

            field, inline_value = _product_field(current)
            if field:
                value_lines = [inline_value] if inline_value else []
                index += 1
                while index < len(section_lines) and not section_lines[index].strip():
                    index += 1
                while index < len(section_lines):
                    candidate = section_lines[index].strip()
                    if not candidate or _product_field(candidate)[0]:
                        break
                    value_lines.append(candidate)
                    index += 1
                values[field] = "\n".join(value_lines).strip()
                continue

            if not subtitle and current.startswith("**"):
                subtitle = current
            else:
                extras.append(current)
            index += 1

        with st.container(border=True, key=f"{key_prefix}_heading_product_{product_number}"):
            st.markdown(f"### {product_number:02d} · {title}")
            if subtitle:
                st.markdown(subtitle)
            if values.get("price"):
                st.markdown(f"**Approx. price**  \n{values['price']}")
            detail_labels = {"fit": "Why it fits", "tradeoff": "Main trade-off"}
            for field, label in detail_labels.items():
                if values.get(field):
                    st.markdown(f"**{label}**  \n{values[field]}")
            for extra in extras:
                st.markdown(extra, unsafe_allow_html=False)
        rendered_through = end

    after = "\n".join(lines[rendered_through:]).strip()
    if after:
        render_follow_up(after, key_prefix)
    return True


def render_follow_up(text: str, key_prefix: str) -> None:
    """Give the recommendation and plain-language summary their own visual blocks."""
    recommendation = re.search(
        r"(?im)^\s*\*\*(?:final\s+)?recommendation\s*:?\s*\*\*\s*[:–—-]?\s*",
        text,
    )
    plain = re.search(
        r"(?im)^\s*\*\*(?:in\s+simple\s+terms|plain\s+english)\s*:?\s*\*\*\s*:?\s*",
        text,
    )
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
        with st.container(border=True, key=f"{key_prefix}_answer_{kind}"):
            st.markdown(f"**{label}**")
            st.markdown(content, unsafe_allow_html=False)


def render_message(message: dict[str, object], message_index: int) -> None:
    role = str(message.get("role", "assistant"))
    key_prefix = f"history_{message_index}"
    avatar = ":material/account_circle:" if role == "user" else "✳"
    with st.chat_message(role, avatar=avatar):
        content = str(message.get("content", ""))
        if role == "assistant":
            render_product_table(content, key_prefix)
            sources = message.get("sources", [])
            if isinstance(sources, list) and sources:
                with st.expander("Research links", icon=":material/link:"):
                    for source_index, source in enumerate(sources):
                        source_url = source.get("url", "") if isinstance(source, dict) else ""
                        if isinstance(source_url, str) and source_url.startswith("https://"):
                            st.link_button(
                                str(source.get("title", "Source")),
                                source_url,
                                icon=":material/open_in_new:",
                                width="stretch",
                                key=f"{key_prefix}_source_{source_index}",
                            )
        else:
            st.markdown(content)


def set_theme(theme: str) -> None:
    st.session_state.theme = theme


def request_retry_after() -> int:
    """Enforce a soft 12-request quota per visitor session over ten minutes."""
    now = monotonic()
    recent = [
        timestamp
        for timestamp in st.session_state.request_timestamps
        if now - timestamp < 600
    ]
    if len(recent) >= 12:
        st.session_state.request_timestamps = recent
        return max(1, int(600 - (now - recent[0]) + 0.999))

    recent.append(now)
    st.session_state.request_timestamps = recent
    return 0


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
    for message_index, item in enumerate(st.session_state.messages):
        render_message(item, message_index)

with st.container(key="composer"):
    st.markdown(
        '<div class="composer-hint">Pick an idea to edit it before sending · Check prices and availability before you buy</div>',
        unsafe_allow_html=True,
    )
    input_column, send_column = st.columns([12, 1], vertical_alignment="bottom", gap="small")
    with input_column:
        st.text_area(
            "Message Ani",
            placeholder="Tell Ani what you’re shopping for…",
            key="composer_input",
            max_chars=1400,
            height=82,
            label_visibility="collapsed",
        )
    with send_column:
        st.button(
            ":material/arrow_upward:",
            key="send_message",
            help="Send message to Ani",
            type="primary",
            width="stretch",
            on_click=queue_message,
        )

prompt = st.session_state.pop("pending_message", "")

if prompt and prompt.strip():
    user_message = {"role": "user", "content": prompt.strip()}
    st.session_state.messages.append(user_message)
    with st.chat_message("user", avatar=":material/account_circle:"):
        st.markdown(user_message["content"])

    with st.chat_message("assistant", avatar="✳"):
        new_message_key = f"new_{len(st.session_state.messages)}"
        wait_seconds = request_retry_after()
        if wait_seconds:
            wait_minutes = max(1, (wait_seconds + 59) // 60)
            error_message = (
                f"Ani has reached the short-term request limit for this connection. "
                f"Please wait about {wait_minutes} minute(s) and try again."
            )
            st.warning(error_message)
            st.session_state.messages.append(
                {"role": "assistant", "content": error_message, "sources": []}
            )
        else:
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
                render_product_table(assistant_message["content"], new_message_key)
                if assistant_message["sources"]:
                    with st.expander("Research links", icon=":material/link:"):
                        for source_index, source in enumerate(assistant_message["sources"]):
                            st.link_button(
                                source["title"],
                                source["url"],
                                icon=":material/open_in_new:",
                                width="stretch",
                                key=f"{new_message_key}_source_{source_index}",
                            )

