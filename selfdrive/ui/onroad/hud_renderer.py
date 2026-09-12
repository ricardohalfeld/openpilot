import json
import pyray as rl
from functools import partial
from dataclasses import dataclass
from openpilot.selfdrive.controls.lib.latcontrol_torque import (
  INTERP_SPEEDS as LAT_TORQUE_INTERP_SPEEDS,
  KI as LAT_TORQUE_KI,
  KP_INTERP as LAT_TORQUE_KP_INTERP,
)
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets.button import Button, ButtonStyle
from openpilot.system.ui.widgets import Widget

TORQUE_TUNE_OVERRIDE_PARAM = "TorqueTuneOverride"
TUNE_STEP = {
  "latAccelFactor": 0.05,
  "friction": 0.01,
  "maxLatAccel": 0.10,
  "kpScale": 0.05,
  "kiScale": 0.05,
  "ffScale": 0.05,
}
TUNE_LIMITS = {
  "latAccelFactor": (1.5, 3.5),
  "friction": (0.0, 0.25),
  "maxLatAccel": (1.5, 3.5),
  "kpScale": (0.0, 2.0),
  "kiScale": (0.0, 2.0),
  "ffScale": (0.0, 2.0),
}


@dataclass(frozen=True)
class FontSizes:
  title: int = 72
  subtitle: int = 34
  section: int = 30
  row_label: int = 42
  row_value: int = 54
  small: int = 28
  tiny: int = 24


@dataclass(frozen=True)
class Colors:
  WHITE = rl.WHITE
  WHITE_TRANSLUCENT = rl.Color(255, 255, 255, 210)
  MUTED = rl.Color(185, 185, 185, 255)
  PANEL_BG = rl.Color(0, 0, 0, 225)
  CARD_BG = rl.Color(25, 25, 25, 230)
  BUTTON_BG = rl.Color(255, 255, 255, 40)
  BORDER = rl.Color(255, 255, 255, 75)
  BAR_BG = rl.Color(16, 16, 16, 255)
  BAR_ZERO = rl.Color(255, 255, 255, 220)
  BAR_MARKER = rl.Color(255, 255, 255, 255)
  BAR_P = rl.Color(80, 180, 255, 255)
  BAR_I = rl.Color(255, 190, 70, 255)
  BAR_D = rl.Color(190, 120, 255, 255)
  BAR_F = rl.Color(90, 230, 120, 255)
  BAR_CMD = rl.Color(255, 95, 95, 255)


FONT_SIZES = FontSizes()
COLORS = Colors()


def _clamp(value: float, lo: float, hi: float) -> float:
  return min(max(value, lo), hi)


def _loads_param_json(raw):
  if raw is None:
    return None
  if isinstance(raw, dict):
    return raw
  if isinstance(raw, bytes):
    raw = raw.decode("utf-8")
  if isinstance(raw, str):
    return json.loads(raw)
  return None


def _interp(x: float, xp: list[float], fp: list[float]) -> float:
  if x <= xp[0]:
    return fp[0]
  if x >= xp[-1]:
    return fp[-1]
  for i in range(1, len(xp)):
    if x < xp[i]:
      t = (x - xp[i - 1]) / (xp[i] - xp[i - 1])
      return fp[i - 1] + t * (fp[i] - fp[i - 1])
  return fp[-1]


class HudRenderer(Widget):
  def __init__(self):
    super().__init__()
    self._font_semi_bold: rl.Font = gui_app.font(FontWeight.SEMI_BOLD)
    self._font_bold: rl.Font = gui_app.font(FontWeight.BOLD)
    self._font_medium: rl.Font = gui_app.font(FontWeight.MEDIUM)

    self._tune_buttons: dict[tuple[str, int], Button] = {}
    for key in TUNE_STEP:
      for direction, text in ((-1, "-"), (1, "+")):
        self._tune_buttons[(key, direction)] = self._child(Button(text, partial(self._adjust_tune, key, direction),
                                                                  font_size=54,
                                                                  button_style=ButtonStyle.TRANSPARENT_WHITE_BORDER,
                                                                  border_radius=10))
    self._tune_reset_button = self._child(Button("RST", self._reset_tune, font_size=44,
                                                 button_style=ButtonStyle.TRANSPARENT_WHITE_BORDER, border_radius=10))

  def _update_state(self) -> None:
    pass

  def _render(self, rect: rl.Rectangle) -> None:
    values = self._tune_values()
    if values is None:
      return

    rl.draw_rectangle(int(rect.x), int(rect.y), int(rect.width), int(rect.height), COLORS.PANEL_BG)
    self._draw_torque_tune_panel(rect, values)

  def user_interacting(self) -> bool:
    # The fullscreen tuner owns the onroad screen. Do not let touches fall through to the main layout.
    return True

  def _default_tune_values(self) -> dict[str, float] | None:
    if ui_state.CP is None or ui_state.CP.lateralTuning.which() != "torque":
      return None

    torque = ui_state.CP.lateralTuning.torque
    return {
      "latAccelFactor": float(torque.latAccelFactor),
      "friction": float(torque.friction),
      "maxLatAccel": float(ui_state.CP.maxLateralAccel),
      "kpScale": 1.0,
      "kiScale": 1.0,
      "ffScale": 1.0,
    }

  def _tune_values(self) -> dict[str, float] | None:
    values = self._default_tune_values()
    if values is None:
      return None

    try:
      override = _loads_param_json(ui_state.params.get(TORQUE_TUNE_OVERRIDE_PARAM))
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
      override = None

    if isinstance(override, dict) and override.get("enabled", False):
      for key in values:
        if key in override:
          try:
            values[key] = float(override[key])
          except (TypeError, ValueError):
            pass
    return values

  def _write_tune_values(self, values: dict[str, float]) -> None:
    payload = {
      "enabled": True,
      "latAccelFactor": round(values["latAccelFactor"], 3),
      "friction": round(values["friction"], 3),
      "maxLatAccel": round(values["maxLatAccel"], 3),
      "kpScale": round(values["kpScale"], 3),
      "kiScale": round(values["kiScale"], 3),
      "ffScale": round(values["ffScale"], 3),
    }
    ui_state.params.put_nonblocking(TORQUE_TUNE_OVERRIDE_PARAM, json.dumps(payload))

  def _adjust_tune(self, key: str, direction: int) -> None:
    values = self._tune_values()
    if values is None:
      return

    lo, hi = TUNE_LIMITS[key]
    values[key] = _clamp(values[key] + direction * TUNE_STEP[key], lo, hi)
    self._write_tune_values(values)

  def _reset_tune(self) -> None:
    ui_state.params.remove(TORQUE_TUNE_OVERRIDE_PARAM)

  def _draw_text_right(self, text: str, x: float, y: float, font_size: int, color: rl.Color = COLORS.WHITE) -> None:
    text_size = measure_text_cached(self._font_medium, text, font_size)
    rl.draw_text_ex(self._font_medium, text, rl.Vector2(x - text_size.x, y), font_size, 0, color)

  def _draw_tune_row(self, x: float, y: float, width: float, label: str, key: str, value: float, help_text: str) -> None:
    row_h = 88
    rl.draw_rectangle_rounded(rl.Rectangle(x, y, width, row_h), 0.12, 8, COLORS.CARD_BG)
    rl.draw_rectangle_rounded_lines_ex(rl.Rectangle(x, y, width, row_h), 0.12, 8, 2, COLORS.BORDER)

    rl.draw_text_ex(self._font_medium, label, rl.Vector2(x + 22, y + 17), FONT_SIZES.row_label, 0, COLORS.WHITE)
    rl.draw_text_ex(self._font_medium, help_text, rl.Vector2(x + 22, y + 58), FONT_SIZES.tiny, 0, COLORS.MUTED)

    value_text = f"{value:.2f}"
    value_size = measure_text_cached(self._font_bold, value_text, FONT_SIZES.row_value)
    value_x = x + width - 255 - value_size.x / 2
    rl.draw_text_ex(self._font_bold, value_text, rl.Vector2(value_x, y + 14), FONT_SIZES.row_value, 0, COLORS.WHITE)

    self._tune_buttons[(key, -1)].render(rl.Rectangle(x + width - 184, y + 8, 76, 72))
    self._tune_buttons[(key, 1)].render(rl.Rectangle(x + width - 92, y + 8, 76, 72))

  def _draw_signed_component_bar(self, x: float, y: float, width: float, height: float,
                                 values: list[tuple[str, float, rl.Color]], total: float) -> None:
    center_x = int(x + width / 2)
    half_width = int(width / 2 - 10)
    pos_sum = sum(max(value, 0.0) for _, value, _ in values)
    neg_sum = abs(sum(min(value, 0.0) for _, value, _ in values))
    scale = max(0.25, abs(total), pos_sum, neg_sum)

    rl.draw_rectangle_rounded(rl.Rectangle(x, y, width, height), 0.18, 8, COLORS.BAR_BG)
    rl.draw_rectangle_rounded_lines_ex(rl.Rectangle(x, y, width, height), 0.18, 8, 2, COLORS.BORDER)
    rl.draw_line(center_x, int(y - 7), center_x, int(y + height + 7), COLORS.BAR_ZERO)

    pos_x = center_x
    neg_x = center_x
    for _, value, color in values:
      segment_width = int(abs(value) / scale * half_width)
      if segment_width <= 0:
        continue
      if value >= 0.0:
        rl.draw_rectangle(pos_x, int(y + 5), segment_width, int(height - 10), color)
        pos_x += segment_width
      else:
        neg_x -= segment_width
        rl.draw_rectangle(neg_x, int(y + 5), segment_width, int(height - 10), color)

    total_x = int(center_x + _clamp(total / scale, -1.0, 1.0) * half_width)
    rl.draw_line(total_x, int(y - 11), total_x, int(y + height + 11), COLORS.BAR_MARKER)
    rl.draw_circle(total_x, int(y + height / 2), 7.0, COLORS.BAR_MARKER)

  def _draw_signed_single_bar(self, x: float, y: float, width: float, height: float, value: float, limit: float = 1.0) -> None:
    center_x = int(x + width / 2)
    half_width = int(width / 2 - 10)
    clipped = _clamp(value, -limit, limit)
    end_x = int(center_x + clipped / limit * half_width)
    bar_x = min(center_x, end_x)
    bar_w = abs(end_x - center_x)

    rl.draw_rectangle_rounded(rl.Rectangle(x, y, width, height), 0.18, 8, COLORS.BAR_BG)
    rl.draw_rectangle_rounded_lines_ex(rl.Rectangle(x, y, width, height), 0.18, 8, 2, COLORS.BORDER)
    rl.draw_line(center_x, int(y - 7), center_x, int(y + height + 7), COLORS.BAR_ZERO)
    if bar_w > 0:
      rl.draw_rectangle(bar_x, int(y + 5), bar_w, int(height - 10), COLORS.BAR_CMD)
    rl.draw_line(end_x, int(y - 11), end_x, int(y + height + 11), COLORS.BAR_MARKER)
    rl.draw_circle(end_x, int(y + height / 2), 7.0, COLORS.BAR_MARKER)

  def _draw_bar_legend(self, x: float, y: float, values: list[tuple[str, float, rl.Color]]) -> None:
    cursor_x = x
    for label, value, color in values:
      rl.draw_rectangle(int(cursor_x), int(y + 7), 20, 20, color)
      rl.draw_text_ex(self._font_medium, f"{label} {value:+.2f}", rl.Vector2(cursor_x + 30, y),
                      FONT_SIZES.tiny, 0, COLORS.WHITE)
      cursor_x += 170

  def _draw_command_composition(self, x: float, y: float, width: float, values: dict[str, float]) -> None:
    sm = ui_state.sm
    lateral_state = sm['controlsState'].lateralControlState
    if lateral_state.which() != "torqueState":
      rl.draw_text_ex(self._font_medium, "Waiting for torqueState", rl.Vector2(x, y), FONT_SIZES.section, 0, COLORS.MUTED)
      return

    torque_state = lateral_state.torqueState
    p_term = float(torque_state.p)
    i_term = float(torque_state.i)
    d_term = float(torque_state.d)
    f_term = float(torque_state.f)
    lat_total = p_term + i_term + d_term + f_term
    torque_cmd = float(sm['carControl'].actuators.torque)
    current_kp = float(_interp(sm['carState'].vEgo, LAT_TORQUE_INTERP_SPEEDS, LAT_TORQUE_KP_INTERP) * values["kpScale"])
    current_ki = float(LAT_TORQUE_KI * values["kiScale"])

    rl.draw_text_ex(self._font_medium, "PID + FF lateral-accel command", rl.Vector2(x, y),
                    FONT_SIZES.section, 0, COLORS.WHITE_TRANSLUCENT)
    self._draw_text_right(f"KP {current_kp:.3f}   KI {current_ki:.3f}   ERR {float(torque_state.error):+.2f}",
                          x + width, y, FONT_SIZES.small, COLORS.WHITE_TRANSLUCENT)

    components = [
      ("P", p_term, COLORS.BAR_P),
      ("I", i_term, COLORS.BAR_I),
      ("D", d_term, COLORS.BAR_D),
      ("FF", f_term, COLORS.BAR_F),
    ]
    self._draw_signed_component_bar(x, y + 54, width, 54, components, lat_total)
    self._draw_bar_legend(x, y + 122, components)
    self._draw_text_right(f"SUM {lat_total:+.2f} m/s²", x + width, y + 122, FONT_SIZES.tiny, COLORS.MUTED)

    rl.draw_text_ex(self._font_medium, "After LAT conversion: steering command", rl.Vector2(x, y + 176),
                    FONT_SIZES.section, 0, COLORS.WHITE_TRANSLUCENT)
    self._draw_text_right(f"CMD {torque_cmd:+.3f}", x + width, y + 176, FONT_SIZES.small, COLORS.WHITE_TRANSLUCENT)
    self._draw_signed_single_bar(x, y + 230, width, 50, torque_cmd)

  def _draw_torque_tune_panel(self, rect: rl.Rectangle, values: dict[str, float]) -> None:
    margin = 36
    x = rect.x + margin
    y = rect.y + margin
    width = rect.width - 2 * margin

    rl.draw_text_ex(self._font_bold, "TORQUE TUNE", rl.Vector2(x, y), FONT_SIZES.title, 0, COLORS.WHITE)
    rl.draw_text_ex(self._font_medium, "Full-screen driving tuner: model/limit knobs on the left, PID/FF scale knobs on the right.",
                    rl.Vector2(x, y + 78), FONT_SIZES.subtitle, 0, COLORS.WHITE_TRANSLUCENT)
    self._tune_reset_button.render(rl.Rectangle(x + width - 140, y + 4, 128, 76))

    col_gap = 28
    col_w = (width - col_gap) / 2
    left_x = x
    right_x = x + col_w + col_gap
    rows_y = y + 142

    rl.draw_text_ex(self._font_medium, "MODEL / LIMIT", rl.Vector2(left_x, rows_y), FONT_SIZES.section, 0, COLORS.WHITE_TRANSLUCENT)
    rl.draw_text_ex(self._font_medium, "PID / FF SCALE", rl.Vector2(right_x, rows_y), FONT_SIZES.section, 0, COLORS.WHITE_TRANSLUCENT)

    row_gap = 18
    row_h = 88
    rows = (
      (("LAT", "latAccelFactor", "accel-to-torque model"), ("KP", "kpScale", "P gain multiplier")),
      (("F", "friction", "friction in FF"), ("KI", "kiScale", "I gain multiplier")),
      (("MAX", "maxLatAccel", "request accel cap"), ("FF", "ffScale", "feedforward multiplier")),
    )
    for idx, (left, right) in enumerate(rows):
      row_y = rows_y + 46 + idx * (row_h + row_gap)
      self._draw_tune_row(left_x, row_y, col_w, left[0], left[1], values[left[1]], left[2])
      self._draw_tune_row(right_x, row_y, col_w, right[0], right[1], values[right[1]], right[2])

    self._draw_command_composition(x, rows_y + 386, width, values)
