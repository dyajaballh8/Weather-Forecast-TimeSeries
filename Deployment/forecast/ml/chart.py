"""Server-rendered inline SVG chart (no JavaScript / CDN needed): the six inputs and the forecast."""
import math

# (form field, label shown on the chart) in chronological order, oldest first
ROWS = [
    ("temp_1y_ago", "1 year ago"),
    ("temp_24d_ago", "24 days ago"),
    ("avg_62d", "62-day average"),
    ("avg_30d", "30-day average"),
    ("avg_8d", "8-day average"),
    ("temp_2d_ago", "2 days ago"),
]


def build_input_chart(inputs: dict, result) -> str:
    """Horizontal dot plot: one row per input, the forecast row at the bottom with its 80% range."""
    width, row_h, top, bottom = 420, 38, 14, 34
    label_w, plot_l, plot_r = 118, 132, 376
    height = top + row_h * (len(ROWS) + 1) + bottom

    values = [float(inputs[key]) for key, _ in ROWS]
    lo = math.floor(min(values + [result.low80, result.value]) / 2) * 2 - 2
    hi = math.ceil(max(values + [result.high80, result.value]) / 2) * 2 + 2

    def x_of(v):
        return plot_l + (plot_r - plot_l) * (v - lo) / (hi - lo)

    def y_of(i):
        return top + row_h * (i + 0.5)

    parts = [f'<svg class="input-chart" viewBox="0 0 {width} {height}" role="img" '
             f'aria-label="Recent temperatures and the forecast" xmlns="http://www.w3.org/2000/svg">']
    step = 2 if hi - lo <= 14 else 5
    for tick in range(lo, hi + 1, step):
        x = x_of(tick)
        parts.append(f'<line class="grid" x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height - bottom}"/>')
        parts.append(f'<text class="axis" x="{x:.1f}" y="{height - bottom + 18}" text-anchor="middle">{tick}°</text>')

    trail = " ".join(f"{x_of(v):.1f},{y_of(i):.1f}" for i, v in enumerate(values))
    parts.append(f'<polyline class="trail" points="{trail}"/>')
    last = len(values) - 1
    parts.append(f'<line class="link" x1="{x_of(values[last]):.1f}" y1="{y_of(last):.1f}" '
                 f'x2="{x_of(result.value):.1f}" y2="{y_of(len(ROWS)):.1f}"/>')

    for i, (_, label) in enumerate(ROWS):
        y = y_of(i)
        parts.append(f'<text class="cat" x="{label_w}" y="{y + 4:.1f}" text-anchor="end">{label}</text>')
        parts.append(f'<circle class="dot" cx="{x_of(values[i]):.1f}" cy="{y:.1f}" r="6"/>')
        parts.append(f'<text class="val" x="{x_of(values[i]) + 11:.1f}" y="{y + 4.5:.1f}">{values[i]:.1f}</text>')

    fy = y_of(len(ROWS))
    x_lo, x_hi, x_f = x_of(result.low80), x_of(result.high80), x_of(result.value)
    parts.append(f'<line class="whisker" x1="{x_lo:.1f}" y1="{fy:.1f}" x2="{x_hi:.1f}" y2="{fy:.1f}"/>')
    for xx in (x_lo, x_hi):
        parts.append(f'<line class="whisker" x1="{xx:.1f}" y1="{fy - 8:.1f}" x2="{xx:.1f}" y2="{fy + 8:.1f}"/>')
    parts.append(f'<circle class="dot forecast" cx="{x_f:.1f}" cy="{fy:.1f}" r="9"/>')
    parts.append(f'<text class="val forecast" x="{x_hi + 10:.1f}" y="{fy + 5:.1f}" text-anchor="start">{result.value:.1f}</text>')
    parts.append(f'<text class="cat strong" x="{label_w}" y="{fy - 1:.1f}" text-anchor="end">Forecast</text>')
    parts.append(f'<text class="cat small" x="{label_w}" y="{fy + 13:.1f}" text-anchor="end">(80% range)</text>')
    parts.append("</svg>")
    return "".join(parts)
