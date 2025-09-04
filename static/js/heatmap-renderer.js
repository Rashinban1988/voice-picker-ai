/**
 * Advanced Heatmap Renderer with Canvas
 * より詳細で美しいヒートマップ描画システム
 */

class HeatmapRenderer {
    constructor(container, options = {}) {
        this.container = container
        this.canvas = document.createElement('canvas')
        this.ctx = this.canvas.getContext('2d')
        this.iframe = null
        this.scrollOffset = { x: 0, y: 0 }
        this.options = {
            radius: 25,
            blur: 15,
            maxOpacity: 0.8,
            minOpacity: 0.1,
            gradient: {
                0.0: 'rgba(0, 0, 255, 0)',
                0.2: 'rgba(0, 255, 0, 0.7)',
                0.4: 'rgba(255, 255, 0, 0.8)',
                0.6: 'rgba(255, 165, 0, 0.9)',
                1.0: 'rgba(255, 0, 0, 1)',
            },
            ...options
        }

        this.setupCanvas()
        this.createGradient()
        this.setupScrollTracking()
    }

    setupCanvas() {
        // iframe要素を取得
        this.iframe = document.getElementById('page-iframe')

        this.canvas.style.position = 'absolute'
        this.canvas.style.pointerEvents = 'none'  // Canvasはクリックを透過
        this.canvas.style.zIndex = '100'  // iframeより上だが、UIの邪魔にならないように
        this.canvas.style.background = 'transparent'
        this.canvas.id = 'heatmap-canvas'
        console.log('Canvasセットアップ中:', this.canvas)

        // Canvas位置をiframeと同期
        this.updateCanvasPosition()
        this.container.appendChild(this.canvas)
        this.resize()

        console.log('Canvas追加完了:', this.container.querySelector('#heatmap-canvas'))
        window.addEventListener('resize', () => this.resize())
    }

    updateCanvasPosition() {
        if (this.iframe) {
            const iframeRect = this.iframe.getBoundingClientRect()
            const containerRect = this.container.getBoundingClientRect()

            this.canvas.style.left = (iframeRect.left - containerRect.left) + 'px'
            this.canvas.style.top = (iframeRect.top - containerRect.top) + 'px'
            console.log('Canvas位置更新:', this.canvas.style.left, this.canvas.style.top)
        }
    }

    resize() {
        if (this.iframe) {
            // iframe要素のサイズに合わせる
            const iframeRect = this.iframe.getBoundingClientRect()
            this.canvas.width = this.iframe.clientWidth
            this.canvas.height = this.iframe.clientHeight
            this.canvas.style.width = this.iframe.clientWidth + 'px'
            this.canvas.style.height = this.iframe.clientHeight + 'px'
            console.log('Canvas resized to iframe:', this.canvas.width, 'x', this.canvas.height)

            // 位置も更新
            this.updateCanvasPosition()
        } else {
            // fallback: container全体のサイズ
            const rect = this.container.getBoundingClientRect()
            this.canvas.width = rect.width
            this.canvas.height = rect.height
            this.canvas.style.width = rect.width + 'px'
            this.canvas.style.height = rect.height + 'px'
            console.log('Canvas resized to container:', rect.width, 'x', rect.height)
        }
    }

    createGradient() {
        const gradient = this.ctx.createLinearGradient(0, 0, 0, 256)

        for (const [stop, color] of Object.entries(this.options.gradient)) {
            gradient.addColorStop(parseFloat(stop), color)
        }

        this.gradient = gradient
    }


    drawPoint(x, y, value, maxValue) {
        const intensity = value / maxValue
        const radius = this.options.radius
        const opacity = this.options.minOpacity +
                       (intensity * (this.options.maxOpacity - this.options.minOpacity))

        // 放射状グラデーションを作成
        const gradient = this.ctx.createRadialGradient(x, y, 0, x, y, radius)
        gradient.addColorStop(0, `rgba(255, 255, 255, ${opacity})`)
        gradient.addColorStop(1, 'rgba(255, 255, 255, 0)')

        this.ctx.globalCompositeOperation = 'lighter'
        this.ctx.fillStyle = gradient
        this.ctx.beginPath()
        this.ctx.arc(x, y, radius, 0, Math.PI * 2)
        this.ctx.fill()
    }

    applyColorMap() {
        const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height)
        const data = imageData.data

        for (let i = 0; i < data.length; i += 4) {
            const alpha = data[i + 3]
            if (alpha === 0) continue

            const intensity = alpha / 255
            const color = this.getColorForIntensity(intensity)

            data[i] = color.r      // Red
            data[i + 1] = color.g  // Green
            data[i + 2] = color.b  // Blue
            data[i + 3] = alpha    // Alpha
        }

        this.ctx.putImageData(imageData, 0, 0)
    }

    getColorForIntensity(intensity) {
        if (intensity <= 0.2) {
            return { r: 0, g: Math.floor(255 * intensity * 5), b: 255 }
        } else if (intensity <= 0.4) {
            return { r: 0, g: 255, b: Math.floor(255 * (0.4 - intensity) * 5) }
        } else if (intensity <= 0.6) {
            return { r: Math.floor(255 * (intensity - 0.4) * 5), g: 255, b: 0 }
        } else if (intensity <= 0.8) {
            return { r: 255, g: Math.floor(255 * (0.8 - intensity) * 5), b: 0 }
        } else {
            return { r: 255, g: 0, b: 0 }
        }
    }

    clear() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height)
    }

    hide() {
        this.canvas.style.display = 'none'
    }

    show() {
        this.canvas.style.display = 'block'
    }

    toggle() {
        if (this.canvas.style.display === 'none') {
            this.show()
        } else {
            this.hide()
        }
    }

    // iframeのスクロール追跡を設定
    setupScrollTracking() {
        // iframe要素を後で設定できるようにする
        this.findAndTrackIframe()
    }

    findAndTrackIframe() {
        const iframe = document.getElementById('page-iframe')
        if (iframe) {
            this.iframe = iframe
            console.log('iframe発見、スクロール追跡開始')

            iframe.addEventListener('load', () => {
                try {
                    const iframeDoc = iframe.contentDocument || iframe.contentWindow.document
                    const iframeWindow = iframe.contentWindow

                    // iframeのスクロールイベントを監視
                    iframeWindow.addEventListener('scroll', () => {
                        this.updateScrollOffset()
                        this.renderWithScroll()
                    })

                    console.log('iframeスクロール監視設定完了')
                } catch (e) {
                    console.log('iframe内容にアクセスできません（CORS制限）:', e.message)
                    // CORS制限の場合はポーリングを使わず、手動更新のみ
                    console.log('自動ポーリングは無効化されました。手動でデータ更新ボタンを使用してください。')
                }
            })
        }
    }

    updateScrollOffset() {
        if (this.iframe && this.iframe.contentWindow) {
            try {
                const iframeWindow = this.iframe.contentWindow
                this.scrollOffset = {
                    x: iframeWindow.scrollX || 0,
                    y: iframeWindow.scrollY || 0
                }
                console.log('スクロールオフセット更新:', this.scrollOffset)
            } catch (e) {
                console.log('スクロール位置取得エラー:', e.message)
            }
        }
    }

    startPositionPolling() {
        // CORS制限の場合の代替手段 - ポーリング頻度を大幅に下げる
        this.pollingInterval = setInterval(() => {
            if (this.currentHeatmapData) {
                this.render(this.currentHeatmapData)
            }
        }, 5000) // 5秒間隔に変更
        console.log('定期的な位置更新開始（5秒間隔）')
    }

    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval)
            this.pollingInterval = null
            console.log('ポーリング停止')
        }
    }

    renderWithScroll() {
        if (this.currentHeatmapData) {
            this.render(this.currentHeatmapData)
        }
    }

    // データを保存してスクロール連動できるようにする
    render(heatmapData) {
        console.log('ヒートマップrender呼び出し:', heatmapData) // デバッグ用

        this.currentHeatmapData = heatmapData // データを保存

        if (!heatmapData || heatmapData.length === 0) {
            console.log('データなし、クリア実行') // デバッグ用
            this.clear()
            return
        }

        // キャンバスをクリア
        this.clear()
        console.log('Canvasサイズ:', this.canvas.width, 'x', this.canvas.height) // デバッグ用

        // 最大値を計算
        const maxValue = Math.max(...heatmapData.map(point => point.value))
        console.log('最大値:', maxValue) // デバッグ用

        // 各ポイントを描画（スクロールオフセットを考慮）
        heatmapData.forEach(point => {
            const adjustedX = point.x - this.scrollOffset.x
            const adjustedY = point.y - this.scrollOffset.y
            console.log('ポイント描画:', point, '調整後:', adjustedX, adjustedY) // デバッグ用
            this.drawPoint(adjustedX, adjustedY, point.value, maxValue)
        })

        // カラーマップを適用
        this.applyColorMap()
        console.log('ヒートマップrender完了') // デバッグ用
    }
}

// グローバルで利用可能にする
window.HeatmapRenderer = HeatmapRenderer