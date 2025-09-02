/**
 * LP Analytics SDK
 * Xserver VPS向けランディングページ分析ライブラリ
 */
class LPAnalytics {
    constructor(config) {
        this.trackingId = config.trackingId;
        this.apiEndpoint = config.apiEndpoint || window.location.origin;
        this.sessionId = this.generateSessionId();
        this.pageViewId = null;
        this.eventQueue = [];
        this.throttleDelay = 100;
        this.lastScrollEvent = 0;
        this.lastMouseMoveEvent = 0;
        this.maxScrollPercentage = 0;
        
        this.init();
    }

    generateSessionId() {
        return 'sess_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    generateElementSelector(element) {
        if (!element) return null;
        
        let selector = element.tagName.toLowerCase();
        
        if (element.id) {
            selector += '#' + element.id;
        }
        
        if (element.className) {
            const classes = element.className.split(' ').filter(c => c.trim());
            if (classes.length > 0) {
                selector += '.' + classes.slice(0, 3).join('.');
            }
        }
        
        return selector;
    }

    async init() {
        await this.trackPageView();
        this.bindEvents();
        this.startHeartbeat();
    }

    async trackPageView() {
        const pageViewData = {
            tracking_id: this.trackingId,
            session_id: this.sessionId,
            page_url: window.location.href,
            page_title: document.title,
            referrer: document.referrer || null,
            user_agent: navigator.userAgent,
            screen_width: screen.width,
            screen_height: screen.height,
            viewport_width: window.innerWidth,
            viewport_height: window.innerHeight
        };

        try {
            const response = await fetch(`${this.apiEndpoint}/analytics/api/page-view/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(pageViewData)
            });

            if (response.ok) {
                const result = await response.json();
                this.pageViewId = result.page_view_id;
            }
        } catch (error) {
            console.warn('LP Analytics: ページビュー送信に失敗しました', error);
        }
    }

    bindEvents() {
        this.bindClickEvents();
        this.bindScrollEvents();
        this.bindMouseMoveEvents();
        this.bindResizeEvents();
        this.bindFocusEvents();
    }

    bindClickEvents() {
        document.addEventListener('click', (event) => {
            const rect = event.target.getBoundingClientRect();
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
            
            this.queueEvent({
                event_type: 'click',
                x_coordinate: Math.round(event.clientX + scrollLeft),
                y_coordinate: Math.round(event.clientY + scrollTop),
                element_selector: this.generateElementSelector(event.target),
                element_text: event.target.textContent?.slice(0, 100) || null,
                viewport_width: window.innerWidth,
                viewport_height: window.innerHeight
            });
        });
    }

    bindScrollEvents() {
        let scrollTimeout;
        
        window.addEventListener('scroll', () => {
            const now = Date.now();
            if (now - this.lastScrollEvent < this.throttleDelay) return;
            this.lastScrollEvent = now;

            clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                const documentHeight = document.documentElement.scrollHeight - window.innerHeight;
                const scrollPercentage = Math.round((scrollTop / documentHeight) * 100);
                
                if (scrollPercentage > this.maxScrollPercentage) {
                    this.maxScrollPercentage = scrollPercentage;
                    
                    this.queueEvent({
                        event_type: 'scroll',
                        scroll_percentage: scrollPercentage,
                        viewport_width: window.innerWidth,
                        viewport_height: window.innerHeight
                    });
                }
            }, 250);
        });
    }

    bindMouseMoveEvents() {
        window.addEventListener('mousemove', (event) => {
            const now = Date.now();
            if (now - this.lastMouseMoveEvent < this.throttleDelay * 5) return;
            this.lastMouseMoveEvent = now;

            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
            
            this.queueEvent({
                event_type: 'mousemove',
                x_coordinate: Math.round(event.clientX + scrollLeft),
                y_coordinate: Math.round(event.clientY + scrollTop),
                viewport_width: window.innerWidth,
                viewport_height: window.innerHeight
            });
        });
    }

    bindResizeEvents() {
        window.addEventListener('resize', () => {
            this.queueEvent({
                event_type: 'resize',
                viewport_width: window.innerWidth,
                viewport_height: window.innerHeight
            });
        });
    }

    bindFocusEvents() {
        document.addEventListener('focusin', (event) => {
            this.queueEvent({
                event_type: 'focus',
                element_selector: this.generateElementSelector(event.target),
                element_text: event.target.value?.slice(0, 100) || null
            });
        });

        document.addEventListener('focusout', (event) => {
            this.queueEvent({
                event_type: 'blur',
                element_selector: this.generateElementSelector(event.target),
                element_text: event.target.value?.slice(0, 100) || null
            });
        });
    }

    queueEvent(eventData) {
        if (!this.pageViewId) return;

        const event = {
            page_view_id: this.pageViewId,
            timestamp: new Date().toISOString(),
            ...eventData
        };

        this.eventQueue.push(event);

        if (this.eventQueue.length >= 10) {
            this.flushEvents();
        }
    }

    async flushEvents() {
        if (this.eventQueue.length === 0) return;

        const events = [...this.eventQueue];
        this.eventQueue = [];

        try {
            await fetch(`${this.apiEndpoint}/analytics/api/interactions/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ events })
            });
        } catch (error) {
            console.warn('LP Analytics: イベント送信に失敗しました', error);
            this.eventQueue.unshift(...events);
        }
    }

    startHeartbeat() {
        setInterval(() => {
            this.flushEvents();
        }, 5000);

        window.addEventListener('beforeunload', () => {
            if (this.eventQueue.length > 0) {
                navigator.sendBeacon(
                    `${this.apiEndpoint}/analytics/api/interactions/`,
                    JSON.stringify({ events: this.eventQueue })
                );
            }
        });
    }

    trackCustomEvent(eventName, data = {}) {
        this.queueEvent({
            event_type: 'custom',
            element_text: eventName,
            custom_data: JSON.stringify(data)
        });
    }
}

window.LPAnalytics = LPAnalytics;