"""
Mano abierta = descarga fotos de Taylor Swift y Bob Esponja.

Abre la cámara, detecta si tu palma está abierta y, cuando lo confirma,
baja imágenes de Wikimedia Commons a la carpeta fotos/.
"""

from __future__ import annotations

import math
import os
import sys
import threading
import time
from pathlib import Path

import cv2
import mediapipe as mp
import requests

CARPETA_FOTOS = Path(__file__).resolve().parent / "fotos"
BUSQUEDAS = {
    "taylor": {
        "consulta": "Taylor Swift",
        "articulo": "Taylor Swift",
        "categoria": "Taylor Swift",
        "palabras": ("taylor",)
    },
    "bob_esponja": {
        "consulta": "SpongeBob SquarePants",
        "articulo": "SpongeBob SquarePants",
        "categoria": "SpongeBob SquarePants",
        "palabras": ("spongebob", "sponge-bob", "bob esponja", "bob l'eponge", "bob_l"),
    },
}
FOTOS_POR_CATEGORIA = 3
COOLDOWN_SEGUNDOS = 8
FRAMES_PARA_CONFIRMAR = 10
MAX_FOTOS_POR_CARPETA = 30

USER_AGENT = (
    "ManoFotos/1.0 (proyecto personal; descarga desde Wikimedia Commons) "
    "Python-requests"
)

FINGERTIPS = (4, 8, 12, 16, 20)
FINGER_PIPS = (3, 6, 10, 14, 18)


def distancia(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def palma_abierta(landmarks) -> bool:
    """True si los 5 dedos están extendidos (mano abierta)."""
    muneca = landmarks[0]
    dedos_arriba = 0
    for tip, pip in zip(FINGERTIPS, FINGER_PIPS):
        if distancia(landmarks[tip], muneca) > distancia(landmarks[pip], muneca) * 1.12:
            dedos_arriba += 1
    return dedos_arriba == 5


def _get_json(url: str, params: dict) -> dict:
    ultimo_error: Exception | None = None
    for intento in range(4):
        try:
            respuesta = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=20)
            if respuesta.status_code == 429:
                time.sleep(1.5 * (intento + 1))
                continue
            respuesta.raise_for_status()
            return respuesta.json()
        except requests.RequestException as e:
            ultimo_error = e
            time.sleep(0.6 * (intento + 1))
    if ultimo_error:
        raise ultimo_error
    raise requests.RequestException("No pude consultar Wikimedia")


def _titulo_vale(titulo: str, palabras: tuple[str, ...], exigir_palabras: bool = True) -> bool:
    t = titulo.lower().replace("é", "e")
    prohibidas = (
        "icon", "flag", "logo", "coat of arms", "map of", "signature",
        "education center", "geometry", "relativity", "diagram",
        "theater", "event hall", "single cover",
    )
    if any(p in t for p in prohibidas):
        return False
    if not exigir_palabras or not palabras:
        return True
    return any(p in t for p in palabras)


def _urls_desde_paginas(paginas: dict, palabras: tuple[str, ...], limite: int,
                        exigir_palabras: bool = True) -> list[str]:
    urls: list[str] = []
    mime_ok = {"image/jpeg", "image/png", "image/webp"}
    for pagina in paginas.values():
        titulo = pagina.get("title", "")
        if not _titulo_vale(titulo, palabras, exigir_palabras=exigir_palabras):
            continue
        info = (pagina.get("imageinfo") or [{}])[0]
        if info.get("mime") not in mime_ok:
            continue
        candidato = info.get("thumburl") or info.get("url")
        if candidato and candidato not in urls:
            urls.append(candidato)
        if len(urls) >= limite:
            break
    return urls


def _info_de_archivos(archivos: list[str], palabras: tuple[str, ...], limite: int) -> list[str]:
    if not archivos:
        return []
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "format": "json",
        "titles": "|".join(archivos[:50]),
        "prop": "imageinfo",
        "iiprop": "url|mime|size",
        "iiurlwidth": 1280,
    }
    datos = _get_json(url, params)
    return _urls_desde_paginas(datos.get("query", {}).get("pages", {}), palabras, limite)


def buscar_urls_commons(consulta: str, limite: int, palabras: tuple[str, ...] | None = None,
                        articulo: str | None = None, categoria: str | None = None) -> list[str]:
    """Busca fotos en Wikimedia Commons y en el artículo de Wikipedia."""
    if palabras is None:
        palabras = tuple(consulta.lower().split())
    urls: list[str] = []

    if articulo:
        try:
            time.sleep(0.25)
            datos = _get_json(
                "https://en.wikipedia.org/w/api.php",
                {
                    "action": "query",
                    "format": "json",
                    "titles": articulo,
                    "prop": "pageimages",
                    "piprop": "original|name",
                    "pithumbsize": 1280,
                },
            )
            for pagina in datos.get("query", {}).get("pages", {}).values():
                original = (pagina.get("original") or {}).get("source")
                nombre = pagina.get("pageimage", "")
                if original and not original.lower().endswith(".svg") and _titulo_vale(nombre, palabras):
                    urls.append(original)
        except requests.RequestException:
            pass

    if categoria:
        try:
            time.sleep(0.25)
            datos = _get_json(
                "https://commons.wikimedia.org/w/api.php",
                {
                    "action": "query",
                    "format": "json",
                    "generator": "categorymembers",
                    "gcmtitle": f"Category:{categoria}",
                    "gcmtype": "file",
                    "gcmlimit": max(limite * 6, 24),
                    "prop": "imageinfo",
                    "iiprop": "url|mime|size",
                    "iiurlwidth": 1280,
                },
            )
            urls.extend(_urls_desde_paginas(datos.get("query", {}).get("pages", {}), palabras, limite))
        except requests.RequestException:
            pass

    if len(urls) < limite and articulo:
        try:
            time.sleep(0.25)
            datos = _get_json(
                "https://en.wikipedia.org/w/api.php",
                {
                    "action": "query",
                    "format": "json",
                    "titles": articulo,
                    "prop": "images",
                    "imlimit": 50,
                },
            )
            paginas = datos.get("query", {}).get("pages", {})
            archivos = []
            for pagina in paginas.values():
                for img in pagina.get("images", []):
                    archivos.append(img.get("title", ""))
            urls.extend(u for u in _info_de_archivos(archivos, palabras, limite) if u not in urls)
        except requests.RequestException:
            pass

    if len(urls) < limite:
        time.sleep(0.25)
        datos = _get_json(
            "https://commons.wikimedia.org/w/api.php",
            {
                "action": "query",
                "format": "json",
                "generator": "search",
                "gsrsearch": f'filetype:bitmap intitle:"{consulta}"',
                "gsrlimit": max(limite * 5, 15),
                "gsrnamespace": 6,
                "prop": "imageinfo",
                "iiprop": "url|mime|size",
                "iiurlwidth": 1280,
            },
        )
        extras = _urls_desde_paginas(datos.get("query", {}).get("pages", {}), palabras, limite)
        urls.extend(u for u in extras if u not in urls)

    return urls[:limite]


def ya_descargada(carpeta: Path, url: str) -> bool:
    nombre = nombre_desde_url(url)
    return (carpeta / nombre).exists()


def nombre_desde_url(url: str) -> str:
    bruto = url.split("?")[0].rstrip("/").split("/")[-1]
    seguro = "".join(c if c.isalnum() or c in "._-" else "_" for c in bruto)
    if not seguro.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        seguro += ".jpg"
    return seguro[:120]


def descargar_archivo(url: str, destino: Path) -> bool:
    destino.parent.mkdir(parents=True, exist_ok=True)
    try:
        with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30, stream=True) as r:
            r.raise_for_status()
            tipo = r.headers.get("Content-Type", "")
            if not tipo.startswith("image/"):
                return False
            with open(destino, "wb") as f:
                for trozo in r.iter_content(chunk_size=64 * 1024):
                    if trozo:
                        f.write(trozo)
        if destino.stat().st_size < 2048:
            destino.unlink(missing_ok=True)
            return False
        return True
    except requests.RequestException:
        destino.unlink(missing_ok=True)
        return False


def descargar_lote() -> tuple[int, list[str]]:
    """Descarga un lote de fotos. Devuelve (cantidad, mensajes)."""
    total = 0
    mensajes: list[str] = []

    for carpeta_nombre, meta in BUSQUEDAS.items():
        carpeta = CARPETA_FOTOS / carpeta_nombre
        carpeta.mkdir(parents=True, exist_ok=True)
        existentes = list(carpeta.glob("*.*"))
        if len(existentes) >= MAX_FOTOS_POR_CARPETA:
            mensajes.append(f"{carpeta_nombre}: ya hay {len(existentes)} fotos, salto.")
            continue

        try:
            urls = buscar_urls_commons(
                meta["consulta"],
                FOTOS_POR_CATEGORIA + 8,
                palabras=meta["palabras"],
                articulo=meta["articulo"],
                categoria=meta["categoria"],
            )
        except requests.RequestException as e:
            mensajes.append(f"{carpeta_nombre}: error de red ({e})")
            continue

        nuevas = [u for u in urls if not ya_descargada(carpeta, u)]
        bajadas = 0
        for url in nuevas:
            if bajadas >= FOTOS_POR_CATEGORIA:
                break
            destino = carpeta / nombre_desde_url(url)
            if descargar_archivo(url, destino):
                bajadas += 1
                total += 1

        if bajadas:
            mensajes.append(f"{carpeta_nombre}: +{bajadas} fotos")
        else:
            mensajes.append(f"{carpeta_nombre}: no encontré fotos nuevas")

    return total, mensajes


class Descargador:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.ocupado = False
        self.ultimo = 0.0
        self.estado = "Abre la mano para descargar"
        self.color = (240, 240, 240)
        self.total_sesion = 0

    def puede_lanzar(self) -> bool:
        with self.lock:
            if self.ocupado:
                return False
            if time.time() - self.ultimo < COOLDOWN_SEGUNDOS:
                return False
            return True

    def lanzar(self) -> None:
        if not self.puede_lanzar():
            return
        with self.lock:
            self.ocupado = True
            self.estado = "Descargando fotos..."
            self.color = (80, 200, 255)

        def trabajo() -> None:
            try:
                cantidad, mensajes = descargar_lote()
                with self.lock:
                    self.total_sesion += cantidad
                    if cantidad:
                        self.estado = f"Listo: {cantidad} fotos. " + " | ".join(mensajes)
                        self.color = (80, 220, 120)
                    else:
                        self.estado = "No se bajaron fotos nuevas. " + " | ".join(mensajes)
                        self.color = (80, 180, 255)
            except Exception as e:  # noqa: BLE001 - mostrar cualquier fallo en pantalla
                with self.lock:
                    self.estado = f"Error: {e}"
                    self.color = (60, 60, 255)
            finally:
                with self.lock:
                    self.ocupado = False
                    self.ultimo = time.time()

        threading.Thread(target=trabajo, daemon=True).start()


def abrir_carpeta_fotos() -> None:
    CARPETA_FOTOS.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(CARPETA_FOTOS)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f'open "{CARPETA_FOTOS}"')
    else:
        os.system(f'xdg-open "{CARPETA_FOTOS}"')


def dibujar_texto(frame, texto: str, origen: tuple[int, int], color, escala=0.7, grosor=2) -> None:
    cv2.putText(frame, texto, origen, cv2.FONT_HERSHEY_SIMPLEX, escala, (0, 0, 0), grosor + 3, cv2.LINE_AA)
    cv2.putText(frame, texto, origen, cv2.FONT_HERSHEY_SIMPLEX, escala, color, grosor, cv2.LINE_AA)


def main() -> int:
    CARPETA_FOTOS.mkdir(parents=True, exist_ok=True)
    descargador = Descargador()

    manos = mp.solutions.hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.6,
    )
    dibujo = mp.solutions.drawing_utils
    estilos = mp.solutions.drawing_styles

    camara = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not camara.isOpened():
        camara = cv2.VideoCapture(0)
    if not camara.isOpened():
        print("No pude abrir la cámara. Conéctala y vuelve a intentar.")
        return 1

    camara.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    camara.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    frames_abierta = 0
    print("Cámara lista. Abre la mano frente a la cámara.")
    print("Teclas: Q = salir  |  D = descargar ahora  |  O = abrir carpeta fotos")

    try:
        while True:
            ok, frame = camara.read()
            if not ok:
                print("Se perdió la señal de la cámara.")
                break

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resultado = manos.process(rgb)

            abierta = False
            if resultado.multi_hand_landmarks:
                for landmarks in resultado.multi_hand_landmarks:
                    dibujo.draw_landmarks(
                        frame,
                        landmarks,
                        mp.solutions.hands.HAND_CONNECTIONS,
                        estilos.get_default_hand_landmarks_style(),
                        estilos.get_default_hand_connections_style(),
                    )
                    if palma_abierta(landmarks.landmark):
                        abierta = True

            if abierta:
                frames_abierta += 1
            else:
                frames_abierta = 0

            if abierta and frames_abierta >= FRAMES_PARA_CONFIRMAR:
                descargador.lanzar()

            with descargador.lock:
                estado = descargador.estado
                color = descargador.color
                ocupado = descargador.ocupado
                total = descargador.total_sesion
                restante = max(0, COOLDOWN_SEGUNDOS - (time.time() - descargador.ultimo))

            alto, ancho = frame.shape[:2]
            cv2.rectangle(frame, (0, 0), (ancho, 110), (20, 20, 20), -1)

            if ocupado:
                etiqueta = "DESCARGANDO..."
                color_etiqueta = (80, 200, 255)
            elif abierta:
                etiqueta = "MANO ABIERTA"
                color_etiqueta = (80, 220, 120)
            else:
                etiqueta = "Muestra la palma abierta"
                color_etiqueta = (220, 220, 220)

            dibujar_texto(frame, etiqueta, (20, 40), color_etiqueta, 1.0, 2)
            dibujar_texto(frame, estado[:90], (20, 72), color, 0.55, 1)
            extra = f"Fotos esta sesion: {total}"
            if not ocupado and restante > 0 and descargador.ultimo:
                extra += f"   |   espera {restante:.0f}s"
            dibujar_texto(frame, extra, (20, 98), (180, 180, 180), 0.55, 1)
            dibujar_texto(
                frame,
                "Q salir   D descargar   O abrir carpeta",
                (20, alto - 20),
                (200, 200, 200),
                0.55,
                1,
            )

            cv2.imshow("Mano abierta = Taylor + Bob Esponja", frame)
            tecla = cv2.waitKey(1) & 0xFF
            if tecla in (ord("q"), ord("Q"), 27):
                break
            if tecla in (ord("d"), ord("D")):
                descargador.lanzar()
            if tecla in (ord("o"), ord("O")):
                abrir_carpeta_fotos()
    finally:
        manos.close()
        camara.release()
        cv2.destroyAllWindows()

    print(f"Listo. Las fotos están en: {CARPETA_FOTOS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
