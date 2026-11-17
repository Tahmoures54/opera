/**
 * OPERA Command Palette
 * Open with Ctrl+K / Cmd+K or the search button in the top bar.
 */
(function () {
  var ITEMS = [
    { title: 'Operations Dashboard', hint: 'Projects & readiness', path: '/commissioning/', icon: 'fa-gauge-high' },
    { title: 'Create Project', hint: 'New commissioning project', path: '/commissioning/projects/new', icon: 'fa-folder-plus' },
    { title: 'Product Overview', hint: 'OPERA capabilities', path: '/overview', icon: 'fa-compass' },
    { title: 'Getting Started', hint: 'First steps', path: '/getting-started', icon: 'fa-book-open' },
    { title: 'User Guide', hint: 'How to use OPERA', path: '/user-guide', icon: 'fa-book' },
    { title: 'Help Center', hint: 'Guides & support', path: '/help/', icon: 'fa-circle-question' },
    { title: 'Contact', hint: 'Contact the OPERA team', path: '/contact', icon: 'fa-envelope' },
    { title: 'About OPERA', hint: 'Product information', path: '/about', icon: 'fa-circle-info' },
    { title: 'Privacy Policy', hint: 'Data & privacy', path: '/privacy_policy', icon: 'fa-shield-halved' },
    { title: 'Terms of Service', hint: 'Terms & conditions', path: '/terms_of_service', icon: 'fa-file-contract' }
  ];

  // Resolve real paths from sidebar links when available
  function hydratePaths() {
    document.querySelectorAll('.mh-nav a[href]').forEach(function (a) {
      var href = a.getAttribute('href');
      var label = (a.textContent || '').trim().toLowerCase();
      ITEMS.forEach(function (item) {
        if (label.indexOf(item.title.toLowerCase()) !== -1 || label === item.title.toLowerCase()) {
          item.path = href;
        }
      });
    });
  }

  var overlay, input, list, activeIndex = 0, filtered = [];

  function ensureUI() {
    if (overlay) return;
    overlay = document.createElement('div');
    overlay.className = 'mh-cmd-overlay';
    overlay.innerHTML =
      '<div class="mh-cmd" role="dialog" aria-modal="true" aria-label="Command palette">' +
      '  <div class="mh-cmd-input-wrap">' +
      '    <i class="fas fa-search"></i>' +
      '    <input type="search" class="mh-cmd-input" placeholder="Jump to…" autocomplete="off" spellcheck="false">' +
      '    <kbd>ESC</kbd>' +
      '  </div>' +
      '  <ul class="mh-cmd-list" role="listbox"></ul>' +
      '  <div class="mh-cmd-hint">↑↓ navigate · Enter open · Esc close</div>' +
      '</div>';
    document.body.appendChild(overlay);
    input = overlay.querySelector('.mh-cmd-input');
    list = overlay.querySelector('.mh-cmd-list');

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close();
    });
    input.addEventListener('input', function () {
      render(input.value);
    });
    input.addEventListener('keydown', onKey);
  }

  function render(query) {
    query = (query || '').trim().toLowerCase();
    filtered = !query
      ? ITEMS.slice()
      : ITEMS.filter(function (item) {
          return (
            item.title.toLowerCase().indexOf(query) !== -1 ||
            (item.hint && item.hint.toLowerCase().indexOf(query) !== -1)
          );
        });
    activeIndex = 0;
    list.innerHTML = '';
    if (!filtered.length) {
      list.innerHTML = '<li class="mh-cmd-empty">No matches</li>';
      return;
    }
    filtered.forEach(function (item, i) {
      var li = document.createElement('li');
      li.className = 'mh-cmd-item' + (i === 0 ? ' active' : '');
      li.setAttribute('role', 'option');
      li.innerHTML =
        '<i class="fas ' + item.icon + '"></i>' +
        '<span class="mh-cmd-title">' + item.title + '</span>' +
        '<span class="mh-cmd-hint-text">' + (item.hint || '') + '</span>';
      li.addEventListener('mouseenter', function () {
        activeIndex = i;
        syncActive();
      });
      li.addEventListener('click', function () {
        go(item.path);
      });
      list.appendChild(li);
    });
  }

  function syncActive() {
    var nodes = list.querySelectorAll('.mh-cmd-item');
    nodes.forEach(function (n, i) {
      n.classList.toggle('active', i === activeIndex);
    });
    if (nodes[activeIndex]) {
      nodes[activeIndex].scrollIntoView({ block: 'nearest' });
    }
  }

  function onKey(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIndex = Math.min(activeIndex + 1, filtered.length - 1);
      syncActive();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIndex = Math.max(activeIndex - 1, 0);
      syncActive();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[activeIndex]) go(filtered[activeIndex].path);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      close();
    }
  }

  function go(path) {
    close();
    if (path) window.location.href = path;
  }

  function open() {
    ensureUI();
    hydratePaths();
    overlay.classList.add('open');
    input.value = '';
    render('');
    setTimeout(function () { input.focus(); }, 10);
  }

  function close() {
    if (!overlay) return;
    overlay.classList.remove('open');
  }

  document.addEventListener('keydown', function (e) {
    var isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
    if ((isMac ? e.metaKey : e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
      e.preventDefault();
      if (document.body.querySelector('.mh-sidebar')) open();
    }
    if (e.key === 'Escape' && overlay && overlay.classList.contains('open')) {
      close();
    }
  });

  document.addEventListener('DOMContentLoaded', function () {
    var actions = document.querySelector('.mh-top-actions');
    if (actions && !document.getElementById('mh-cmd-trigger')) {
      var btn = document.createElement('button');
      btn.id = 'mh-cmd-trigger';
      btn.type = 'button';
      btn.className = 'mh-pill mh-cmd-trigger';
      btn.setAttribute('aria-label', 'Open command palette');
      btn.innerHTML = '<i class="fas fa-search"></i><span class="mh-cmd-trigger-label">Search</span><kbd>⌘K</kbd>';
      btn.addEventListener('click', open);
      actions.insertBefore(btn, actions.firstChild);
    }
  });

  window.mhCommandPalette = { open: open, close: close };
})();
