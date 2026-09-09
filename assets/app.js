// ユーチューブ一覧 — data/videos.json を読み込んで動画を一覧表示する

const CH_KEY = 'yi-channel'
const SORT_KEY = 'yi-sort'
const JST_OFFSET_MIN = 9 * 60

const state = {
  videos: [],
  channels: [],
  channel: '', // 選択中の channel_id（'' = すべて）
  sort: 'published', // 'published' | 'views'
}

const els = {
  updated: document.getElementById('updated'),
  channel: document.getElementById('channel-select'),
  sort: document.getElementById('sort-select'),
  list: document.getElementById('list'),
  count: document.getElementById('count'),
  empty: document.getElementById('empty'),
  error: document.getElementById('error'),
}

async function loadData() {
  const res = await fetch(`data/videos.json?ts=${Date.now()}`, { cache: 'no-store' })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

const pad = (n) => String(n).padStart(2, '0')

// UTC の Date を JST の年月日時分に変換
function toJstParts(date) {
  const s = new Date(date.getTime() + JST_OFFSET_MIN * 60000)
  return {
    y: s.getUTCFullYear(),
    mo: s.getUTCMonth() + 1,
    d: s.getUTCDate(),
    h: s.getUTCHours(),
    mi: s.getUTCMinutes(),
  }
}

function formatWhen(iso) {
  const dt = new Date(iso)
  if (Number.isNaN(dt.getTime())) return ''
  const min = Math.floor((Date.now() - dt.getTime()) / 60000)
  if (min < 1) return 'たった今'
  if (min < 60) return `${min}分前`
  if (min < 1440) return `${Math.floor(min / 60)}時間前`
  const days = Math.floor(min / 1440)
  if (days < 7) return `${days}日前`
  const p = toJstParts(dt)
  return p.y === new Date().getFullYear()
    ? `${p.mo}/${p.d}`
    : `${p.y}/${p.mo}/${p.d}`
}

function formatViews(n) {
  if (typeof n !== 'number' || !Number.isFinite(n)) return '再生回数不明'
  if (n >= 1e8) return `${trimNum(n / 1e8)}億回`
  if (n >= 1e4) return `${trimNum(n / 1e4)}万回`
  return `${n.toLocaleString('ja-JP')}回`
}

function trimNum(x) {
  const rounded = x >= 100 ? Math.round(x) : Math.round(x * 10) / 10
  return String(rounded)
}

function formatUpdated(iso) {
  if (!iso) return 'データ取得前'
  const dt = new Date(iso)
  if (Number.isNaN(dt.getTime())) return ''
  const p = toJstParts(dt)
  return `最終更新 ${p.y}/${p.mo}/${p.d} ${pad(p.h)}:${pad(p.mi)}`
}

const span = (t) => {
  const s = document.createElement('span')
  s.textContent = t
  return s
}
const dotSep = () => {
  const s = document.createElement('span')
  s.className = 'dot'
  s.textContent = '・'
  return s
}

function card(v) {
  const el = document.createElement('article')
  el.className = 'card'

  const thumbLink = document.createElement('a')
  thumbLink.className = 'card__thumb-link'
  thumbLink.href = v.url
  thumbLink.target = '_blank'
  thumbLink.rel = 'noopener'
  const img = document.createElement('img')
  img.className = 'card__thumb'
  img.src = v.thumbnail || `https://i.ytimg.com/vi/${v.video_id}/hqdefault.jpg`
  img.alt = ''
  img.loading = 'lazy'
  img.referrerPolicy = 'no-referrer'
  thumbLink.appendChild(img)
  el.appendChild(thumbLink)

  const body = document.createElement('div')
  body.className = 'card__body'

  const title = document.createElement('a')
  title.className = 'card__title'
  title.href = v.url
  title.target = '_blank'
  title.rel = 'noopener'
  title.textContent = v.title || '(無題)'
  body.appendChild(title)

  const meta = document.createElement('p')
  meta.className = 'card__meta'
  meta.append(
    span(v.channel || ''),
    dotSep(),
    span(formatWhen(v.published_at)),
    dotSep(),
    span(formatViews(v.views)),
  )
  body.appendChild(meta)

  el.appendChild(body)
  return el
}

function render() {
  const items = state.channel
    ? state.videos.filter((v) => v.channel_id === state.channel)
    : state.videos.slice()

  items.sort((a, b) => {
    if (state.sort === 'views') {
      const av = typeof a.views === 'number' ? a.views : -1
      const bv = typeof b.views === 'number' ? b.views : -1
      if (bv !== av) return bv - av
    }
    return (b.published_at || '').localeCompare(a.published_at || '')
  })

  els.list.replaceChildren(...items.map(card))
  els.empty.hidden = items.length > 0
  els.count.hidden = items.length === 0
  els.count.textContent = `${items.length} 本`
}

function fillChannels() {
  const list = state.channels
    .slice()
    .sort((a, b) => (a.name || '').localeCompare(b.name || '', 'ja'))
  for (const c of list) {
    const opt = document.createElement('option')
    opt.value = c.channel_id
    opt.textContent = c.name || c.channel_id
    els.channel.appendChild(opt)
  }
}

const safeGet = (k) => {
  try {
    return localStorage.getItem(k)
  } catch {
    return null
  }
}
const safeSet = (k, v) => {
  try {
    localStorage.setItem(k, v)
  } catch {
    /* localStorage 不可でも動作は継続 */
  }
}

function setupControls() {
  els.channel.addEventListener('change', () => {
    state.channel = els.channel.value
    safeSet(CH_KEY, state.channel)
    render()
  })
  els.sort.addEventListener('change', () => {
    state.sort = els.sort.value === 'views' ? 'views' : 'published'
    safeSet(SORT_KEY, state.sort)
    render()
  })
}

async function main() {
  state.channel = safeGet(CH_KEY) || ''
  state.sort = safeGet(SORT_KEY) === 'views' ? 'views' : 'published'
  els.sort.value = state.sort
  setupControls()

  try {
    const data = await loadData()
    state.videos = Array.isArray(data.videos) ? data.videos : []
    state.channels = Array.isArray(data.channels) ? data.channels : []
    fillChannels()

    // 保存済みの選択チャンネルが今の一覧に無ければ「すべて」に戻す
    if (
      state.channel &&
      !state.channels.some((c) => c.channel_id === state.channel)
    ) {
      state.channel = ''
    }
    els.channel.value = state.channel

    els.updated.textContent = formatUpdated(data.updated_at)
    render()
  } catch (err) {
    console.error(err)
    els.updated.textContent = ''
    els.error.hidden = false
  }
}

main()
