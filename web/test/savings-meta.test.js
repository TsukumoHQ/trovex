/**
 * /api/savings rewrites og/twitter meta on a shared link. The injected value is
 * HTML-attribute-escaped — these tests pin that boundary so a crafted value can't
 * break out of content="" and inject markup. See setMeta in api/savings.js.
 */
import { describe, expect, it } from 'vitest'
import { setMeta } from '../api/savings.js'

const tag = (sel) => `<meta property="${sel}" content="old" />`

describe('setMeta', () => {
  it('replaces the content of the matching meta tag', () => {
    const out = setMeta(tag('og:title'), 'property="og:title"', 'new title')
    expect(out).toContain('content="new title"')
    expect(out).not.toContain('content="old"')
  })

  it('escapes quotes so a value cannot break out of the attribute', () => {
    const evil = '"><script>alert(1)</script>'
    const out = setMeta(tag('og:title'), 'property="og:title"', evil)
    expect(out).not.toContain('<script>')
    expect(out).toContain('&quot;&gt;&lt;script&gt;')
  })

  it('escapes ampersands and angle brackets', () => {
    const out = setMeta(tag('og:description'), 'property="og:description"', 'a & b < c > d')
    expect(out).toContain('content="a &amp; b &lt; c &gt; d"')
  })

  it('leaves the html untouched when no matching tag exists', () => {
    const html = '<meta name="other" content="x" />'
    expect(setMeta(html, 'property="og:title"', 'new')).toBe(html)
  })
})
