import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import serial
import serial.tools.list_ports
import io
import random
from PIL import Image
import time

# -----------------------------
# CONFIG PAGE
# -----------------------------
st.set_page_config(layout="wide")
st.title("2D Grid Plotter")

# -----------------------------
# SIDEBAR CONTROLS
# -----------------------------
st.sidebar.header("Paramètres")

ports = [p.device for p in serial.tools.list_ports.comports()]
selected_port = st.sidebar.selectbox("Port COM", ["Test (Auto)"] + ports)

refresh_ms = st.sidebar.slider("Refresh (ms)", 100, 2000, 500)
alpha = st.sidebar.slider("Transparence heatmap", 0.05, 1.0, 0.8)
show_grid = st.sidebar.checkbox("Afficher la grille (cellules)", value=True)
show_ticks = st.sidebar.checkbox("Afficher coordonnées (axes)", value=True)
show_colorbar = st.sidebar.checkbox("Afficher échelle d'intensité", value=True)

bg_file = st.sidebar.file_uploader("Image de fond (optionnelle)", type=["png", "jpg", "jpeg"])
if bg_file:
    bg_image_orig = Image.open(bg_file).convert("RGBA")
else:
    bg_image_orig = None

if st.sidebar.button("Reset grille"):
    st.session_state.grid = np.zeros((10, 10))

# -----------------------------
# SESSION INIT
# -----------------------------
if "grid" not in st.session_state:
    st.session_state.grid = np.zeros((10, 10))

# store last received measurement for display
if "last_meas" not in st.session_state:
    st.session_state.last_meas = {"x": None, "y": None, "v": None}

# -----------------------------
# READ DATA (test or serial)
# -----------------------------
def read_data_once():
    # Test mode random
    if selected_port == "Test (Auto)":
        return random.randint(0, 50), random.randint(0, 50), random.random()
    # Real serial
    try:
        ser = serial.Serial(selected_port, 115200, timeout=0.05)
        line = ser.readline().decode(errors="ignore").strip()
        ser.close()
        if not line:
            return None
        parts = line.split(",")
        if len(parts) < 3:
            return None
        x, y, intensity = map(float, parts[:3])
        return int(x), int(y), float(intensity)
    except Exception:
        return None

data = read_data_once()
if data:
    x, y, intensity = data
    intensity = float(max(0.0, min(1.0, intensity)))
    rows, cols = st.session_state.grid.shape

    # Resize automatique si nécessaire
    new_rows = max(rows, y + 1)
    new_cols = max(cols, x + 1)
    if new_rows != rows or new_cols != cols:
        new_grid = np.zeros((new_rows, new_cols))
        new_grid[:rows, :cols] = st.session_state.grid
        st.session_state.grid = new_grid
        rows, cols = new_rows, new_cols

    st.session_state.grid[y, x] = intensity
    st.session_state.last_meas = {"x": x, "y": y, "v": intensity}

# -----------------------------
# RENDER IMAGE (pixel-perfect, limited size)
# -----------------------------
grid = st.session_state.grid.copy()
rows, cols = grid.shape

# PARAMETERS for display sizing
MAX_DISPLAY_PIX = 700        # max pixel dimension for the heatmap (width or height)
CELL_MAX_PIX = 50              # max pixels per cell
CELL_MIN_PIX = 15              # min pixels per cell
dpi = 100                      # matplotlib dpi for figure rendering

# choose cell pixel size so that entire grid fits within MAX_DISPLAY_PIX
cell_pix = int(np.clip(MAX_DISPLAY_PIX / max(rows, cols), CELL_MIN_PIX, CELL_MAX_PIX))
img_w = int(cols * cell_pix)
img_h = int(rows * cell_pix)

# Build matplotlib figure with exact pixel size
fig_w_in = max(2.0, img_w / dpi)
fig_h_in = max(2.0, img_h / dpi)
fig, ax = plt.subplots(figsize=(fig_w_in, fig_h_in), dpi=dpi)

# background image: resize to img_w x img_h and draw first (if provided)
if bg_image_orig is not None:
    try:
        bg = bg_image_orig.resize((img_w, img_h), Image.LANCZOS)
        ax.imshow(bg, extent=[0, cols, 0, rows], origin="lower")
    except Exception:
        pass

# heatmap
cmap = plt.get_cmap("inferno")
im = ax.imshow(grid, origin="lower", cmap=cmap, vmin=0, vmax=1, interpolation="nearest", alpha=alpha)

# grid lines (thin)
if show_grid:
    # draw minor grid lines between cells
    ax.set_xticks(np.arange(-0.5, cols, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, rows, 1), minor=True)
    ax.grid(which="minor", color="white", linestyle='-', linewidth=0.4)

# ticks / coordinates
if show_ticks:
    # show a subset of ticks so labels remain readable
    max_labels = 12
    step_x = max(1, int(np.ceil(cols / max_labels)))
    step_y = max(1, int(np.ceil(rows / max_labels)))
    ax.set_xticks(np.arange(0, cols, step_x))
    ax.set_yticks(np.arange(0, rows, step_y))
    ax.set_xticklabels([str(i) for i in np.arange(0, cols, step_x)], fontsize=8)
    ax.set_yticklabels([str(i) for i in np.arange(0, rows, step_y)], fontsize=8)
else:
    ax.set_xticks([])
    ax.set_yticks([])

# limits and aspect (one cell = square)
ax.set_xlim(-0.5, cols - 0.5)
ax.set_ylim(-0.5, rows - 0.5)
ax.set_aspect('equal')

# colorbar: draw inside figure if selected
if show_colorbar:
    # add a small colorbar to the right
    from mpl_toolkits.axes_grid1 import make_axes_locatable
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="4%", pad=0.04)
    cb = fig.colorbar(im, cax=cax)
    cb.ax.tick_params(labelsize=8)
    cax.yaxis.set_label_position('right')
    cb.set_label('Intensité (0→1)', fontsize=8)
else:
    # no colorbar (keep figure compact)
    pass

# annotate last measurement (top-left corner)
lm = st.session_state.last_meas
if lm["x"] is not None:
    info_text = f"Last: x={lm['x']} y={lm['y']} v={lm['v']:.3f}"
    ax.text(0.0, 1.03, info_text, transform=ax.transAxes, fontsize=6,
            verticalalignment='top', bbox=dict(facecolor='white', alpha=0.8, pad=1.5))

# remove extra margins
plt.tight_layout(pad=0.5)

# render to PNG buffer and display with st.image (fixed width)
buf = io.BytesIO()
fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight')
plt.close(fig)
buf.seek(0)

# Choose display width so the image fits and doesn't produce vertical scroll.
# Display width capped to 920 px (adjust if you want), but keep aspect ratio.
display_width = min(920, img_w)
st.image(buf.getvalue(), width=display_width)

# -----------------------------
# EXPORT
# -----------------------------
col1, col2, col3 = st.columns(3)
with col1:
    csv = io.StringIO()
    np.savetxt(csv, st.session_state.grid, delimiter=",", fmt="%.6f")
    st.download_button("⬇ Télécharger CSV", csv.getvalue(), file_name="radiation_map.csv", mime="text/csv")
with col2:
    st.download_button("⬇ Télécharger PNG", data=buf.getvalue(), file_name="radiation_map.png", mime="image/png")

# -----------------------------
# AUTO REFRESH
# -----------------------------
time.sleep(refresh_ms / 1000)
st.rerun()
