"""Servidor LAN embebido: sirve el checklist al celular del operario.

Corre dentro de la app PySide6 (hilo daemon) con werkzeug; los QR de las
estaciones apuntan a http://IP-del-PC:8080/<CODIGO_MAQUINA>. Cada request
abre su propia conexión SQLite (WAL ya está activo en la BD).
"""
from __future__ import annotations

import socket
import threading
from pathlib import Path

from flask import Flask, abort, request

from ..core import checklists, db
from ..core.db import TURNOS

PUERTO = 8080

# --------------------------------------------------------------------------- HTML
_CSS = """
:root{--teal:#0D9488;--teal-soft:#CCFBF1;--ink:#0F172A;--muted:#64748B;
--line:#E2E8F0;--amber-soft:#FEF3C7;--red:#EF4444;--red-soft:#FEE2E2;
--green:#22C55E;--green-soft:#DCFCE7;--amber:#B45309;--redink:#B91C1C;--greenink:#15803D}
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,"Segoe UI",Roboto,sans-serif}
body{background:#F1F5F9;color:var(--ink);font-size:15px;-webkit-tap-highlight-color:transparent}
.wrap{max-width:430px;margin:0 auto;padding:14px 14px 110px}
.head{background:#fff;border-radius:16px;padding:15px 16px;margin-bottom:12px;
box-shadow:0 1px 3px rgba(15,23,42,.09)}
.head h1{font-size:17px;font-weight:800}
.head p{font-size:12.5px;color:var(--muted);margin-top:3px}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.chip{font-size:11.5px;font-weight:700;background:#F1F5F9;border:1px solid var(--line);
border-radius:99px;padding:4px 10px;color:#475569}
select{width:100%;font-size:14px;font-weight:600;padding:11px 12px;margin-top:10px;
border:1.5px solid var(--line);border-radius:12px;background:#fff;color:var(--ink);appearance:auto}
.prog{display:flex;justify-content:space-between;font-size:12.5px;font-weight:700;
color:#0F766E;background:var(--teal-soft);border-radius:12px;padding:10px 14px;margin-bottom:12px}
.item{background:#fff;border-radius:16px;padding:14px;margin-bottom:10px;
box-shadow:0 1px 3px rgba(15,23,42,.09)}
.item .lbl{font-size:14.5px;font-weight:600;line-height:1.35;margin-bottom:10px}
.seg{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.seg button{font-size:14px;font-weight:800;padding:13px;border-radius:12px;
border:1.6px solid var(--line);background:#fff;color:var(--muted);cursor:pointer}
.seg .ok{background:var(--green-soft);border-color:var(--green);color:var(--greenink)}
.seg .fa{background:var(--red-soft);border-color:var(--red);color:var(--redink)}
.det{margin-top:11px;border-top:1px dashed var(--line);padding-top:11px;display:none;
flex-direction:column;gap:10px}
.det.on{display:flex}
.det .t{font-size:11.5px;font-weight:700;color:var(--muted)}
.sev{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}
.sev button{font-size:12px;font-weight:800;padding:10px 4px;border-radius:11px;
border:1.6px solid var(--line);background:#fff;color:var(--muted);cursor:pointer}
.sev .l{background:#E0F2FE;border-color:#0EA5E9;color:#0369A1}
.sev .m{background:var(--amber-soft);border-color:#F59E0B;color:var(--amber)}
.sev .c{background:var(--red-soft);border-color:var(--red);color:var(--redink)}
.foto{display:flex;align-items:center;gap:10px;border:1.6px dashed #CBD5E1;border-radius:12px;
padding:11px;background:#F8FAFC;font-size:13px;font-weight:600;color:#475569;width:100%;cursor:pointer}
.foto.has{border-style:solid;border-color:var(--green);background:var(--green-soft);color:var(--greenink)}
.foto input{display:none}
textarea{width:100%;font-family:inherit;font-size:13.5px;border:1.6px solid var(--line);
border-radius:12px;padding:10px;resize:none;height:60px}
.nota{font-size:11.5px;color:#6D28D9;font-weight:700}
footer{position:fixed;bottom:0;left:0;right:0;padding:14px 16px 20px;
background:linear-gradient(180deg,rgba(241,245,249,0),#F1F5F9 32%)}
footer .in{max-width:430px;margin:0 auto}
button.save{width:100%;font-size:16px;font-weight:800;color:#fff;background:var(--teal);
border:none;border-radius:14px;padding:16px;cursor:pointer;box-shadow:0 8px 20px -6px rgba(13,148,136,.5)}
button.save:disabled{background:#94A3B8;box-shadow:none}
.exito{text-align:center;padding:40px 8px}
.exito .ico{width:74px;height:74px;margin:0 auto 14px;border-radius:50%;
background:var(--green-soft);display:flex;align-items:center;justify-content:center}
.exito h1{font-size:20px;margin-bottom:8px}
.exito p{font-size:13.5px;color:var(--muted);line-height:1.55}
.mini{background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px;
margin:18px 0;font-size:13px;text-align:left;line-height:1.6}
.error{background:var(--red-soft);color:var(--redink);border-radius:14px;padding:16px;
font-size:14px;font-weight:600;margin:20px 0}
a.ini{display:inline-block;margin-top:10px;color:var(--teal);font-weight:700;text-decoration:none}
"""

_SVG_CHECK = ('<svg width="38" height="38" viewBox="0 0 24 24" fill="none" '
              'stroke="#15803D" stroke-width="2.4" stroke-linecap="round" '
              'stroke-linejoin="round"><path d="M21.8 10A10 10 0 1 1 17 3.34"/>'
              '<path d="m9 11 3 3L22 4"/></svg>')
_SVG_CAM = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" '
            'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            'stroke-linejoin="round"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16'
            'a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>')

_JS = """
document.querySelectorAll('.item').forEach(it => {
  const ok = it.querySelector('[data-v=ok]'), fa = it.querySelector('[data-v=falla]');
  const det = it.querySelector('.det');
  [ok, fa].forEach(b => b.addEventListener('click', () => {
    ok.classList.toggle('ok', b === ok);
    fa.classList.toggle('fa', b === fa);
    it.dataset.estado = b.dataset.v;
    if (det) det.classList.toggle('on', b === fa);
    progreso();
  }));
  it.querySelectorAll('.sev button').forEach(s => s.addEventListener('click', () => {
    it.querySelectorAll('.sev button').forEach(x => x.classList.remove('l','m','c'));
    s.classList.add(s.dataset.k);
    it.dataset.sev = s.dataset.sev;
  }));
});
function progreso(){
  const tot = document.querySelectorAll('.item').length;
  const hechas = document.querySelectorAll('.item[data-estado]:not([data-estado=""])').length;
  const fallas = document.querySelectorAll('.item[data-estado=falla]').length;
  document.getElementById('prog').textContent = hechas + ' de ' + tot + ' verificados';
  document.getElementById('progfa').textContent = fallas ? fallas + ' con falla' : 'sin fallas por ahora';
  document.querySelector('button.save').disabled = hechas < tot;
}
document.querySelectorAll('.foto').forEach(f => {
  const inp = f.querySelector('input');
  inp.addEventListener('change', () => {
    if (inp.files.length) { f.classList.add('has');
      f.querySelector('.tx').textContent = inp.files[0].name + ' adjuntada'; }
  });
});
document.querySelector('button.save').addEventListener('click', async () => {
  const btn = document.querySelector('button.save');
  btn.disabled = true; btn.textContent = 'Guardando…';
  try {
    const fd = new FormData();
    fd.append('turno', document.getElementById('turno').value);
    fd.append('operario', document.getElementById('operario').value);
    let falta_foto = false;
    const comprimir = async (file) => {   // redimensiona en el celular antes de subir
      if (!/^image\\//.test(file.type)) return file;
      try {
        const img = await createImageBitmap(file);
        const max = 1280, esc = Math.min(1, max / Math.max(img.width, img.height));
        const c = document.createElement('canvas');
        c.width = Math.round(img.width * esc); c.height = Math.round(img.height * esc);
        c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
        return await new Promise(r => c.toBlob(r, 'image/jpeg', 0.82));
      } catch (e) { return file; }
    };
    const items = document.querySelectorAll('.item');
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      const est = it.dataset.estado; if (!est) continue;
      fd.append('item_' + i, it.querySelector('.lbl').textContent.trim());
      fd.append('estado_' + i, est);
      if (est === 'falla') {
        fd.append('sev_' + i, it.dataset.sev || 'Moderada');
        fd.append('com_' + i, (it.querySelector('textarea') || {}).value || '');
        const input = it.querySelector('.foto input');
        if (input && input.files.length) {
          fd.append('foto_' + i, await comprimir(input.files[0]), 'evidencia.jpg');
        } else falta_foto = true;
      }
    }
    if (falta_foto) {
      alert('Cada ítem con FALLA necesita su foto de evidencia.');
      btn.disabled = false; btn.textContent = 'Guardar checklist'; return;
    }
    const r = await fetch(location.href + '/guardar', {method: 'POST', body: fd});
    if (!r.ok) throw new Error('http ' + r.status);
    document.body.innerHTML = await r.text();
    window.scrollTo(0, 0);
  } catch (e) {
    alert('No se pudo guardar. Intenta de nuevo.');
    btn.disabled = false; btn.textContent = 'Guardar checklist';
  }
});
progreso();
"""


def _pagina(titulo: str, cuerpo: str, extra_head: str = "") -> str:
    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{titulo}</title><style>{_CSS}</style>{extra_head}</head>
<body><div class="wrap">{cuerpo}</div></body></html>"""


def _html_formulario(maquina: str) -> str:
    conn = db.conectar()
    try:
        m = conn.execute("SELECT * FROM maquinas WHERE codigo = ?", (maquina,)).fetchone()
        if not m:
            abort(404)
        items = checklists.items_de_maquina(conn, maquina)
        operarios = [r["nombre"] for r in conn.execute(
            "SELECT nombre FROM operarios WHERE area = ? ORDER BY nombre", (m["area"],))]
    finally:
        conn.close()
    if not operarios:
        operarios = [r["nombre"] for r in conn.execute("SELECT nombre FROM operarios ORDER BY nombre")]

    opciones_turno = "".join(f'<option{" selected" if t == "Tarde" else ""}>{t}</option>' for t in TURNOS)
    opciones_op = "".join(f"<option>{o}</option>" for o in operarios)
    tarjetas_html = "".join(f"""
      <div class="item" data-estado="">
        <div class="lbl">{item}</div>
        <div class="seg">
          <button type="button" data-v="ok">OK</button>
          <button type="button" data-v="falla">FALLA</button>
        </div>
        <div class="det">
          <span class="t">Severidad de la anomalía</span>
          <div class="sev">
            <button type="button" data-sev="Leve" data-k="l">Leve</button>
            <button type="button" data-sev="Moderada" data-k="m">Moderada</button>
            <button type="button" data-sev="Crítica" data-k="c">Crítica</button>
          </div>
          <label class="foto">{_SVG_CAM}<span class="tx">Tomar foto de evidencia (obligatorio)</span>
            <input type="file" accept="image/*" capture="environment"></label>
          <textarea placeholder="¿Qué observaste? (opcional)"></textarea>
          <span class="nota">→ al guardar se generará la Tarjeta TPM automáticamente</span>
        </div>
      </div>""" for item in items)

    return _pagina(f"Checklist · {maquina}", f"""
      <div class="head">
        <h1>Checklist · Mantenimiento autónomo</h1>
        <p>{maquina} · {m['tipo']} ({m['area']})</p>
        <div class="chips">
          <span class="chip" id="hoy"></span><span class="chip" id="turno-chip">Turno</span>
        </div>
        <select id="turno">{opciones_turno}</select>
        <select id="operario">{opciones_op}</select>
        <script>document.getElementById('hoy').textContent =
          new Date().toLocaleDateString('es-PE', {{weekday:'short', day:'numeric', month:'short'}});</script>
      </div>
      <div class="prog"><span id="prog"></span><span id="progfa"></span></div>
      {tarjetas_html}
      <footer><div class="in"><button class="save" disabled>Guardar checklist</button></div></footer>
      <script>{_JS}</script>""")


def _html_exito(maquina: str, res: dict) -> str:
    n = len(res["tarjetas"])
    codigos = ", ".join(checklists.codigo_tarjeta(t) for t in res["tarjetas"])
    bloque = (f'<div class="mini"><b>{n} tarjeta{"s" if n != 1 else ""} TPM generada'
              f'{"s" if n != 1 else ""} automáticamente:</b><br>'
              f'{codigos} · Mantenimiento — con foto de evidencia.<br>'
              f'<span style="color:var(--muted)">El supervisor ya la ve en su bandeja de Tarjetas TPM.</span></div>'
              if n else '<div class="mini">Sin fallas declaradas — estación conforme.</div>')
    return _pagina("Guardado", f"""
      <div class="exito">
        <div class="ico">{_SVG_CHECK}</div>
        <h1>Checklist #{res['checklist_id']:04d} guardado</h1>
        <p>{maquina} · registrado correctamente</p>
        {bloque}
        <a class="ini" href="/{maquina}">← Realizar otro checklist en {maquina}</a>
        <p style="margin-top:14px"><a class="ini" href="/">Ir al listado de estaciones</a></p>
      </div>""")


# --------------------------------------------------------------------------- app
def crear_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # fotos hasta 16 MB

    @app.get("/")
    def index():
        conn = db.conectar()
        try:
            filas = conn.execute(
                "SELECT codigo, tipo, area FROM maquinas ORDER BY codigo").fetchall()
        finally:
            conn.close()
        lis = "".join(
            f'<div class="item"><div class="lbl"><a href="/{r["codigo"]}" '
            f'style="color:var(--teal);text-decoration:none;font-weight:800">{r["codigo"]}</a>'
            f' — {r["tipo"]} ({r["area"]})</div></div>' for r in filas)
        return _pagina("Estaciones", f"""
          <div class="head"><h1>Estaciones SICAM</h1>
          <p>Escanea el QR de tu estación o elige tu máquina:</p></div>{lis}""")

    @app.get("/health")
    def health():
        return "ok"

    @app.get("/<maquina>")
    def formulario(maquina: str):
        return _html_formulario(maquina)

    @app.post("/<maquina>/guardar")
    def guardar(maquina: str):
        conn = db.conectar()
        try:
            if not conn.execute("SELECT 1 FROM maquinas WHERE codigo = ?", (maquina,)).fetchone():
                abort(404)
            claves = [k[5:] for k in request.form if k.startswith("item_")]
            items = []
            for i in claves:
                estado = request.form.get(f"estado_{i}")
                if estado != "falla":
                    items.append({"item": request.form[f"item_{i}"], "estado": "ok"})
                    continue
                archivo = request.files.get(f"foto_{i}")
                if archivo is None or not archivo.filename:
                    return _pagina("Falta evidencia", """
                      <div class="error">Cada ítem con FALLA necesita su foto de evidencia.<br>
                      Vuelve e inténtalo de nuevo.</div>
                      <a class="ini" href="/""" + maquina + """">← Volver al checklist</a>"""), 400
                items.append({
                    "item": request.form[f"item_{i}"],
                    "estado": "falla",
                    "severidad": request.form.get(f"sev_{i}", "Moderada"),
                    "comentario": request.form.get(f"com_{i}", ""),
                    "foto_bytes": archivo.read(),
                    "foto_ext": Path(archivo.filename).suffix or ".jpg",
                })
            res = checklists.registrar_checklist(
                conn, maquina, request.form.get("turno", "Tarde"),
                request.form.get("operario", "—"), items, origen="celular")
        finally:
            conn.close()
        return _html_exito(maquina, res)

    return app


def ip_local() -> str:
    """IP LAN del PC (para construir la URL del QR)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))          # no envía nada, solo resuelve la ruta
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except socket.gaierror:
            return "127.0.0.1"


class ServidorLAN:
    """Wrapper del servidor Flask corriendo en un hilo daemon."""

    def __init__(self, puerto: int = PUERTO):
        self.puerto = puerto
        self._server = None
        self._hilo: threading.Thread | None = None

    @property
    def activo(self) -> bool:
        return self._server is not None

    def url_base(self) -> str:
        return f"http://{ip_local()}:{self.puerto}"

    def url_estacion(self, maquina: str) -> str:
        return f"{self.url_base()}/{maquina}"

    def iniciar(self) -> str:
        """Levanta el servidor; retorna la URL base."""
        if self.activo:
            return self.url_base()
        from werkzeug.serving import make_server

        self._server = make_server("0.0.0.0", self.puerto, crear_app(), threaded=True)
        self._hilo = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._hilo.start()
        return self.url_base()

    def detener(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server = None
            self._hilo = None
