// Cache buster utility for development
(function() {
    'use strict';
    
    // Only run in development mode
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        // Add version parameter to all CSS links
        const links = document.querySelectorAll('link[rel="stylesheet"]');
        links.forEach(link => {
            const href = link.getAttribute('href');
            if (href && !href.includes('?v=')) {
                link.setAttribute('href', href + '?v=' + Date.now());
            }
        });
        
        // Add version parameter to all script tags
        const scripts = document.querySelectorAll('script[src]');
        scripts.forEach(script => {
            const src = script.getAttribute('src');
            if (src && !src.includes('?v=') && !src.includes('node_modules')) {
                script.setAttribute('src', src + '?v=' + Date.now());
            }
        });
    }
})();