/**
 * Lightweight, privacy-respecting event wiring for the static /vs/ comparison pages.
 *
 * The Plausible pageview script is already loaded per page (reach + referrer/UTM are
 * captured natively). This adds the custom events those pages need for the funnel:
 *   - command_copied  — the in-page install command was copied (install-intent signal)
 *   - github_clicked  — a click on any GitHub link (the conversion proxy on a vs page)
 *   - compare_clicked — a click to another /vs/ page (cross-comparison navigation)
 *   - consult_clicked — a click on the soft tsukumo discovery-call band (funnel handoff)
 *
 * No cookies, no identifiers, no PII. A delegated listener so it survives any markup,
 * and a no-op if no analytics script is present. location = vs-<page-slug>.
 */
(function () {
  if (typeof window === 'undefined') return

  var seg = location.pathname.replace(/^\/vs\/?/, '').replace(/\/.*$/, '')
  var loc = 'vs-' + (seg || 'index')

  function track(ev, props) {
    if (typeof window.plausible === 'function') window.plausible(ev, { props: props })
  }

  document.addEventListener(
    'click',
    function (e) {
      var t = e.target

      // Copy-to-clipboard for the in-page install command (vanilla CopyCmd twin).
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
      if (!a) return
      var href = a.getAttribute('href') || ''
      if (/github\.com/i.test(href)) track('github_clicked', { location: loc })
      else if (/calendly\.com/i.test(href) || a.hasAttribute('data-consult')) track('consult_clicked', { location: loc })
      else if (href === '/vs/' || /^\/vs\//.test(href)) track('compare_clicked', { location: loc })
    },
    true,
  )
})()
