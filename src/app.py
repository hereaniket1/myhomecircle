from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

PAGE = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>myhomecircle</title>
    <style>
      :root { color-scheme: dark; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }
      body { margin: 0; min-height: 100vh; background: linear-gradient(180deg, #0b1020, #050816); color: #eef2ff; display: grid; place-items: center; padding: 24px; }
      main { width: min(720px, 100%); background: rgba(10,15,33,.82); border: 1px solid rgba(255,255,255,.1); border-radius: 24px; padding: 32px; box-shadow: 0 30px 90px rgba(0,0,0,.35); }
      h1 { margin: 0 0 12px; font-size: clamp(2.5rem, 6vw, 4.5rem); line-height: .95; }
      p { line-height: 1.7; color: #cbd5e1; }
      code { display: inline-block; margin-top: 16px; padding: 10px 12px; border-radius: 12px; background: rgba(148,163,184,.12); }
      button { margin-top: 16px; border: 0; border-radius: 999px; padding: 12px 18px; background: #60a5fa; color: #08111f; font-weight: 700; cursor: pointer; }
      .row { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; }
      .pill { font-size: .85rem; color: #93c5fd; text-transform: uppercase; letter-spacing: .16em; }
      #out { margin-top: 16px; }
    </style>
  </head>
  <body>
    <main>
      <div class="pill">Flask + Render + Postgres ready</div>
      <h1>myhomecircle</h1>
      <p>A tiny single-page app scaffold. This keeps deployment simple: one Flask app, one requirements file, one database URL.</p>
      <div class="row">
        <button onclick="loadHealth()">Check API</button>
        <code>/api/health</code>
      </div>
      <div id="out"></div>
    </main>
    <script>
      async function loadHealth() {
        const out = document.getElementById('out');
        out.textContent = 'Loading...';
        try {
          const res = await fetch('/api/health');
          const data = await res.json();
          out.textContent = JSON.stringify(data, null, 2);
        } catch (e) {
          out.textContent = 'API request failed';
        }
      }
    </script>
  </body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.get("/api/health")
def health():
    return jsonify(status="ok")


@app.get("/api/echo")
def echo():
    return jsonify(message=request.args.get("message", "hello from myhomecircle"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
