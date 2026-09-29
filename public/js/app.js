(() => {
  const elements = {
    form: document.querySelector('#chatForm'),
    input: document.querySelector('#chatInput'),
    sendButton: document.querySelector('#sendButton'),
    welcome: document.querySelector('#welcome'),
    messages: document.querySelector('#messages'),
    toast: document.querySelector('#toast'),
    themeToggle: document.querySelector('#themeToggle'),
    pageTitle: document.querySelector('.breadcrumb strong'),
  };

  const state = {
    history: [],
    isWaiting: false,
    title: 'New conversation',
    toastTimer: null,
  };

  const MAX_INPUT_LENGTH = 1400;
  const THEME_STORAGE_KEY = 'smartshop.theme';

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    })[character]);
  }

  function renderInlineMarkdown(value, sourcesById = new Map()) {
    let html = escapeHtml(value);

    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, label, url) => {
      const safeUrl = escapeHtml(url.replace(/&amp;/g, '&'));
      return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${label}</a>`;
    });

    html = html.replace(/[【〖](\d+)(?:†L[\d-]+)?[】〗]/g, (citation, id) => {
      const source = sourcesById.get(id);
      if (!source) return `<span class="source-reference" title="Source ${id}">${id}</span>`;
      return `<a class="source-reference" href="${escapeHtml(source.url)}" target="_blank" rel="noopener noreferrer" title="${escapeHtml(source.title)}" aria-label="Open source ${id}: ${escapeHtml(source.title)}">${id}</a>`;
    });

    html = html.replace(/\\([^\w\s])/g, '$1');

    return html
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>');
  }

  function renderMarkdown(markdown, sources = []) {
    const html = [];
    const sourcesById = new Map(sources.map((source) => [String(source.id), source]));
    const inline = (value) => renderInlineMarkdown(value, sourcesById);
    let listType = null;
    let paragraphLines = [];
    const lines = markdown.split(/\r?\n/);

    function splitTableRow(line) {
      return line.trim().replace(/\\\|/g, '|').replace(/^\|/, '').replace(/\|$/, '')
        .split('|').map((cell) => cell.trim());
    }

    function isTableDivider(line) {
      const cells = splitTableRow(line);
      return cells.length > 1 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
    }

    function renderTable(headers, rows) {
      const products = rows.map((row) => {
        const cells = headers.map((_, index) => row[index] || '—');
        const title = inline(cells[0] || 'Product');
        const price = cells[1] ? inline(cells[1]) : '';
        const details = headers.slice(2).map((header, index) => `
          <div class="product-detail"><span>${inline(header)}</span><p>${inline(cells[index + 2] || '—')}</p></div>`).join('');
        return `<article class="product-card"><div class="product-card-heading"><h3>${title}</h3>${price ? `<span class="product-price">${price}</span>` : ''}</div>${details ? `<div class="product-details">${details}</div>` : ''}</article>`;
      }).join('');
      return `<section class="product-shortlist" aria-label="Product shortlist">${products}</section>`;
    }

    function closeList() {
      if (listType) html.push(listType === 'ul' ? '</ul>' : '</ol>');
      listType = null;
    }

    function flushParagraph() {
      if (!paragraphLines.length) return;
      const paragraph = paragraphLines.join(' ').trim();
      paragraphLines = [];

      if (/^\*\*(recommendation|final recommendation|our pick):?\*\*/i.test(paragraph)) {
        html.push(`<aside class="recommendation-card">${inline(paragraph)}</aside>`);
      } else if (/^\*\*(in simple terms|plain english):?\*\*/i.test(paragraph)) {
        html.push(`<aside class="plain-explanation">${inline(paragraph)}</aside>`);
      } else {
        html.push(`<p>${inline(paragraph)}</p>`);
      }
    }

    for (let index = 0; index < lines.length; index += 1) {
      const rawLine = lines[index];
      const line = rawLine.trim();
      if (!line) {
        closeList();
        flushParagraph();
        continue;
      }

      // Turn comparison tables into readable product cards, including tables
      // emitted with escaped pipes by some model responses.
      if (line.includes('|') && index + 1 < lines.length && isTableDivider(lines[index + 1].trim())) {
        flushParagraph();
        closeList();
        const headers = splitTableRow(line);
        const rows = [];
        index += 2;
        while (index < lines.length && lines[index].trim().includes('|')) {
          rows.push(splitTableRow(lines[index]));
          index += 1;
        }
        index -= 1;
        if (rows.length) html.push(renderTable(headers, rows));
        continue;
      }

      const heading = line.match(/^(#{1,3})\s+(.+)$/);
      const unorderedItem = line.match(/^[-*]\s+(.+)$/);
      const orderedItem = line.match(/^\d+[.)]\s+(.+)$/);

      if (heading) {
        flushParagraph();
        closeList();
        const level = heading[1].length === 1 ? 2 : 3;
        html.push(`<h${level}>${inline(heading[2])}</h${level}>`);
        continue;
      }

      if (unorderedItem || orderedItem) {
        flushParagraph();
        const nextListType = unorderedItem ? 'ul' : 'ol';
        if (listType !== nextListType) {
          closeList();
          listType = nextListType;
          html.push(`<${listType}>`);
        }
        const content = (unorderedItem || orderedItem)[1];
        html.push(`<li>${inline(content)}</li>`);
        continue;
      }

      closeList();
      paragraphLines.push(line);
    }

    closeList();
    flushParagraph();
    return formatProductSections(html.join(''));
  }

  function fieldTypeFromLabel(value) {
    const label = value.replace(/[\\*:]/g, '').trim().toLowerCase();
    if (/^(?:approx(?:imate)?\.?\s*)?price$/.test(label)) return 'price';
    if (/^(?:why it fits|why it works|good for|best for)/.test(label)) return 'fit';
    if (/^(?:main\s+)?trade[- ]?off|^(?:watch out|downside)/.test(label)) return 'tradeoff';
    return null;
  }

  function standaloneStrongText(node) {
    if (node.nodeType !== Node.ELEMENT_NODE || node.tagName !== 'P') return null;
    const strong = node.firstElementChild;
    if (!strong || strong.tagName !== 'STRONG' || node.children.length !== 1) return null;
    return strong.textContent.trim();
  }

  function isProductBoundary(node) {
    if (node.nodeType !== Node.ELEMENT_NODE) return false;
    if (node.matches('aside.recommendation-card, aside.plain-explanation')) return true;
    const text = node.textContent.trim();
    const strongText = standaloneStrongText(node) || '';
    return /^(?:prices?\s+(?:may|can|are)|\*?prices?\b)/i.test(text)
      || /^(?:recommendation|final recommendation|our pick|in simple terms|plain english)\b/i.test(strongText);
  }

  function isProductSection(nodes) {
    const labels = nodes.map(standaloneStrongText).filter(Boolean);
    const hasPrice = labels.some((label) => fieldTypeFromLabel(label) === 'price');
    const hasFit = labels.some((label) => fieldTypeFromLabel(label) === 'fit');
    const hasTradeoff = labels.some((label) => fieldTypeFromLabel(label) === 'tradeoff');
    return hasPrice && (hasFit || hasTradeoff) || hasFit && hasTradeoff;
  }

  function renderProductSection(titleNode, bodyNodes) {
    let subtitle = '';
    let price = '';
    const details = [];
    const extras = [];

    for (let index = 0; index < bodyNodes.length; index += 1) {
      const node = bodyNodes[index];
      const strongText = standaloneStrongText(node);
      const fieldType = strongText ? fieldTypeFromLabel(strongText) : null;

      if (fieldType) {
        let valueNode = bodyNodes[index + 1];
        while (valueNode?.nodeType === Node.TEXT_NODE && !valueNode.textContent.trim()) {
          index += 1;
          valueNode = bodyNodes[index + 1];
        }
        const value = valueNode?.nodeType === Node.ELEMENT_NODE && valueNode.tagName === 'P'
          && !standaloneStrongText(valueNode)
          ? valueNode.innerHTML
          : '';
        if (value) index += 1;

        if (fieldType === 'price') price = value;
        else details.push({
          label: fieldType === 'fit' ? 'Why it fits' : 'Main trade-off',
          value,
        });
        continue;
      }

      if (!subtitle && strongText) {
        subtitle = node.innerHTML;
      } else {
        const markup = node.outerHTML || escapeHtml(node.textContent);
        if (markup.trim()) extras.push(markup);
      }
    }

    const detailMarkup = details.map(({ label, value }) => `
      <div class="product-detail"><span>${label}</span><p>${value}</p></div>`).join('');
    const subtitleMarkup = subtitle ? `<p class="product-specs">${subtitle}</p>` : '';
    const priceMarkup = price
      ? `<div class="product-price-wrap"><span>Approx. price</span><strong class="product-price">${price}</strong></div>`
      : '';

    return `<article class="product-card product-result-card">
      <div class="product-card-heading"><h3>${titleNode.innerHTML}</h3></div>
      ${subtitleMarkup}${priceMarkup}${detailMarkup ? `<div class="product-details">${detailMarkup}</div>` : ''}${extras.join('')}
    </article>`;
  }

  function formatProductSections(markup) {
    const parsed = document.createElement('div');
    parsed.innerHTML = markup;
    const nodes = Array.from(parsed.childNodes);
    const output = document.createElement('div');
    let productCards = [];

    function flushProductCards() {
      if (!productCards.length) return;
      const section = document.createElement('section');
      section.className = 'product-shortlist';
      section.setAttribute('aria-label', 'Product shortlist');
      section.innerHTML = productCards.join('');
      output.append(section);
      productCards = [];
    }

    function appendNode(node) {
      flushProductCards();
      if (node.nodeType === Node.TEXT_NODE && !node.textContent.trim()) return;
      output.append(node.cloneNode(true));
    }

    for (let index = 0; index < nodes.length;) {
      const node = nodes[index];
      if (node.nodeType !== Node.ELEMENT_NODE || node.tagName !== 'H3') {
        appendNode(node);
        index += 1;
        continue;
      }

      let end = index + 1;
      while (end < nodes.length) {
        const next = nodes[end];
        if (next.nodeType === Node.ELEMENT_NODE
          && (next.tagName === 'H3' || isProductBoundary(next))) break;
        end += 1;
      }
      const bodyNodes = nodes.slice(index + 1, end);

      if (isProductSection(bodyNodes)) {
        productCards.push(renderProductSection(node, bodyNodes));
      } else {
        flushProductCards();
        output.append(node.cloneNode(true));
        bodyNodes.forEach((bodyNode) => {
          if (!(bodyNode.nodeType === Node.TEXT_NODE && !bodyNode.textContent.trim())) {
            output.append(bodyNode.cloneNode(true));
          }
        });
      }
      index = end;
    }

    flushProductCards();
    return output.innerHTML;
  }

  function showToast(message) {
    elements.toast.textContent = message;
    elements.toast.classList.add('show');
    window.clearTimeout(state.toastTimer);
    state.toastTimer = window.setTimeout(() => {
      elements.toast.classList.remove('show');
    }, 2600);
  }

  function addMessage(role, content, { markdown = false, typing = false } = {}) {
    const message = document.createElement('div');
    message.className = `message ${role}`;

    if (role === 'user') {
      message.innerHTML = `<div class="bubble">${escapeHtml(content)}</div>`;
    } else {
      const body = markdown ? renderMarkdown(content) : escapeHtml(content);
      message.innerHTML = `
        <div class="message-avatar" aria-hidden="true">✳</div>
        <div class="bubble"><div class="answer-content">${body}</div></div>
      `;

      if (typing) {
        const indicator = document.createElement('div');
        indicator.className = 'typing';
        indicator.setAttribute('role', 'status');
        indicator.setAttribute('aria-label', 'Ani is researching');
        for (let index = 0; index < 3; index += 1) {
          indicator.append(document.createElement('i'));
        }
        message.querySelector('.answer-content').replaceChildren(indicator);
      }
    }

    elements.messages.append(message);
    message.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    return message;
  }

  function setInputValue(value) {
    elements.input.value = value;
    elements.input.style.height = 'auto';
    elements.input.style.height = `${Math.min(elements.input.scrollHeight, 120)}px`;
    elements.sendButton.disabled = state.isWaiting || !value.trim();
    elements.input.focus();
  }

  function retryButton(query, userMessage, assistantMessage) {
    const button = document.createElement('button');
    button.className = 'retry-button';
    button.type = 'button';
    button.textContent = '↻ Try again';
    button.addEventListener('click', () => {
      userMessage.remove();
      assistantMessage.remove();
      setInputValue(query);
      elements.form.requestSubmit();
    });
    return button;
  }

  async function askAni(query) {
    if (state.isWaiting) return;

    state.isWaiting = true;
    if (!state.history.some((message) => message.role === 'user')) {
      state.title = query.length > 36 ? `${query.slice(0, 33)}…` : query;
    }
    elements.pageTitle.textContent = state.title;
    elements.welcome.hidden = true;
    elements.messages.hidden = false;

    const userMessage = addMessage('user', query);
    state.history.push({ role: 'user', content: query });
    const assistantMessage = addMessage('assistant', '', { typing: true });
    elements.sendButton.disabled = true;

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: state.history.slice(-6) }),
      });
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || 'Ani could not complete that request.');
      }

      const answer = result.answer.trim();
      assistantMessage.querySelector('.answer-content').innerHTML = renderMarkdown(answer, result.sources || []);
      state.history.push({ role: 'assistant', content: answer });
    } catch (error) {
      const answer = assistantMessage.querySelector('.answer-content');
      answer.innerHTML = `<p>${escapeHtml(error.message)}</p><p>Your request is still here. Try again when Ani is ready.</p>`;
      answer.append(retryButton(query, userMessage, assistantMessage));
      state.history.pop();
      showToast('Ani could not connect right now.');
    } finally {
      state.isWaiting = false;
      elements.sendButton.disabled = !elements.input.value.trim();
    }
  }

  function submitMessage(event) {
    event.preventDefault();
    const query = elements.input.value.trim().slice(0, MAX_INPUT_LENGTH);
    if (!query || state.isWaiting) return;

    elements.input.value = '';
    elements.input.style.height = 'auto';
    askAni(query);
  }

  function initialTheme() {
    try {
      const savedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
      if (savedTheme === 'dark' || savedTheme === 'light') return savedTheme;
    } catch {
      // Keep the app usable when browser storage is disabled.
    }
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }

  function applyTheme(theme) {
    const darkMode = theme === 'dark';
    document.documentElement.dataset.theme = darkMode ? 'dark' : 'light';
    document.querySelector('meta[name="theme-color"]').content = darkMode ? '#1d1f1c' : '#f7f5f0';
    elements.themeToggle.querySelector('.theme-icon').textContent = darkMode ? '☼' : '☾';
    elements.themeToggle.setAttribute('aria-label', `Switch to ${darkMode ? 'light' : 'dark'} mode`);
    elements.themeToggle.title = `Switch to ${darkMode ? 'light' : 'dark'} mode`;

    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, darkMode ? 'dark' : 'light');
    } catch {
      // Theme still applies for this page view when storage is disabled.
    }
  }

  elements.form.addEventListener('submit', submitMessage);
  elements.input.addEventListener('input', () => {
    elements.sendButton.disabled = state.isWaiting || !elements.input.value.trim();
    elements.input.style.height = 'auto';
    elements.input.style.height = `${Math.min(elements.input.scrollHeight, 120)}px`;
  });
  elements.input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      elements.form.requestSubmit();
    }
  });

  document.querySelectorAll('.suggestion').forEach((button) => {
    button.addEventListener('click', () => {
      setInputValue(button.dataset.prompt || '');
      showToast('Draft added. Edit it, then send when you’re ready.');
    });
  });

  document.querySelector('#assistantNav').addEventListener('click', (event) => {
    event.preventDefault();
    elements.welcome.hidden = state.history.length > 0;
    elements.messages.hidden = false;
    document.querySelector('#conversation').scrollTo({ top: 0, behavior: 'smooth' });
  });

  elements.themeToggle.addEventListener('click', () => {
    const nextTheme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(nextTheme);
  });

  applyTheme(initialTheme());
})();
