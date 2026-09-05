// Prepends http:// to a scheme-less "host:port" value. Needed because
// Render's fromService (render.yaml) resolves CORE_URL/INGEST_URL to a
// private-network "host:port" with no scheme -- fetch()/new URL() both
// need one. Values already carrying a scheme (local dev's 127.0.0.1
// default, or a plain https:// URL) pass through unchanged. Shared between
// index.js and consent.js -- both read these env vars independently.
function withScheme(url) {
  return /^https?:\/\//.test(url) ? url : `http://${url}`;
}

module.exports = { withScheme };
