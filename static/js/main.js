/* ============================================================
   DJ KUAMI YOGHURT — main.js
   Vanilla JS: nav toggle, audio player, gallery lightbox,
   chat polling, copy-to-clipboard, smooth scroll.
   ============================================================ */

'use strict';

/* ---- Nav Toggle ------------------------------------------ */
(function initNavToggle() {
  var toggle = document.getElementById('navToggle');
  var menu = document.getElementById('navMenu');
  if (!toggle || !menu) return;

  toggle.addEventListener('click', function () {
    var expanded = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', String(!expanded));
    menu.classList.toggle('is-open');
  });

  // Close menu when a link is clicked (mobile).
  menu.addEventListener('click', function (e) {
    if (e.target.classList.contains('nav__link')) {
      toggle.setAttribute('aria-expanded', 'false');
      menu.classList.remove('is-open');
    }
  });

  // Close menu when clicking outside.
  document.addEventListener('click', function (e) {
    if (!toggle.contains(e.target) && !menu.contains(e.target)) {
      toggle.setAttribute('aria-expanded', 'false');
      menu.classList.remove('is-open');
    }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
      toggle.setAttribute('aria-expanded', 'false');
      menu.classList.remove('is-open');
      toggle.focus();
    }
  });
})();


/* ---- Audio Player ---------------------------------------- */
function initAudioPlayer() {
  var audio = document.getElementById('audioPlayer');
  var playBtn = document.getElementById('playPauseBtn');
  var progressBar = document.getElementById('progressBar');
  var currentTimeEl = document.getElementById('currentTime');
  var totalTimeEl = document.getElementById('totalTime');
  var volumeSlider = document.getElementById('volumeSlider');
  var player = audio && audio.closest('.audio-player');
  var playerStatus = document.getElementById('playerStatus');

  if (!audio || !playBtn) return;
  if (audio.dataset.playerInitialized === 'true') return;
  audio.dataset.playerInitialized = 'true';

  var iconPlay = playBtn.querySelector('.icon-play');
  var iconPause = playBtn.querySelector('.icon-pause');

  function formatTime(secs) {
    if (!isFinite(secs)) return '--:--';
    var m = Math.floor(secs / 60);
    var s = Math.floor(secs % 60);
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  function setPlayingState(playing) {
    if (iconPlay) iconPlay.style.display = playing ? 'none' : '';
    if (iconPause) iconPause.style.display = playing ? '' : 'none';
    playBtn.setAttribute('aria-label', playing ? 'Pause' : 'Play');
  }

  function setPlayerState(state, message) {
    if (player) {
      player.classList.toggle('is-playing', state === 'playing');
      player.classList.toggle('is-loading', state === 'loading');
      player.classList.toggle('is-error', state === 'error');
      player.setAttribute('aria-busy', String(state === 'loading'));
    }
    if (playerStatus) {
      playerStatus.textContent = message || ({
        ready: 'Ready to play',
        loading: 'Loading audio',
        playing: 'Playing',
        paused: 'Paused',
        error: 'Audio could not be loaded'
      }[state] || 'Ready to play');
    }
  }

  function describeAudioError() {
    if (!audio.error) return 'Audio could not be loaded. Check your connection and try again.';
    return {
      1: 'Audio playback was interrupted. Press Play to try again.',
      2: 'Audio could not be downloaded. Check your connection and try again.',
      3: 'This audio file could not be decoded.',
      4: 'This audio file is unavailable or uses an unsupported format.'
    }[audio.error.code] || 'Audio could not be loaded. Check your connection and try again.';
  }

  function reportPlaybackFailure(error) {
    var message = error && error.name === 'NotAllowedError'
      ? 'Your browser blocked playback. Press Play to try again.'
      : describeAudioError();
    setPlayerState('error', message);
  }

  playBtn.addEventListener('click', function () {
    if (audio.paused) {
      var playback = audio.play();
      if (playback && typeof playback.catch === 'function') {
        playback.catch(reportPlaybackFailure);
      }
    } else {
      audio.pause();
    }
  });

  audio.addEventListener('loadstart', function () { setPlayerState('loading'); });
  audio.addEventListener('waiting', function () { setPlayerState('loading'); });
  audio.addEventListener('canplay', function () {
    setPlayerState(audio.paused ? 'ready' : 'playing');
  });
  audio.addEventListener('error', function () {
    setPlayerState('error', describeAudioError());
  });
  audio.addEventListener('play', function () {
    setPlayingState(true);
    setPlayerState('playing');
  });
  audio.addEventListener('pause', function () {
    setPlayingState(false);
    setPlayerState('paused');
  });
  audio.addEventListener('ended', function () {
    setPlayingState(false);
    setPlayerState('ready');
  });

  audio.addEventListener('loadedmetadata', function () {
    if (totalTimeEl) totalTimeEl.textContent = formatTime(audio.duration);
    if (progressBar) {
      progressBar.max = 100;
    }
    if (audio.paused) setPlayerState('ready');
  });

  audio.addEventListener('timeupdate', function () {
    if (currentTimeEl) currentTimeEl.textContent = formatTime(audio.currentTime);
    if (progressBar && audio.duration) {
      progressBar.value = (audio.currentTime / audio.duration) * 100;
    }
  });

  if (progressBar) {
    progressBar.addEventListener('input', function () {
      if (audio.duration) {
        audio.currentTime = (progressBar.value / 100) * audio.duration;
      }
    });
  }

  if (volumeSlider) {
    volumeSlider.addEventListener('input', function () {
      audio.volume = volumeSlider.value / 100;
    });
  }

  // Keyboard shortcut: Space toggles play/pause.
  document.addEventListener('keydown', function (e) {
    if (
      e.code === 'Space' &&
      document.activeElement.tagName !== 'INPUT' &&
      document.activeElement.tagName !== 'TEXTAREA' &&
      document.activeElement.tagName !== 'SELECT' &&
      document.activeElement.tagName !== 'BUTTON'
    ) {
      e.preventDefault();
      if (audio.paused) {
        var playback = audio.play();
        if (playback && typeof playback.catch === 'function') {
          playback.catch(reportPlaybackFailure);
        }
      } else {
        audio.pause();
      }
    }
  });
}

// Auto-init on pages that have the player.
document.addEventListener('DOMContentLoaded', function () {
  if (document.getElementById('audioPlayer')) {
    initAudioPlayer();
  }
});

window.initAudioPlayer = initAudioPlayer;


/* ---- Public page reveals -------------------------------- */
function initPublicReveals() {
  if (!document.body.classList.contains('public-site')) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  if (!('IntersectionObserver' in window)) return;

  var revealItems = document.querySelectorAll(
    'main section:not(.hero), main .card, main .about-layout, main .gallery-grid, main .chat-window'
  );
  if (!revealItems.length) return;

  revealItems.forEach(function (item) { item.setAttribute('data-reveal', ''); });
  document.documentElement.classList.add('has-reveal-motion');

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -32px 0px' });

  revealItems.forEach(function (item) { observer.observe(item); });
}

document.addEventListener('DOMContentLoaded', initPublicReveals);


/* ---- Gallery Lightbox ------------------------------------ */
function initGalleryLightbox() {
  var grid = document.getElementById('galleryGrid');
  var lightbox = document.getElementById('lightbox');
  var lightboxImg = document.getElementById('lightboxImg');
  var lightboxCaption = document.getElementById('lightboxCaption');
  var closeBtn = document.getElementById('lightboxClose');
  var prevBtn = document.getElementById('lightboxPrev');
  var nextBtn = document.getElementById('lightboxNext');

  if (!grid || !lightbox) return;

  var items = Array.from(grid.querySelectorAll('[data-lightbox-index]'));
  var currentIndex = 0;

  function openLightbox(index) {
    currentIndex = index;
    var item = items[currentIndex];
    if (!item) return;
    lightboxImg.src = item.dataset.lightboxSrc || '';
    lightboxImg.alt = item.dataset.lightboxTitle || '';
    if (lightboxCaption) lightboxCaption.textContent = item.dataset.lightboxTitle || '';
    lightbox.removeAttribute('hidden');
    document.body.style.overflow = 'hidden';
    closeBtn.focus();
  }

  function closeLightbox() {
    lightbox.setAttribute('hidden', '');
    document.body.style.overflow = '';
    if (items[currentIndex]) items[currentIndex].focus();
  }

  function navigate(direction) {
    var next = (currentIndex + direction + items.length) % items.length;
    openLightbox(next);
  }

  items.forEach(function (item) {
    item.addEventListener('click', function () {
      openLightbox(parseInt(item.dataset.lightboxIndex, 10));
    });
  });

  if (closeBtn) closeBtn.addEventListener('click', closeLightbox);
  if (prevBtn) prevBtn.addEventListener('click', function () { navigate(-1); });
  if (nextBtn) nextBtn.addEventListener('click', function () { navigate(1); });

  lightbox.addEventListener('click', function (e) {
    if (e.target === lightbox) closeLightbox();
  });

  document.addEventListener('keydown', function (e) {
    if (lightbox.hasAttribute('hidden')) return;
    if (e.key === 'Escape') closeLightbox();
    if (e.key === 'ArrowLeft') navigate(-1);
    if (e.key === 'ArrowRight') navigate(1);
  });
}

window.initGalleryLightbox = initGalleryLightbox;

document.addEventListener('DOMContentLoaded', function () {
  if (document.getElementById('galleryGrid')) {
    initGalleryLightbox();
  }
});


/* ---- Chat Polling ---------------------------------------- */
function startChatPolling(sendUrl, pollUrl, historyUrl, deleteBaseUrl, csrfToken) {
  var sendForm = document.getElementById('chatSendForm');
  var messagesContainer = document.getElementById('chatMessages');
  var chatInput = document.getElementById('chatInput');
  var sendError = document.getElementById('sendError');

  if (!sendForm || !messagesContainer) return;

  var lastMessageId = 0;
  var historyButton = document.getElementById('loadOlderMessages');
  var chatStatus = document.getElementById('chatStatus');

  var existingMessages = messagesContainer.querySelectorAll('.chat-message');
  if (existingMessages.length > 0) {
    lastMessageId = parseInt(existingMessages[existingMessages.length - 1].id.replace('msg-', ''), 10) || 0;
  }

  function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }

  function appendDeleteControl(bubble, msg) {
    if (!msg.is_own || msg.is_deleted) return;
    var form = document.createElement('form');
    form.method = 'post';
    form.action = deleteBaseUrl + msg.id + '/delete/';
    form.addEventListener('submit', function (event) {
      if (!window.confirm('Remove this message from the conversation?')) event.preventDefault();
    });
    var csrf = document.createElement('input');
    csrf.type = 'hidden';
    csrf.name = 'csrfmiddlewaretoken';
    csrf.value = csrfToken;
    var confirmField = document.createElement('input');
    confirmField.type = 'hidden';
    confirmField.name = 'confirm_delete';
    confirmField.value = '1';
    var button = document.createElement('button');
    button.type = 'submit';
    button.className = 'chat-message__delete';
    button.textContent = 'Delete message';
    form.appendChild(csrf);
    form.appendChild(confirmField);
    form.appendChild(button);
    bubble.appendChild(form);
  }

  function appendMessage(msg) {
    var div = document.createElement('div');
    div.className = 'chat-message ' + (msg.is_from_dj ? 'chat-message--dj' : 'chat-message--customer');
    div.id = 'msg-' + msg.id;

    var ts = new Date(msg.timestamp);
    var timeStr = ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    var bubble = document.createElement('div');
    bubble.className = 'chat-message__bubble';
    var text = document.createElement('p');
    text.className = 'chat-message__text';
    text.textContent = msg.is_deleted ? 'This message was removed.' : msg.content;
    var time = document.createElement('time');
    time.className = 'chat-message__time';
    time.dateTime = msg.timestamp;
    time.textContent = timeStr;
    bubble.appendChild(text);
    bubble.appendChild(time);
    appendDeleteControl(bubble, msg);
    div.appendChild(bubble);

    // Remove empty-state placeholder if present.
    var empty = messagesContainer.querySelector('.chat-window__empty');
    if (empty) empty.remove();

    messagesContainer.appendChild(div);
    lastMessageId = Math.max(lastMessageId, msg.id);
  }

  function updateDeletedMessage(msg) {
    var message = document.getElementById('msg-' + msg.id);
    if (!message) return;
    var text = message.querySelector('.chat-message__text');
    if (text) text.textContent = 'This message was removed.';
    var deleteButton = message.querySelector('.chat-message__delete');
    if (deleteButton) deleteButton.remove();
  }

  // Send message.
  sendForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var content = chatInput.value.trim();
    if (!content) return;

    var formData = new FormData();
    formData.append('content', content);
    formData.append('csrfmiddlewaretoken', csrfToken);

    fetch(sendUrl, {
      method: 'POST',
      body: formData,
      headers: { 'X-CSRFToken': csrfToken }
    })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.error) {
          if (sendError) {
            sendError.textContent = data.error;
            sendError.removeAttribute('hidden');
          }
        } else {
          chatInput.value = '';
          if (sendError) sendError.setAttribute('hidden', '');
          appendMessage(data);
          scrollToBottom();
        }
      })
      .catch(function () {
        if (sendError) {
          sendError.textContent = 'Failed to send message. Please try again.';
          sendError.removeAttribute('hidden');
        }
      });
  });

  // Poll for new messages.
  function poll() {
    var url = pollUrl + '?after=' + encodeURIComponent(lastMessageId);
    fetch(url, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (data.messages && data.messages.length > 0) {
          data.messages.forEach(function (msg) {
            // Avoid duplicates: skip if already on the page.
            if (!document.getElementById('msg-' + msg.id)) {
              appendMessage(msg);
            }
          });
          scrollToBottom();
        }
        if (data.deleted_updates) data.deleted_updates.forEach(updateDeletedMessage);
        if (chatStatus && typeof data.agent_online === 'boolean') {
          chatStatus.textContent = data.agent_online ? 'Staff online' : 'Staff offline';
        }
      })
      .catch(function () {
        if (chatStatus) chatStatus.textContent = 'Connection interrupted';
      });
  }

  if (historyButton) {
    historyButton.addEventListener('click', function () {
      var firstMessage = messagesContainer.querySelector('.chat-message');
      var beforeId = firstMessage ? parseInt(firstMessage.id.replace('msg-', ''), 10) : 0;
      if (!beforeId) return;
      historyButton.disabled = true;
      fetch(historyUrl + '?before=' + encodeURIComponent(beforeId))
        .then(function (response) {
          if (!response.ok) throw new Error('History request failed');
          return response.json();
        })
        .then(function (data) {
          var fragment = document.createDocumentFragment();
          data.messages.forEach(function (msg) {
            var div = document.createElement('div');
            div.className = 'chat-message ' + (msg.is_from_dj ? 'chat-message--dj' : 'chat-message--customer');
            div.id = 'msg-' + msg.id;
            var bubble = document.createElement('div');
            bubble.className = 'chat-message__bubble';
            var text = document.createElement('p');
            text.className = 'chat-message__text';
            text.textContent = msg.is_deleted ? 'This message was removed.' : msg.content;
            var time = document.createElement('time');
            time.className = 'chat-message__time';
            time.dateTime = msg.timestamp;
            time.textContent = new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
            bubble.appendChild(text);
            bubble.appendChild(time);
            appendDeleteControl(bubble, msg);
            div.appendChild(bubble);
            fragment.appendChild(div);
          });
          var previousHeight = messagesContainer.scrollHeight;
          messagesContainer.insertBefore(fragment, historyButton.nextSibling);
          messagesContainer.scrollTop += messagesContainer.scrollHeight - previousHeight;
          if (!data.has_more) historyButton.remove();
          else historyButton.disabled = false;
        })
        .catch(function () {
          historyButton.disabled = false;
          if (sendError) {
            sendError.textContent = 'Could not load older messages.';
            sendError.removeAttribute('hidden');
          }
        });
    });
  }

  // Start polling every 3 seconds.
  scrollToBottom();
  setInterval(poll, 3000);
}

window.startChatPolling = startChatPolling;


/* ---- Copy to Clipboard ----------------------------------- */
function copyToClipboard(elementId, buttonEl) {
  var el = document.getElementById(elementId);
  if (!el) return;
  var text = el.value || el.textContent;
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(function () {
      if (buttonEl) {
        var original = buttonEl.textContent;
        buttonEl.textContent = 'Copied!';
        setTimeout(function () { buttonEl.textContent = original; }, 2000);
      }
    });
  } else {
    if (el.select) el.select();
    document.execCommand('copy');
  }
}

window.copyToClipboard = copyToClipboard;


/* ---- Smooth Scroll --------------------------------------- */
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener('click', function (e) {
      var targetId = anchor.getAttribute('href').slice(1);
      var target = document.getElementById(targetId);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        target.focus({ preventScroll: true });
      }
    });
  });
});


/* ---- Auto-dismiss alerts after 5s ------------------------ */
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.alert').forEach(function (alert) {
    setTimeout(function () {
      alert.style.transition = 'opacity 0.4s';
      alert.style.opacity = '0';
      setTimeout(function () { alert.remove(); }, 400);
    }, 5000);
  });
});
