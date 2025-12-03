// Minimal safeguard: if the browser serves a page from the back/forward cache,
// force a reload so server-side timeouts continue to apply.
(function () {
    'use strict';

    function shouldReloadOnPageshow(event) {
        if (event.persisted) {
            return true;
        }

        if (window.performance && performance.getEntriesByType) {
            var entries = performance.getEntriesByType('navigation');
            if (entries && entries.length > 0) {
                var navType = entries[0].type;
                if (navType === 'back_forward') {
                    return true;
                }
            }
        }

        return false;
    }

    window.addEventListener('pageshow', function (event) {
        if (shouldReloadOnPageshow(event)) {
            var url = new URL(window.location.href);
            url.searchParams.delete('_ts');
            url.searchParams.append('_ts', Date.now().toString());
            window.location.replace(url.toString());
        }
    });
})();

