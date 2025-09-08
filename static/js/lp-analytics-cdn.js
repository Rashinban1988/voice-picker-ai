/*!
 * LP Analytics CDN SDK v1.0.0
 * 外部配布用のシンプルなヒートマップ分析SDK
 *
 * 基本使用方法:
 * <script src="https://your-domain.com/analytics/sdk/lp-analytics.js" data-tracking-id="lp_xxxxx"></script>
 *
 * 自動生成モード:
 * <script src="https://your-domain.com/analytics/sdk/lp-analytics.js" data-auto-generate="true"></script>
 *
 * カスタムAPI:
 * <script src="https://your-domain.com/analytics/sdk/lp-analytics.js" data-tracking-id="lp_xxxxx" data-api-endpoint="https://custom-api.com"></script>
 */

(function() {
    'use strict'

    // CDN SDK設定を自動取得 - より確実な方法
    const findLPAnalyticsScript = () => {
        const scripts = document.querySelectorAll('script[src*="lp-analytics.js"]')
        return scripts[scripts.length - 1] // 最後に見つかったものを使用
    }

    let script = findLPAnalyticsScript()

    // スクリプトが見つからない場合は、現在のスクリプトを使用
    if (!script) {
        const scripts = document.getElementsByTagName('script')
        script = scripts[scripts.length - 1]
    }

    let trackingId = script ? script.getAttribute('data-tracking-id') : null
    const apiEndpoint = script ? (script.getAttribute('data-api-endpoint') || window.location.origin) : window.location.origin
    const debug = script ? script.getAttribute('data-debug') === 'true' : false
    const autoGenerate = script ? script.getAttribute('data-auto-generate') === 'true' : false

    // 自動生成オプションが有効で、トラッキングIDが無い場合は生成
    if (!trackingId && autoGenerate) {
        trackingId = 'lp_auto_' + Math.random().toString(36).substr(2, 12)
        console.log('Auto-generated tracking ID:', trackingId)
    }

    if (!trackingId) {
        console.error('LP Analytics: data-tracking-id が設定されていません。data-auto-generate="true" を追加するか、data-tracking-id を設定してください')
        return
    }

    if (debug) {
        console.log('LP Analytics CDN SDK初期化:', { trackingId, apiEndpoint })
    }

    // コアAnalyticsクラス（簡略版）
    class LPAnalyticsCDN {
        constructor(config) {
            this.config = {
                trackingId: config.trackingId,
                apiEndpoint: config.apiEndpoint,
                debug: config.debug || false,
                batchSize: 10,
                flushInterval: 5000,
                sessionId: this.generateSessionId()
            }

            this.eventQueue = []
            this.pageViewId = null
            this.isInitialized = false

            this.init()
        }

        generateSessionId() {
            return 'sess_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now()
        }

        async init() {
            try {
                // ページビュー作成
                await this.createPageView()

                // 自動イベント追跡開始
                this.setupAutoTracking()

                // 定期的なフラッシュ
                setInterval(() => this.flush(), this.config.flushInterval)

                this.isInitialized = true
                if (this.config.debug) {
                    console.log('LP Analytics CDN初期化完了')
                }
            } catch (error) {
                console.error('LP Analytics CDN初期化エラー:', error)
            }
        }

        async createPageView() {
            try {
                const response = await fetch(`${this.config.apiEndpoint}/analytics/api/page-view/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tracking_id: this.config.trackingId,
                        page_url: window.location.href,
                        page_title: document.title,
                        referrer: document.referrer || null,
                        session_id: this.config.sessionId,
                        user_agent: navigator.userAgent,
                        screen_width: screen.width,
                        screen_height: screen.height
                    })
                })

                const result = await response.json()
                if (result.success) {
                    this.pageViewId = result.page_view_id
                    if (this.config.debug) {
                        console.log('ページビュー作成成功:', this.pageViewId)
                    }
                }
            } catch (error) {
                console.error('ページビュー作成エラー:', error)
            }
        }

        setupAutoTracking() {
            // クリック追跡
            document.addEventListener('click', (e) => {
                this.trackClick(e)
            })

            // スクロール追跡（スロットル）
            let scrollTimer = null
            document.addEventListener('scroll', () => {
                if (scrollTimer) clearTimeout(scrollTimer)
                scrollTimer = setTimeout(() => {
                    this.trackScroll()
                }, 100)
            })

            // ページ離脱時の最終フラッシュ
            window.addEventListener('beforeunload', () => {
                this.flush(true) // 同期モード
            })
        }

        trackClick(event) {
            const rect = document.documentElement.getBoundingClientRect()
            const data = {
                event_type: 'click',
                x_coordinate: Math.round(event.clientX + window.scrollX),
                y_coordinate: Math.round(event.clientY + window.scrollY),
                element_selector: this.getElementSelector(event.target),
                element_text: event.target.textContent?.slice(0, 100) || null,
                timestamp: new Date().toISOString()
            }

            this.addEvent(data)

            if (this.config.debug) {
                console.log('クリックイベント追跡:', data)
            }
        }

        trackScroll() {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop
            const scrollHeight = document.documentElement.scrollHeight - window.innerHeight
            const scrollPercentage = scrollHeight > 0 ? Math.round((scrollTop / scrollHeight) * 100) : 0

            const data = {
                event_type: 'scroll',
                scroll_percentage: scrollPercentage,
                timestamp: new Date().toISOString()
            }

            this.addEvent(data)
        }

        getElementSelector(element) {
            if (element.id) return `#${element.id}`
            if (element.className) return `.${element.className.split(' ')[0]}`
            return element.tagName.toLowerCase()
        }

        addEvent(eventData) {
            if (!this.pageViewId) return

            this.eventQueue.push({
                page_view_id: this.pageViewId,
                ...eventData
            })

            // バッチサイズに達したら即座にフラッシュ
            if (this.eventQueue.length >= this.config.batchSize) {
                this.flush()
            }
        }

        async flush(sync = false) {
            if (this.eventQueue.length === 0) return

            const events = [...this.eventQueue]
            this.eventQueue = []

            const requestBody = { events }

            try {
                if (sync) {
                    // 同期リクエスト（ページ離脱時）
                    navigator.sendBeacon(
                        `${this.config.apiEndpoint}/analytics/api/interactions/`,
                        JSON.stringify(requestBody)
                    )
                } else {
                    // 非同期リクエスト
                    await fetch(`${this.config.apiEndpoint}/analytics/api/interactions/`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(requestBody)
                    })
                }

                if (this.config.debug) {
                    console.log(`${events.length}個のイベントを送信しました`)
                }
            } catch (error) {
                console.error('イベント送信エラー:', error)
                // 失敗した場合はキューに戻す
                this.eventQueue.unshift(...events)
            }
        }

        // 手動イベント追跡API
        track(eventName, properties = {}) {
            this.addEvent({
                event_type: 'custom',
                custom_event_name: eventName,
                custom_properties: JSON.stringify(properties),
                timestamp: new Date().toISOString()
            })
        }
    }

    // DOM読み込み完了後に自動初期化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.lpAnalytics = new LPAnalyticsCDN({
                trackingId,
                apiEndpoint,
                debug
            })
        })
    } else {
        // すでに読み込み完了している場合
        window.lpAnalytics = new LPAnalyticsCDN({
            trackingId,
            apiEndpoint,
            debug
        })
    }

})()