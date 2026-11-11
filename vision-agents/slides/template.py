"""The 16:9 slide design, rendered by headless Chromium.

Palette and type come straight from the product theme
(``src/app/globals.css`` + ``public/logo.svg``):

    brand green   #17CF97
    background    near-black with a faint green cast
    text          soft white
    headings      Lato     body  Nunito
"""

TEMPLATE_HTML = r"""<!doctype html>
<html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Lato:wght@400;700;900&family=Nunito:wght@400;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
<script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
<style>
  :root {
    --bg:      #0a0e0d;   /* near-black, faint green cast          */
    --surface: #121917;
    --border:  #22302c;
    --fg:      #eaf2ef;   /* soft white                            */
    --muted:   #8ca09a;
    --accent:  #17cf97;   /* Miva brand green                      */
    --font-body:    Nunito, "Segoe UI", system-ui, sans-serif;
    --font-heading: Lato, Nunito, "Segoe UI", system-ui, sans-serif;
  }
  * { box-sizing:border-box; margin:0; padding:0; }
  html,body { width:1920px; height:1080px; overflow:hidden; }
  body { background:var(--bg); color:var(--fg); font-family:var(--font-body); }

  #stage { position:relative; width:100%; height:100%; padding:76px 100px 84px;
           display:flex; flex-direction:column; gap:26px; overflow:hidden;
           background:
             radial-gradient(1200px 620px at 8% -14%, rgba(23,207,151,.16), transparent 62%),
             radial-gradient(900px 520px at 114% 120%, rgba(23,207,151,.07), transparent 62%),
             var(--bg); }
  #stage::after { content:""; position:absolute; inset:0; pointer-events:none;
    background-image:linear-gradient(rgba(23,207,151,.045) 1px, transparent 1px),
                     linear-gradient(90deg, rgba(23,207,151,.045) 1px, transparent 1px);
    background-size:80px 80px; }
  .kicker { font-family:var(--font-heading); font-size:25px; letter-spacing:.16em;
            text-transform:uppercase; color:var(--accent); font-weight:700; }
  .title  { font-family:var(--font-heading); font-size:76px; line-height:1.06;
            letter-spacing:-.02em; font-weight:900; }
  .body   { flex:1; display:grid; gap:60px; min-height:0; align-items:center;
            position:relative; z-index:1; }
  .body.split { grid-template-columns:0.85fr 1.15fr; }
  .body.stack { grid-template-columns:1fr; }
  /* a photo beside the text, or a full-width photo with no text */
  .body.media { grid-template-columns:0.78fr 1.22fr; align-items:stretch; gap:52px; }
  .body.media ul.bullets li { font-size:32px; }
  .body.solo  { grid-template-columns:1fr; align-items:stretch; }

  ul.bullets { list-style:none; display:flex; flex-direction:column; gap:26px; }
  ul.bullets li { font-size:36px; line-height:1.3; padding-left:44px; position:relative;
                  color:#dce8e4; }
  ul.bullets li::before { content:""; position:absolute; left:0; top:.42em;
                          width:15px; height:15px; border-radius:5px; background:var(--accent); }

  .visual { display:flex; align-items:center; justify-content:center; height:100%;
            min-width:0; overflow:hidden; }
  .visual.math { font-size:62px; }
  /* Mermaid writes an inline max-width on its <svg>; override it so diagrams
     scale up to fill the stage instead of rendering at their natural size. */
  .visual svg { width:100% !important; height:100% !important;
                max-width:100% !important; max-height:100% !important; }
  .katex-display { margin:0; }

  pre.code { width:100%; background:#0d1311; border:1px solid var(--border);
             border-radius:20px; padding:30px 34px;
             font-family:"Cascadia Code","JetBrains Mono",Consolas,monospace;
             font-size:27px; line-height:1.5; white-space:pre-wrap; overflow:hidden; }
  pre.code b { color:var(--accent); font-weight:400; }

  /* ---------- a real photograph ---------- */
  figure.shot { position:relative; display:flex; align-items:center; justify-content:center;
                min-width:0; min-height:0; height:100%; overflow:hidden;
                border:1px solid var(--border); border-radius:24px;
                background:#0b110f; box-shadow:0 34px 80px rgba(0,0,0,.5); }
  figure.shot img { width:100%; height:100%; object-fit:cover; display:block; }
  .body.solo figure.shot { width:fit-content; max-width:100%; margin:0 auto; }
  .body.solo figure.shot img { width:auto; max-width:100%; height:100%; object-fit:contain; }
  figure.shot figcaption { position:absolute; left:0; right:0; bottom:0;
                           padding:46px 22px 15px; font-size:17px; line-height:1.35;
                           background:linear-gradient(transparent, rgba(5,9,8,.88));
                           color:#c6d6d1; text-align:right; }

  .caption { font-size:24px; color:var(--muted); }
  .footer  { display:flex; justify-content:space-between; align-items:center;
             font-size:22px; color:var(--muted); position:relative; z-index:1; }
  .footer svg { width:24px; height:24px; display:block; }
  .brand { display:flex; align-items:center; gap:12px; color:var(--fg); font-weight:600; }

  /* ---------- idle: the branded "listening" card ---------- */
  #stage.idle { align-items:center; justify-content:center; text-align:center; gap:30px; }
  #stage.idle .title { font-size:104px; letter-spacing:-.03em; }
  #stage.idle .kicker { font-size:23px; }
  #stage.idle .body { display:block; flex:0 0 auto; }
  #stage.idle .logo { width:150px; height:150px; margin:0 auto; }
  #stage.idle .footer { position:absolute; left:100px; right:100px; bottom:84px; }
</style>
</head><body>
<div id="stage">
  <p class="kicker" id="kicker"></p>
  <h1 class="title" id="title"></h1>
  <div class="body" id="body"></div>
  <div class="footer">
    <span id="caption"></span>
    <span class="brand">
      <svg viewBox="0 0 49 48" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <path d="M24.5 12.75C24.5 18.9632 19.4632 24 13.25 24H2V12.75C2 6.53679 7.03679 1.5 13.25 1.5C19.4632 1.5 24.5 6.53679 24.5 12.75Z" fill="#17CF97"/>
        <path d="M24.5 35.25C24.5 29.0368 29.5368 24 35.75 24H47V35.25C47 41.4632 41.9632 46.5 35.75 46.5C29.5368 46.5 24.5 41.4632 24.5 35.25Z" fill="#17CF97"/>
        <path d="M2 35.25C2 41.4632 7.03679 46.5 13.25 46.5H24.5V35.25C24.5 29.0368 19.4632 24 13.25 24C7.03679 24 2 29.0368 2 35.25Z" fill="#17CF97"/>
        <path d="M47 12.75C47 6.53679 41.9632 1.5 35.75 1.5H24.5V12.75C24.5 18.9632 29.5368 24 35.75 24C41.9632 24 47 18.9632 47 12.75Z" fill="#17CF97"/>
      </svg>
      Miva AI
    </span>
  </div>
</div>

<script type="module">
  try {
    const mod = await import("https://cdn.jsdelivr.net/npm/mermaid@12/dist/mermaid.esm.min.mjs");
    const mermaid = mod.default ?? mod;
    mermaid.initialize({
      startOnLoad: false, securityLevel: "strict", layout: "elk", math: true,
      theme: "base", maxTextSize: 20000, maxEdges: 120,
      themeVariables: {
        background: "#0a0e0d",
        primaryColor: "#13201c",
        primaryTextColor: "#eaf2ef",
        primaryBorderColor: "#2c3f38",
        lineColor: "#6e8c82",
        textColor: "#eaf2ef",
        secondaryColor: "#182722",
        secondaryTextColor: "#eaf2ef",
        tertiaryColor: "#0d1311",
        tertiaryTextColor: "#eaf2ef",
        edgeLabelBackground: "#0a0e0d",
        clusterBkg: "#101816",
        clusterBorder: "#22302c",
        fontSize: "22px",
        fontFamily: "Lato, Nunito, Segoe UI, sans-serif"
      }
    });
    window.mermaid = mermaid;
    await document.fonts.ready;
    window.__ready = true;
  } catch (e) {
    window.__bootError = String(e);
  }
</script>

<script>
  let seq = 0;
  const LOGO =
    '<svg viewBox="0 0 49 48" fill="none" xmlns="http://www.w3.org/2000/svg">' +
    '<path d="M24.5 12.75C24.5 18.9632 19.4632 24 13.25 24H2V12.75C2 6.53679 7.03679 1.5 13.25 1.5C19.4632 1.5 24.5 6.53679 24.5 12.75Z" fill="#17CF97"/>' +
    '<path d="M24.5 35.25C24.5 29.0368 29.5368 24 35.75 24H47V35.25C47 41.4632 41.9632 46.5 35.75 46.5C29.5368 46.5 24.5 41.4632 24.5 35.25Z" fill="#17CF97"/>' +
    '<path d="M2 35.25C2 41.4632 7.03679 46.5 13.25 46.5H24.5V35.25C24.5 29.0368 19.4632 24 13.25 24C7.03679 24 2 29.0368 2 35.25Z" fill="#17CF97"/>' +
    '<path d="M47 12.75C47 6.53679 41.9632 1.5 35.75 1.5H24.5V12.75C24.5 18.9632 29.5368 24 35.75 24C41.9632 24 47 18.9632 47 12.75Z" fill="#17CF97"/>' +
    '</svg>';

  const mk = (tag, cls, text) => { const e = document.createElement(tag);
    if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

  window.renderSlide = async (spec) => {
    const warnings = [];
    const stage = document.getElementById("stage");
    const body = document.getElementById("body");

    stage.className = spec.layout === "idle" ? "idle" : "";
    document.getElementById("kicker").textContent = spec.kicker || "";
    document.getElementById("title").textContent = spec.title || "";
    document.getElementById("caption").textContent = spec.caption || "";
    body.innerHTML = "";
    body.className = "body";

    // ---- idle card: logo, agent name, nothing else ----
    if (spec.layout === "idle") {
      const logo = mk("div", "logo");
      logo.innerHTML = LOGO;
      body.appendChild(logo);
      await document.fonts.ready;
      await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
      return warnings;
    }

    const hasImage = !!spec.image;
    const hasVisual = !!(spec.mermaid || spec.latex || spec.code);
    const columns = hasImage
      ? (spec.bullets.length ? "media" : "solo")
      : (hasVisual && spec.bullets.length ? "split" : "stack");
    body.className = "body " + columns;

    if (spec.bullets.length) {
      const ul = mk("ul", "bullets");
      spec.bullets.forEach(b => ul.appendChild(mk("li", null, b)));
      body.appendChild(ul);
    }

    if (hasImage) {
      const figure = mk("figure", "shot");
      const img = document.createElement("img");
      img.alt = spec.title || "Illustration";
      img.decoding = "sync";
      img.src = spec.image;
      figure.appendChild(img);
      if (spec.credit) figure.appendChild(mk("figcaption", null, spec.credit));
      body.appendChild(figure);
      // The screenshot must not happen before the photo has painted.
      try {
        if (img.decode) await img.decode();
        else await new Promise((resolve, reject) => {
          img.onload = resolve; img.onerror = reject;
        });
      } catch (e) {
        figure.remove();
        if (!spec.bullets.length) body.className = "body stack";
        warnings.push("image: " + (e && e.message ? e.message : "could not load"));
      }
    } else if (hasVisual) {
      const v = mk("div", "visual");
      body.appendChild(v);

      if (spec.mermaid) {
        try {
          await window.mermaid.parse(spec.mermaid);
          const { svg } = await window.mermaid.render("d" + (++seq), spec.mermaid);
          v.innerHTML = svg;
        } catch (e) {
          warnings.push("mermaid: " + e.message);
          v.appendChild(mk("pre", "code", spec.mermaid));
        }
      } else if (spec.latex) {
        v.classList.add("math");
        try {
          katex.render(spec.latex, v, { throwOnError: true, displayMode: true });
          // Shrink the formula until it fits the column instead of overflowing.
          let size = 62;
          v.style.fontSize = size + "px";
          while (
            size > 22 &&
            (v.scrollWidth > v.clientWidth || v.scrollHeight > v.clientHeight)
          ) {
            size -= 4;
            v.style.fontSize = size + "px";
          }
        } catch (e) {
          warnings.push("katex: " + e.message);
          v.appendChild(mk("pre", "code", spec.latex));
        }
      } else if (spec.code) {
        v.appendChild(mk("pre", "code", spec.code));
      }
    }

    await document.fonts.ready;
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    return warnings;
  };
</script>
</body></html>
"""
