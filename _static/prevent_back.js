// Prevent browser back button navigation - aggressive approach
// This script runs immediately to prevent timer resets

(function() {
    'use strict';
    
    // Store a unique page ID to prevent cache restoration
    var pageId = Date.now() + Math.random();
    sessionStorage.setItem('currentPageId', pageId);
    sessionStorage.setItem('lastPageUrl', window.location.href);
    
    // Prevent page from being cached
    if (window.history && window.history.replaceState) {
        // Add a timestamp to the URL to prevent cache restoration
        var url = window.location.href;
        if (url.indexOf('_t=') === -1) {
            url += (url.indexOf('?') === -1 ? '?' : '&') + '_t=' + pageId;
            window.history.replaceState(null, null, url);
        }
    }
    
    // Push a new state to create a barrier
    window.history.pushState({pageId: pageId}, null, window.location.href);
    
    // Function to force user to stay on current page
    function preventBack() {
        // Check if we're trying to restore from cache
        var storedPageId = sessionStorage.getItem('currentPageId');
        var storedUrl = sessionStorage.getItem('lastPageUrl');
        
        if (storedPageId !== String(pageId) || storedUrl !== window.location.href) {
            // Page was restored from cache - reload to reset timer
            window.location.reload();
            return;
        }
        
        // Push forward to prevent back navigation
        window.history.pushState({pageId: pageId}, null, window.location.href);
    }
    
    // Handle back button attempts
    window.addEventListener('popstate', function(event) {
        // If state doesn't have our pageId, it's a back navigation attempt
        if (!event.state || event.state.pageId !== pageId) {
            preventBack();
            // Force forward
            setTimeout(function() {
                window.history.go(1);
            }, 0);
        }
    }, false);
    
    // Also set onpopstate as backup
    window.onpopstate = function(event) {
        if (!event.state || event.state.pageId !== pageId) {
            preventBack();
            setTimeout(function() {
                window.history.go(1);
            }, 0);
        }
    };
    
    // Check on page load if this is a restored page
    window.addEventListener('pageshow', function(event) {
        // If page was restored from cache (back/forward cache)
        if (event.persisted) {
            // Force reload to reset timer
            window.location.reload();
        }
        
        // Check if page ID matches
        var storedPageId = sessionStorage.getItem('currentPageId');
        if (storedPageId !== String(pageId)) {
            window.location.reload();
        }
    }, false);
    
    // Prevent page from being stored in cache
    window.addEventListener('beforeunload', function() {
        // Clear the page ID so back navigation will reload
        sessionStorage.removeItem('currentPageId');
    }, false);
    
    // Continuously monitor and prevent back navigation
    setInterval(function() {
        // Check if URL has changed (indicating navigation)
        var currentUrl = window.location.href;
        var storedUrl = sessionStorage.getItem('lastPageUrl');
        
        if (currentUrl !== storedUrl) {
            // URL changed - might be a back navigation
            preventBack();
        }
        
        // Keep pushing forward to prevent back navigation
        window.history.pushState({pageId: pageId}, null, window.location.href);
    }, 100);
})();

