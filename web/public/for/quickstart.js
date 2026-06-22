/**
 * Copy-to-clipboard + analytics for the static /for/ quickstart pages.
 *
 * Static /for pages have no React; this is the vanilla equivalent of the landing's
 * CopyCmd. A delegated listener so it survives any markup and is a no-op if no
 * analytics script is present. No cookies, no identifiers, no PII.
 *   - command_copied — a quickstart command was copied (the install-intent signal)
 *   - github_clicked — a click on any GitHub link (conversion proxy)
 * location = for-<page-slug> (e.g. for-claude-code).
 */
(function () {
  if (typeof window === 'undefined') return

  var seg = location.pathname.replace(/^\/for\/?/, '').replace(/\/.*$/, '')
  var loc = 'for-' + (seg || 'index')

  function track(ev, props) {
    if (typeof window.plausible === 'function') window.plausible(ev, { props: props })
  }

  document.addEventListener(
    'click',
    function (e) {
      var t = e.target
      var btn = t && t.closest ? t.closest('[data-copy]') : null
      if (btn) {
        var text = btn.getAttribute('data-copy')
        if (text && navigator.clipboard) {
          navigator.clipboard.writeText(text).then(
            function () {
              var prev = btn.getAttribute('data-label') || 'copy'
              btn.textContent = 'copied'
              setTimeout(function () { btn.textContent = prev }, 1500)
              track('command_copied', { location: loc, command: btn.getAttribute('data-cmd') || 'cmd' })
            },
            function () {} // clipboard blocked — no-op; the command is still selectable
          )
        }
        return
      }
      var a = t && t.closest ? t.closest('a[href]') : null
      if (a && /github\.com/i.test(a.getAttribute('href') || '')) {
        track('github_clicked', { location: loc })
      }
    },
    true,
  )
})()
