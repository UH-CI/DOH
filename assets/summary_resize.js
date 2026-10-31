// Scales .summary-card-inner so the card contents always fill the square card as a perfect miniature.
(function () {
    var BASE_SIZE = 300;

    function applyScale(card) {
        var inner = card.querySelector('.summary-card-inner');
        if (!inner) return;
        var w = card.getBoundingClientRect().width;
        if (w < 1) return;
        var scale = w / BASE_SIZE;
        inner.style.width = BASE_SIZE + 'px';
        inner.style.height = BASE_SIZE + 'px';
        inner.style.transform = 'scale(' + scale + ')';
        inner.style.transformOrigin = 'top left';
    }

    function scaleAll() {
        document.querySelectorAll('.summary-square-card').forEach(applyScale);
    }

    // ResizeObserver fires whenever each card changes size (window resize, column reflow, etc.)
    var ro = new ResizeObserver(function (entries) {
        entries.forEach(function (e) { applyScale(e.target); });
    });

    function setup() {
        document.querySelectorAll('.summary-square-card').forEach(function (card) {
            applyScale(card);
            ro.observe(card);
        });
    }

    // Run after initial DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setup);
    } else {
        setup();
    }

    // Re-run whenever Dash adds/replaces DOM nodes (page navigation, callbacks)
    new MutationObserver(function (mutations) {
        var needsSetup = mutations.some(function (m) {
            return Array.from(m.addedNodes).some(function (n) {
                return n.nodeType === 1 && (
                    n.classList && n.classList.contains('summary-square-card') ||
                    (n.querySelector && n.querySelector('.summary-square-card'))
                );
            });
        });
        if (needsSetup) setup();
    }).observe(document.body, { childList: true, subtree: true });
}());
