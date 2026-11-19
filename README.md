# Mano abierta = fotos de Taylor Swift y Bob Esponja

Programa en Python que abre tu cámara, detecta si tienes la **palma abierta** y, cuando lo confirma, descarga fotos de Taylor Swift y Bob Esponja.

Las imágenes salen de [Wikimedia Commons](https://commons.wikimedia.org/) (archivos con licencia libre).

## Cómo usarlo

1. Doble clic en `abrir.bat`
2. Espera a que se abra la ventana de la cámara
3. Muestra la **palma abierta** (los 5 dedos extendidos) frente a la cámara
4. El programa baja 3 fotos de cada uno a la carpeta `fotos/`

`fotos/` se queda en esta computadora. El repositorio lleva el programa, no las descargas.

### Teclas

| Tecla | Acción |
| --- | --- |
| `Q` o `Esc` | Salir |
| `D` | Descargar ahora, sin esperar el gesto |
| `O` | Abrir la carpeta `fotos` |

## Carpetas de destino

- `fotos/taylor/` — Taylor Swift
- `fotos/bob_esponja/` — Bob Esponja

Hay un enfriamiento de 8 segundos para que no descargue en bucle si dejas la mano abierta.

## Requisitos

- Windows
- Cámara web
- Python 3.10 o similar
- Internet (para bajar las fotos)

Si quieres instalarlo a mano:

```bash
cd mano-fotos
pip install -r requirements.txt
python main.py
```
