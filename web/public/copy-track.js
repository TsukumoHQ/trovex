/**
 * Shared copy-to-clipboard + analytics for the static GEO discovery pages
 * (/answers/*, /glossary/*). Vanilla twin of the landing's CopyCmd and of
 * /vs/track.js — a delegated listener so it survives any markup, a no-op if no
 * analytics script is present. No cookies, no identifiers, no PII.
 *
 *   - command_copied — the in-page install command was copied (install-intent
 *     signal). location = <section>-<slug>, e.g. answers-reduce-agent-token-costs
 *     or glossary-canonical-doc.
 *   - github_clicked — a click on any GitHub link (conversion proxy).
 *   - consult_clicked — a click on the soft tsukumo discovery-call band (funnel handoff).
 *
 * One file, both sections: a dev arriving from an AI-engine citation can install
 * in place instead of bouncing to the landing. Section + slug are derived from
 * the path, so the same file works on every discovery page.
 */
(function () {
  if (typeof window === 'undefined') return

  var parts = location.pathname.replace(/^\/+/, '').split('/')
  var section = parts[0] || 'index' // answers | glossary | …
  var slug = parts[1] || 'index'
  var loc = section + '-' + slug

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
      if (!a) return
      var href = a.getAttribute('href') || ''
      if (/github\.com/i.test(href)) track('github_clicked', { location: loc })
      else if (/calendly\.com/i.test(href) || a.hasAttribute('data-consult')) track('consult_clicked', { location: loc })
    },
    true,
  )
})()
