import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from streamlit_webserial import st_webserial  # <--- Nouveau
import io
import random
from PIL import Image
import time

# -----------------------------
# CONFIG PAGE
# -----------------------------
st.set_page_config(layout="wide")
st.title("2D Grid Plotter (Web Edition)")

# -----------------------------
# SIDEBAR CONTROLS
# -----------------------------
st.sidebar.header("Paramètres")

# Sur le Web, on ne peut pas lister les ports COM du serveur.
# On propose soit le mode Test, soit la connexion WebSerial.
mode = st.sidebar.radio("Mode de connexion", ["Test (Simulation)", "USB Direct (WebSerial)"])

refresh_ms = st.sidebar.slider("Refresh (ms)", 100, 2000, 500)
alpha = st.sidebar.slider("Transparence heatmap", 0.05, 1.0, 0.8)
show_grid = st.sidebar.checkbox("Afficher la grille", value=True)
show_ticks = st.sidebar.checkbox("Afficher coordonnées", value=True)
show_colorbar = st.sidebar.checkbox("Afficher échelle", value=True)

bg_file = st.sidebar.file_uploader("Image de fond", type=["png", "jpg", "jpeg"])
bg_image_orig = Image.open(bg_file).convert("RGBA") if bg_file else None

if st.sidebar.button("Reset grille"):
    st.session_state.grid = np.zeros((10, 10))
    st.rerun()

# -----------------------------
# SESSION INIT
# -----------------------------
if "grid" not in st.session_state:
    st.session_state.grid = np.zeros((10, 10))

if "last_meas" not in st.session_state:
    st.session_state.last_meas = {"x": None, "y": None, "v": None}

# -----------------------------
# SERIAL DATA HANDLING (WEB)
# -----------------------------
raw_data = None

if mode == "USB Direct (WebSerial)":
    # Ce composant affiche le bouton "Connect" et gère l'USB du navigateur
    res = st_webserial(baudrate=115200, key="serial_port")
    if res:
        raw_data = res
else:
    # Mode Simulation
    if random.random() > 0.5: # Simule un flux intermittent
        raw_data = f"{random.randint(0, 9)},{random.randint(0, 9)},{random.random()}"

# Traitement de la donnée reçue
if raw_data:
    try:
        # Nettoyage et split (format attendu: x,y,v)
        parts = raw_data.strip().split(",")
        if len(parts) >= 3:
            x, y, intensity = int(float(parts[0])), int(float(parts[1])), float(parts[2])
            intensity = max(0.0, min(1.0, intensity))
            
            rows, cols = st.session_state.grid.shape
            # Resize auto
            if y >= rows or x >= cols:
                new_grid = np.zeros((max(rows, y + 1), max(cols, x + 1)))
                new_grid[:rows, :cols] = st.session_state.grid
                st.session_state.grid = new_grid
            
            st.session_state.grid[y, x] = intensity
            st.session_state.last_meas = {"x": x, "y": y, "v": intensity}
    except Exception as e:
        st.error(f"Erreur de format : {raw_data}")

# -----------------------------
# RENDER (Ton code de dessin reste identique)
# -----------------------------
grid = st.session_state.grid.copy()
rows, cols = grid.shape
dpi = 100
cell_pix = int(np.clip(700 / max(rows, cols), 15, 50))
img_w, img_h = int(cols * cell_pix), int(rows * cell_pix)

fig, ax = plt.subplots(figsize=(max(2.0, img_w/dpi), max(2.0, img_h/dpi)), dpi=dpi)

if bg_image_orig:
    ax.imshow(bg_image_orig.resize((img_w, img_h)), extent=[0, cols, 0, rows], origin="lower")

im = ax.imshow(grid, origin="lower", cmap="inferno", vmin=0, vmax=1, interpolation="nearest", alpha=alpha)

if show_grid:
    ax.set_xticks(np.arange(-0.5, cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, rows, 1), minor=True)
    ax.grid(which="minor", color="white", linestyle='-', linewidth=0.4)

ax.set_aspect('equal')

# Affichage des infos
lm = st.session_state.last_meas
if lm["x"] is not None:
    ax.set_title(f"Dernière mesure: x={lm['x']}, y={lm['y']}, val={lm['v']:.2f}", fontsize=10)

buf = io.BytesIO()
fig.savefig(buf, format='png', bbox_inches='tight')
plt.close(fig)
st.image(buf.getvalue(), width=min(920, img_w))

# Export
col1, col2 = st.columns(2)
with col1:
    st.download_button("⬇ CSV", io.StringIO(np.array2string(st.session_state.grid)).getvalue(), "map.csv")
with col2:
    st.download_button("⬇ PNG", buf.getvalue(), "map.png", "image/png")

# Auto-refresh
time.sleep(refresh_ms / 1000)
st.rerun()
