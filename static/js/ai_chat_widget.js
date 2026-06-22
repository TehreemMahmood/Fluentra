(function () {
    function getCsrfToken() {
        var input = document.querySelector('[name=csrfmiddlewaretoken]');
        if (input && input.value) return input.value;

        var cookies = document.cookie ? document.cookie.split('; ') : [];
        for (var i = 0; i < cookies.length; i++) {
            if (cookies[i].indexOf('csrftoken=') === 0) {
                return cookies[i].split('=')[1];
            }
        }
        return '';
    }

    function setupAiChatWidget() {
        var fab = document.getElementById('ai-chat-fab');
        var panel = document.getElementById('ai-chat-panel');
        var closeBtn = document.getElementById('ai-chat-close');
        var form = document.getElementById('ai-chat-form');
        var input = document.getElementById('ai-chat-input');
        var messages = document.getElementById('ai-chat-messages');

        if (!fab || !panel || !form || !input || !messages) {
            return;
        }

        var history = [];
        var loading = false;

        function openPanel() {
            panel.classList.add('open');
            panel.setAttribute('aria-hidden', 'false');
            setTimeout(function () { input.focus(); }, 20);
        }

        function closePanel() {
            panel.classList.remove('open');
            panel.setAttribute('aria-hidden', 'true');
        }

        function addBubble(text, role, cssClass) {
            var div = document.createElement('div');
            div.className = 'ai-chat-bubble ' + (cssClass || role);
            div.textContent = text;
            messages.appendChild(div);
            messages.scrollTop = messages.scrollHeight;
        }

        function setFormDisabled(disabled) {
            loading = disabled;
            input.disabled = disabled;
            form.querySelector('button[type="submit"]').disabled = disabled;
        }

        fab.addEventListener('click', function () {
            if (panel.classList.contains('open')) {
                closePanel();
            } else {
                openPanel();
            }
        });

        if (closeBtn) {
            closeBtn.addEventListener('click', closePanel);
        }

        document.addEventListener('click', function (e) {
            if (!panel.classList.contains('open')) return;
            if (panel.contains(e.target) || fab.contains(e.target)) return;
            closePanel();
        });

        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && panel.classList.contains('open')) {
                closePanel();
            }
        });

        var askCoachButton = document.querySelector('.card .btn.btn-outline.btn-sm');
        if (askCoachButton) {
            askCoachButton.addEventListener('click', function (e) {
                e.preventDefault();
                openPanel();
            });
        }

        form.addEventListener('submit', function (e) {
            e.preventDefault();
            if (loading) return;

            var text = (input.value || '').trim();
            if (!text) return;

            addBubble(text, 'user');
            history.push({ role: 'user', content: text });
            input.value = '';

            setFormDisabled(true);
            addBubble('Thinking...', 'ai');

            fetch('/api/ai-chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({
                    message: text,
                    history: history
                })
            })
                .then(function (response) {
                    if (!response.ok) {
                        throw new Error('Server error: ' + response.status);
                    }
                    return response.json();
                })
                .then(function (data) {
                    messages.removeChild(messages.lastElementChild); // remove "Thinking..."

                    if (!data.success) {
                        throw new Error(data.error || 'Unable to get AI response.');
                    }

                    var reply = (data.reply || '').trim() || 'I could not generate a response right now.';
                    addBubble(reply, 'ai');
                    history.push({ role: 'assistant', content: reply });

                    if (history.length > 16) {
                        history = history.slice(history.length - 16);
                    }
                })
                .catch(function (err) {
                    if (messages.lastElementChild && messages.lastElementChild.textContent === 'Thinking...') {
                        messages.removeChild(messages.lastElementChild);
                    }
                    addBubble(err.message || 'Something went wrong.', 'ai', 'error');
                })
                .finally(function () {
                    setFormDisabled(false);
                    input.focus();
                });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupAiChatWidget);
    } else {
        setupAiChatWidget();
    }
})();
