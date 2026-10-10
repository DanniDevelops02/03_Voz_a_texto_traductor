import base64
import hashlib
import io
import tempfile
import time
from html import escape
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from deep_translator import GoogleTranslator, MyMemoryTranslator
from gtts import gTTS
from PIL import Image

try:
    import speech_recognition as sr
except ImportError:  # la pestaña "Grabar audio" avisará si falta
    sr = None

st.set_page_config(
    page_title="Traductor de voz · Daniel Flórez",
    page_icon="🎤",
    layout="centered",
)

# =====================================================================
#  CONTENIDO
# =====================================================================
IMAGEN = "Traductor_Storybook.jpg"

# "voz" = código que entiende el reconocimiento de voz del navegador
# "respaldo" = código del traductor de respaldo (MyMemory)
IDIOMAS = {
    "Español": {"codigo": "es", "voz": "es-ES", "respaldo": "es-ES"},
    "Inglés": {"codigo": "en", "voz": "en-US", "respaldo": "en-GB"},
    "Bengalí": {"codigo": "bn", "voz": "bn-BD", "respaldo": "bn-IN"},
    "Coreano": {"codigo": "ko", "voz": "ko-KR", "respaldo": "ko-KR"},
    "Mandarín": {"codigo": "zh-CN", "voz": "zh-CN", "respaldo": "zh-CN"},
    "Japonés": {"codigo": "ja", "voz": "ja-JP", "respaldo": "ja-JP"},
}

ACENTOS = {
    "Defecto": "com",
    "México": "com.mx",
    "Reino Unido": "co.uk",
    "Estados Unidos": "com",
    "Canadá": "ca",
    "Australia": "com.au",
    "Irlanda": "ie",
    "Sudáfrica": "co.za",
}

ERRORES_MIC = {
    "not-allowed": (
        "El navegador bloqueó el micrófono. Pulsa el candado 🔒 junto a la dirección "
        "de la página, permite el micrófono y recarga."
    ),
    "service-not-allowed": (
        "El navegador no permite el reconocimiento de voz. En iPhone, activa el "
        "dictado en Ajustes → General → Teclado. Si no funciona, usa la pestaña "
        "«Grabar audio»."
    ),
    "audio-capture": (
        "No se detecta ningún micrófono. Revisa que esté conectado y que no lo "
        "esté usando otra aplicación."
    ),
    "no-speech": "No se escuchó nada. Acércate al micrófono e inténtalo de nuevo.",
    "network": (
        "El servicio de reconocimiento de voz no está disponible. Revisa tu conexión; "
        "algunos navegadores (como Brave) lo bloquean. Prueba la pestaña «Grabar audio»."
    ),
    "language-not-supported": "Este navegador no soporta ese idioma para dictado por voz.",
    "unsupported": (
        "Este navegador no permite reconocimiento de voz en vivo (Firefox, por ejemplo). "
        "Usa Chrome o Edge, o la pestaña «Grabar audio»."
    ),
}

# =====================================================================
#  ESTILO (paleta fría basada en #3f71a6)
# =====================================================================
PRIMARIO = "#3f71a6"
OSCURO = "#1b2f45"
CLARO = "#eaf2f9"
SUAVE = "#a9c7e3"
# Colores del modo "escuchando"
FONDO_A = "#04152a"
FONDO_B = "#0d2e5b"
TEXTO_ESC = "#3886e1"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;600;700&family=Inter:wght@400;500;600&display=swap');

/* Variables animables para el degradado de fondo */
@property --fondo-1 { syntax: '<color>'; inherits: true; initial-value: #f6fafd; }
@property --fondo-2 { syntax: '<color>'; inherits: true; initial-value: __CLARO__; }

html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif;
    font-size: 1.08rem;
}
.stApp {
    background: linear-gradient(180deg, var(--fondo-1) 0%, var(--fondo-2) 100%);
    transition: --fondo-1 .8s ease, --fondo-2 .8s ease;
}
.block-container { max-width: 860px; padding-top: 3rem; padding-bottom: 4rem; }

/* Hero */
.hero { text-align: center; padding: 1rem 0 .5rem 0; }
.hero .etiqueta {
    color: __PRIMARIO__; letter-spacing: .25em; text-transform: uppercase;
    font-size: .85rem; font-weight: 600;
}
.hero h1 {
    font-family: 'Playfair Display', serif; font-size: 3.2rem; color: __OSCURO__;
    margin: .3rem 0 .6rem 0; line-height: 1.1;
}
.hero p { color: #4d6479; font-size: 1.2rem; max-width: 620px; margin: 0 auto; }
.linea {
    width: 70px; height: 4px; border-radius: 4px; background: __PRIMARIO__;
    margin: 1.4rem auto;
}
h2, h3 { font-family: 'Playfair Display', serif !important; color: __OSCURO__ !important; }

/* Tarjetas */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: white;
    border: 1px solid __SUAVE__66 !important;
    border-radius: 18px !important;
    box-shadow: 0 8px 24px rgba(63, 113, 166, .08);
    padding: .6rem .8rem;
    transition: background .8s ease, border-color .8s ease;
}

/* Imagen grande */
[data-testid="stImage"] img {
    width: 100%; aspect-ratio: 2 / 1; object-fit: cover;
    border-radius: 20px; box-shadow: 0 12px 32px rgba(27, 47, 69, .18);
}

/* Resultado de la traducción */
.resultado {
    font-family: 'Playfair Display', serif; font-size: 1.5rem; line-height: 1.5;
    color: __OSCURO__; padding: .4rem .2rem 1rem .2rem;
}

/* Botones */
.stButton > button, .stDownloadButton > button {
    background: __PRIMARIO__; color: white; border: 1.5px solid __PRIMARIO__;
    border-radius: 999px; padding: .7rem 1.6rem; font-size: 1.02rem; font-weight: 600;
    transition: all .2s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    background: __OSCURO__; border-color: __OSCURO__; color: white;
    transform: translateY(-2px); box-shadow: 0 8px 18px rgba(27, 47, 69, .25);
}
[data-testid="stBaseButton-secondary"] { background: white; color: __PRIMARIO__; }

/* Inputs */
.stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
    border-radius: 12px; border: 1px solid __SUAVE__; font-size: 1.05rem;
}
[data-testid="stAlert"] { border-radius: 14px; }

/* Sidebar */
[data-testid="stSidebar"] { background: __OSCURO__; }
[data-testid="stSidebar"] * { color: #e6f0f9 !important; }

#MainMenu, footer { visibility: hidden; }

/* ------------------------------------------------------------------
   MODO ESCUCHANDO: el micrófono pone data-escuchando="1" en <html>
   ------------------------------------------------------------------ */
.stApp p, .stApp label, .stApp li, .stApp span, .stApp h1, .stApp h2, .stApp h3,
.stApp .resultado, .stApp .hero .etiqueta {
    transition: color .6s ease;
}
html[data-escuchando="1"] .stApp {
    --fondo-1: __FONDO_A__;
    --fondo-2: __FONDO_B__;
}
html[data-escuchando="1"] .stApp p,
html[data-escuchando="1"] .stApp label,
html[data-escuchando="1"] .stApp li,
html[data-escuchando="1"] .stApp span,
html[data-escuchando="1"] .stApp h1,
html[data-escuchando="1"] .stApp h2,
html[data-escuchando="1"] .stApp h3,
html[data-escuchando="1"] .stApp .resultado,
html[data-escuchando="1"] .stApp .hero p,
html[data-escuchando="1"] .stApp .hero .etiqueta,
html[data-escuchando="1"] .stApp [data-baseweb="select"] * {
    color: __TEXTO_ESC__ !important;
}
html[data-escuchando="1"] [data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(13, 46, 91, .35) !important;
    border-color: rgba(56, 134, 225, .35) !important;
    box-shadow: none;
}
html[data-escuchando="1"] .stApp .stButton > button,
html[data-escuchando="1"] .stApp .stDownloadButton > button {
    background: rgba(56, 134, 225, .12);
    border-color: __TEXTO_ESC__;
}
html[data-escuchando="1"] .stApp .stTextArea textarea,
html[data-escuchando="1"] .stApp .stSelectbox div[data-baseweb="select"] > div {
    background: rgba(4, 21, 42, .6);
    border-color: rgba(56, 134, 225, .5);
    color: __TEXTO_ESC__;
}
html[data-escuchando="1"] .stApp [data-testid="stAlert"] { background: rgba(13, 46, 91, .6); }
</style>
"""

for token, valor in {
    "__PRIMARIO__": PRIMARIO,
    "__OSCURO__": OSCURO,
    "__CLARO__": CLARO,
    "__SUAVE__": SUAVE,
    "__FONDO_A__": FONDO_A,
    "__FONDO_B__": FONDO_B,
    "__TEXTO_ESC__": TEXTO_ESC,
}.items():
    CSS = CSS.replace(token, valor)

st.markdown(CSS, unsafe_allow_html=True)

# =====================================================================
#  COMPONENTE DE MICRÓFONO (HTML + JavaScript propio)
#  Se guarda en una carpeta temporal al arrancar: no necesitas más archivos.
# =====================================================================
MIC_HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Inter', sans-serif; background: transparent; text-align: center; overflow: hidden; }
  .wrap { display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 38px 8px 8px 8px; }
  .mic {
    position: relative; width: 96px; height: 96px; border-radius: 50%; border: none;
    background: __PRIMARIO__; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: background .25s ease, transform .2s ease;
  }
  .mic:hover { background: __OSCURO__; transform: scale(1.05); }
  .mic svg { width: 40px; height: 40px; fill: #fff; }
  .mic.on { background: __ESC__; }
  .mic.on::before, .mic.on::after {
    content: ""; position: absolute; inset: 0; border-radius: 50%;
    border: 2px solid __ESC__; animation: pulso 1.6s ease-out infinite;
  }
  .mic.on::after { animation-delay: .8s; }
  @keyframes pulso { 0% { transform: scale(1); opacity: .9; } 100% { transform: scale(1.6); opacity: 0; } }
  .estado { font-size: 1rem; font-weight: 600; color: __OSCURO__; transition: color .5s; }
  .parcial { min-height: 1.5em; max-width: 92%; font-size: .95rem; font-style: italic; color: #4d6479; transition: color .5s; }
  body.escuchando .estado, body.escuchando .parcial { color: __ESC__; }
</style>
</head>
<body>
<div class="wrap">
  <button class="mic" id="mic" aria-label="Activar o detener el micrófono">
    <svg viewBox="0 0 24 24"><path d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2z"/></svg>
  </button>
  <div class="estado" id="estado">Pulsa el micrófono para hablar</div>
  <div class="parcial" id="parcial"></div>
</div>

<script>
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const mic = document.getElementById("mic");
  const estado = document.getElementById("estado");
  const parcial = document.getElementById("parcial");
  let args = { idioma: "es-ES" };
  let rec = null;
  let activo = false;

  // --- Comunicación con Streamlit (protocolo de componentes) ---
  function mensaje(tipo, extra) {
    window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type: tipo }, extra), "*");
  }
  const listo = () => mensaje("streamlit:componentReady", { apiVersion: 1 });
  const altura = (h) => mensaje("streamlit:setFrameHeight", { height: h });
  const enviar = (valor) => mensaje("streamlit:setComponentValue", { value: valor, dataType: "json" });

  window.addEventListener("message", (ev) => {
    if (ev.data && ev.data.type === "streamlit:render") args = ev.data.args || args;
  });

  // --- Modo escuchando: marca la página principal para cambiar colores ---
  function modoEscucha(on) {
    document.body.classList.toggle("escuchando", on);
    mic.classList.toggle("on", on);
    try {
      const raiz = window.parent.document.documentElement;
      if (on) raiz.setAttribute("data-escuchando", "1");
      else raiz.removeAttribute("data-escuchando");
    } catch (e) { /* sin acceso a la página: solo se omite el cambio de color */ }
  }
  window.addEventListener("pagehide", () => modoEscucha(false));

  // --- Reconocimiento de voz ---
  function iniciar() {
    if (!SR) {
      estado.textContent = "Tu navegador no soporta reconocimiento de voz";
      enviar({ id: Date.now(), error: "unsupported" });
      return;
    }
    let ultimo = "";
    let huboError = false;

    rec = new SR();
    rec.lang = args.idioma || "es-ES";
    rec.continuous = false;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    rec.onstart = () => {
      activo = true;
      modoEscucha(true);
      estado.textContent = "Escuchando… habla ahora";
      parcial.textContent = "";
    };
    rec.onresult = (e) => {
      let completo = "";
      for (let i = 0; i < e.results.length; i++) completo += e.results[i][0].transcript;
      ultimo = completo;
      parcial.textContent = completo;
    };
    rec.onerror = (e) => {
      if (e.error === "aborted") return;
      huboError = true;
      estado.textContent = "No se pudo usar el micrófono";
      enviar({ id: Date.now(), error: e.error });
    };
    rec.onend = () => {
      activo = false;
      modoEscucha(false);
      if (!huboError) {
        if (ultimo.trim()) {
          estado.textContent = "Listo. Pulsa para hablar de nuevo";
          enviar({ id: Date.now(), texto: ultimo.trim() });
        } else {
          estado.textContent = "No se escuchó nada. Inténtalo de nuevo";
        }
      }
    };

    try { rec.start(); } catch (err) { estado.textContent = "No se pudo iniciar el micrófono"; }
  }

  mic.addEventListener("click", () => {
    if (activo && rec) rec.stop();
    else iniciar();
  });

  listo();
  altura(230);
</script>
</body>
</html>
"""


@st.cache_resource
def preparar_componente():
    carpeta = Path(tempfile.gettempdir()) / "mic_voz_componente"
    carpeta.mkdir(exist_ok=True)
    html = (
        MIC_HTML.replace("__PRIMARIO__", PRIMARIO)
        .replace("__OSCURO__", OSCURO)
        .replace("__ESC__", TEXTO_ESC)
    )
    archivo = carpeta / "index.html"
    if not archivo.exists() or archivo.read_text(encoding="utf-8") != html:
        archivo.write_text(html, encoding="utf-8")
    return components.declare_component("mic_voz", path=str(carpeta))


mic = preparar_componente()

# =====================================================================
#  REPRODUCTOR CON ONDA DE SONIDO (el mismo de la app de texto a audio)
# =====================================================================
PLAYER_HTML = """
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Inter', sans-serif; background: transparent; }
  .player { display: flex; align-items: center; gap: 18px; padding: 8px 2px; }
  .play {
    width: 66px; height: 66px; border-radius: 50%; border: none; flex: none;
    background: __PRIMARIO__; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    transition: background .2s ease, transform .2s ease;
  }
  .play:hover { background: __OSCURO__; transform: scale(1.06); }
  .play svg { width: 28px; height: 28px; fill: white; }
  .wave { flex: 1; height: 88px; display: flex; align-items: center; gap: 3px; cursor: pointer; }
  .bar { flex: 1; min-width: 2px; border-radius: 3px; background: __SUAVE__; transition: background .15s; }
  .bar.done { background: __PRIMARIO__; }
  .time { min-width: 92px; text-align: right; font-size: .9rem; color: #4d6479;
          font-variant-numeric: tabular-nums; }
</style>

<div class="player">
  <button class="play" id="btn" aria-label="Reproducir o pausar">
    <svg viewBox="0 0 24 24"><path id="icon" d="M8 5v14l11-7z"/></svg>
  </button>
  <div class="wave" id="wave" title="Haz clic para saltar a otro punto"></div>
  <div class="time" id="time">0:00 / 0:00</div>
</div>
<audio id="audio" preload="auto" src="data:audio/mpeg;base64,__AUDIO__"></audio>

<script>
  const N = 56;
  const PLAY = "M8 5v14l11-7z";
  const PAUSE = "M6 5h4v14H6zM14 5h4v14h-4z";
  const audio = document.getElementById("audio");
  const wave = document.getElementById("wave");
  const btn = document.getElementById("btn");
  const icon = document.getElementById("icon");
  const time = document.getElementById("time");

  const base = Array.from({length: N}, (_, i) =>
    0.22 + 0.78 * Math.abs(Math.sin(i * 0.9) * Math.cos(i * 0.37)));
  const bars = base.map(() => {
    const d = document.createElement("div");
    d.className = "bar";
    wave.appendChild(d);
    return d;
  });

  let playing = false;

  function fmt(s) {
    if (!isFinite(s)) return "0:00";
    const m = Math.floor(s / 60), r = Math.floor(s % 60);
    return m + ":" + String(r).padStart(2, "0");
  }

  function draw(t) {
    const dur = isFinite(audio.duration) ? audio.duration : 0;
    const p = dur ? audio.currentTime / dur : 0;
    bars.forEach((b, i) => {
      const wob = playing ? 0.68 + 0.32 * Math.sin(t / 130 + i * 0.7) : 1;
      b.style.height = (base[i] * wob * 100) + "%";
      b.classList.toggle("done", i / N < p);
    });
    time.textContent = fmt(audio.currentTime) + " / " + fmt(dur);
    if (playing) requestAnimationFrame(draw);
  }

  btn.onclick = () => (audio.paused ? audio.play() : audio.pause());

  audio.addEventListener("play", () => {
    playing = true;
    icon.setAttribute("d", PAUSE);
    requestAnimationFrame(draw);
  });
  const detener = () => {
    playing = false;
    icon.setAttribute("d", PLAY);
    draw(0);
  };
  audio.addEventListener("pause", detener);
  audio.addEventListener("ended", detener);
  audio.addEventListener("loadedmetadata", () => draw(0));

  wave.addEventListener("click", (e) => {
    const r = wave.getBoundingClientRect();
    if (isFinite(audio.duration)) {
      audio.currentTime = ((e.clientX - r.left) / r.width) * audio.duration;
      if (!playing) draw(0);
    }
  });

  draw(0);
</script>
"""


def reproductor(audio_bytes: bytes) -> str:
    audio_b64 = base64.b64encode(audio_bytes).decode()
    return (
        PLAYER_HTML.replace("__AUDIO__", audio_b64)
        .replace("__PRIMARIO__", PRIMARIO)
        .replace("__OSCURO__", OSCURO)
        .replace("__SUAVE__", SUAVE)
    )


# =====================================================================
#  LÓGICA
# =====================================================================
BASE = Path(__file__).parent


@st.cache_data(show_spinner=False, ttl=3600)
def generar_audio(texto: str, idioma: str, tld: str) -> bytes:
    """Genera el MP3 (con 2 intentos). Si ya se generó igual, usa la copia guardada."""
    ultimo_error = None
    for intento in range(2):
        try:
            buffer = io.BytesIO()
            gTTS(texto, lang=idioma, tld=tld, slow=False).write_to_fp(buffer)
            return buffer.getvalue()
        except Exception as error:
            ultimo_error = error
            time.sleep(1.5)
    raise ultimo_error


@st.cache_data(show_spinner=False, ttl=3600)
def traducir_texto(texto: str, origen: str, destino: str) -> tuple[str, str]:
    """Traduce con Google (2 intentos) y, si está saturado, con MyMemory como respaldo.

    Devuelve (traducción, nombre del servicio usado).
    """
    ultimo_error = None
    for intento in range(2):
        try:
            traduccion = GoogleTranslator(
                source=IDIOMAS[origen]["codigo"], target=IDIOMAS[destino]["codigo"]
            ).translate(texto)
            return traduccion, "Google"
        except Exception as error:
            ultimo_error = error
            time.sleep(1.5)

    try:
        traduccion = MyMemoryTranslator(
            source=IDIOMAS[origen]["respaldo"], target=IDIOMAS[destino]["respaldo"]
        ).translate(texto)
        return traduccion, "MyMemory"
    except Exception:
        raise ultimo_error


def transcribir_wav(wav_bytes: bytes, idioma_voz: str) -> str:
    reconocedor = sr.Recognizer()
    with sr.AudioFile(io.BytesIO(wav_bytes)) as fuente:
        audio = reconocedor.record(fuente)
    return reconocedor.recognize_google(audio, language=idioma_voz)


def procesar_evento(evento):
    """Recibe lo que envía el micrófono en vivo (texto o error), una sola vez."""
    if not evento or evento.get("id") == st.session_state.get("ultimo_evento"):
        return
    st.session_state["ultimo_evento"] = evento.get("id")
    if evento.get("texto"):
        st.session_state["texto_origen"] = evento["texto"]
        st.session_state.pop("aviso_mic", None)
    else:
        codigo = evento.get("error", "desconocido")
        st.session_state["aviso_mic"] = ERRORES_MIC.get(
            codigo, f"Error del micrófono ({codigo})."
        )


# =====================================================================
#  PÁGINA
# =====================================================================
with st.sidebar:
    st.subheader("Cómo usarlo")
    st.markdown(
        "1. Elige el idioma en que hablas y el idioma de destino.\n"
        "2. Pulsa el micrófono, habla y haz una pausa. También puedes grabar un audio.\n"
        "3. Revisa el texto y pulsa **Traducir y escuchar**."
    )
    st.caption(
        "El modo en vivo funciona mejor en Chrome o Edge. En iPhone o Firefox, "
        "usa «Grabar audio»."
    )

st.markdown(
    """
    <div class="hero">
        <div class="etiqueta">Voz a texto · Traductor</div>
        <h1>Traductor de voz</h1>
        <p>Habla en tu idioma, mira cómo se convierte en texto y escucha la traducción.</p>
        <div class="linea"></div>
    </div>
    """,
    unsafe_allow_html=True,
)

ruta_imagen = BASE / IMAGEN
if ruta_imagen.is_file():
    st.image(Image.open(ruta_imagen), use_container_width=True)
else:
    st.info(f"Agrega la imagen '{IMAGEN}' al repositorio para verla aquí.")

st.write("")

# ---- 1. Idiomas ----
with st.container(border=True):
    st.subheader("1 · Idiomas")
    c1, c2 = st.columns(2)
    with c1:
        entrada = st.selectbox("Hablo en", list(IDIOMAS), index=0)
    with c2:
        salida = st.selectbox("Quiero traducir a", list(IDIOMAS), index=1)
    with st.expander("Opciones de voz"):
        acento = st.selectbox("Acento de la voz traducida", list(ACENTOS))

st.write("")

# ---- 2. Micrófono ----
with st.container(border=True):
    st.subheader("2 · Habla")
    tab_vivo, tab_audio = st.tabs(["🎤 En vivo", "🎙️ Grabar audio"])

    with tab_vivo:
        st.caption("Pulsa el micrófono, habla y haz una pausa: el texto aparecerá abajo.")
        evento = mic(idioma=IDIOMAS[entrada]["voz"], key="mic", default=None)
        procesar_evento(evento)

    with tab_audio:
        if sr is None:
            st.info("Falta instalar SpeechRecognition en requirements.txt para usar esta opción.")
        else:
            st.caption(
                "Graba, detén la grabación y se transcribirá sola. "
                "Funciona en cualquier navegador."
            )
            grabacion = st.audio_input("Graba tu voz", label_visibility="collapsed")
            if grabacion is not None:
                datos = grabacion.getvalue()
                huella = hashlib.md5(datos).hexdigest()
                if st.session_state.get("huella_audio") != huella:
                    st.session_state["huella_audio"] = huella
                    with st.spinner("Transcribiendo..."):
                        try:
                            st.session_state["texto_origen"] = transcribir_wav(
                                datos, IDIOMAS[entrada]["voz"]
                            )
                            st.session_state.pop("aviso_mic", None)
                        except sr.UnknownValueError:
                            st.session_state["aviso_mic"] = (
                                "No se entendió el audio. Habla más cerca del micrófono "
                                "y verifica el idioma elegido."
                            )
                        except Exception as error:
                            st.session_state["aviso_mic"] = (
                                f"No se pudo transcribir el audio ({error})."
                            )

    if st.session_state.get("aviso_mic"):
        st.warning(st.session_state["aviso_mic"])

st.write("")

# ---- 3. Texto reconocido ----
with st.container(border=True):
    st.subheader("3 · Texto reconocido")
    texto = st.text_area(
        "Texto reconocido",
        key="texto_origen",
        height=130,
        placeholder="Aquí aparecerá lo que digas. También puedes escribirlo o corregirlo.",
        label_visibility="collapsed",
    )
    traducir = st.button("Traducir y escuchar", type="primary", use_container_width=True)

if traducir:
    if not texto.strip():
        st.warning("Habla, graba o escribe un texto antes de traducir.")
    else:
        traduccion = None
        with st.spinner("Traduciendo..."):
            try:
                traduccion, servicio = traducir_texto(texto.strip(), entrada, salida)
            except Exception:
                st.error(
                    "Los servicios de traducción están saturados en este momento. "
                    "Espera unos segundos y vuelve a pulsar el botón."
                )

        if traduccion:
            audio_traducido = None
            with st.spinner("Generando audio..."):
                try:
                    audio_traducido = generar_audio(
                        traduccion, IDIOMAS[salida]["codigo"], ACENTOS[acento]
                    )
                except Exception:
                    st.warning(
                        "La traducción está lista, pero no se pudo generar el audio "
                        "(el servicio de voz está saturado). Vuelve a intentarlo en unos segundos."
                    )
            st.session_state["resultado"] = {
                "texto": traduccion,
                "audio": audio_traducido,
                "idioma": salida,
                "servicio": servicio,
            }

# ---- 4. Resultado ----
resultado = st.session_state.get("resultado")
if resultado:
    st.write("")
    with st.container(border=True):
        st.subheader(f"Traducción · {resultado['idioma']}")
        st.markdown(
            f'<div class="resultado">{escape(resultado["texto"])}</div>',
            unsafe_allow_html=True,
        )
        if resultado["audio"]:
            components.html(reproductor(resultado["audio"]), height=120)
            st.download_button(
                "Descargar MP3",
                data=resultado["audio"],
                file_name="traduccion.mp3",
                mime="audio/mpeg",
                use_container_width=True,
            )
        if resultado.get("servicio") == "MyMemory":
            st.caption("Traducido con el servicio de respaldo (MyMemory).")

st.write("")
st.caption("Traducción y voz con servicios de Google (deep-translator y gTTS).")
