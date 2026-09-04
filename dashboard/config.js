// Deployed-core-URL injection point. Loaded before tickets.js, which reads
// window.NIDAA_CORE_URL if set (falling back to same-origin or 127.0.0.1:8000
// otherwise -- see tickets.js). Left empty here on purpose: local/file://
// dev needs no change. Render's dashboard static-site build command
// overwrites this file with the real deployed core URL before publishing
// (see render.yaml) -- nothing here needs editing by hand.
window.NIDAA_CORE_URL = window.NIDAA_CORE_URL || "";
