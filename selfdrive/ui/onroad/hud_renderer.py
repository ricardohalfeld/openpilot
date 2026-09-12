import pyray as rl
from functools import partial
from dataclasses import dataclass
from openpilot.common.constants import CV
from openpilot.selfdrive.controls.lib.latcontrol_torque import (
  INTERP_SPEEDS as LAT_TORQUE_INTERP_SPEEDS,
  KI as LAT_TORQUE_KI,
  KP_INTERP as LAT_TORQUE_KP_INTERP,
)
from openpilot.selfdrive.ui.onroad.exp_button import ExpButton
from openpilot.selfdrive.ui.ui_state import ui_state, UIStatus
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.multilang import tr
from openpilot.system.ui.lib.text_measure import measure_text_cached
from openpilot.system.ui.widgets.button import Button, ButtonStyle
from openpilot.system.ui.widgets import Widget

# Constants
SET_SPEED_NA = 255
KM_TO_MILE = 0.621371
TORQUE_TUNE_OVERRIDE_PARAM = "TorqueTuneOverride"
TUNE_STEP = {
  "latAccelFactor": 0.05,
  "friction": 0.01,
  "maxLatAccel": 0.10,
}
TUNE_LIMITS = {
  "latAccelFactor": (1.5, 3.5),
  "friction": (0.0, 0.25),
  "maxLatAccel": (1.5, 3.5),
}
CRUISE_DISABLED_CHAR = '–'


@dataclass(frozen=True)
class UIConfig:
  header_height: int = 300
  border_size: int = 30
  button_size: int = 192
  set_speed_width_metric: int = 200
  set_speed_width_imperial: int = 172
  set_speed_height: int = 204
  wheel_icon_size: int = 144
  tune_panel_width: int = 960
  tune_panel_height: int = 680
  tune_button_size: int = 88


@dataclass(frozen=True)
class FontSizes:
  current_speed: int = 176
  speed_unit: int = 66
  max_speed: int = 40
  set_speed: int = 90
  tune_title: int = 44
  tune_label: int = 38
  tune_value: int = 46
  tune_small: int = 27
  tune_tiny: int = 22


@dataclass(frozen=True)
class Colors:
  WHITE = rl.WHITE
  DISENGAGED = rl.Color(145, 155, 149, 255)
  OVERRIDE = rl.Color(145, 155, 149, 255)  # Added
  ENGAGED = rl.Color(128, 216, 166, 255)
  DISENGAGED_BG = rl.Color(0, 0, 0, 153)
  OVERRIDE_BG = rl.Color(145, 155, 149, 204)
  ENGAGED_BG = rl.Color(128, 216, 166, 204)
  GREY = rl.Color(166, 166, 166, 255)
  DARK_GREY = rl.Color(114, 114, 114, 255)
  BLACK_TRANSLUCENT = rl.Color(0, 0, 0, 166)
  WHITE_TRANSLUCENT = rl.Color(255, 255, 255, 200)
  BORDER_TRANSLUCENT = rl.Color(255, 255, 255, 75)
  HEADER_GRADIENT_START = rl.Color(0, 0, 0, 114)
  HEADER_GRADIENT_END = rl.BLANK
  BAR_BG = rl.Color(20, 20, 20, 205)
  BAR_ZERO = rl.Color(255, 255, 255, 220)
  BAR_MARKER = rl.Color(255, 255, 255, 255)
  BAR_P = rl.Color(80, 180, 255, 255)
  BAR_I = rl.Color(255, 190, 70, 255)
  BAR_D = rl.Color(190, 120, 255, 255)
  BAR_F = rl.Color(90, 230, 120, 255)
  BAR_CMD = rl.Color(255, 95, 95, 255)


UI_CONFIG = UIConfig()
FONT_SIZES = FontSizes()
COLORS = Colors()


def _clamp(value: float, lo: float, hi: float) -> float:
  return min(max(value, lo), hi)


class HudRenderer(Widget):
  def __init__(self):
    super().__init__()
    """Initialize the HUD renderer."""
    self.is_cruise_set: bool = False
    self.is_cruise_available: bool = True
    self.set_speed: float = SET_SPEED_NA
    self.speed: float = 0.0
    self.v_ego_cluster_seen: bool = False

    self._font_semi_bold: rl.Font = gui_app.font(FontWeight.SEMI_BOLD)
    self._font_bold: rl.Font = gui_app.font(FontWeight.BOLD)
    self._font_medium: rl.Font = gui_app.font(FontWeight.MEDIUM)

    self._exp_button: ExpButton = ExpButton(UI_CONFIG.button_size, UI_CONFIG.wheel_icon_size)
    self._tune_buttons: dict[tuple[str, int], Button] = {}
    for key in TUNE_STEP:
      for direction, text in ((-1, "-"), (1, "+")):
        self._tune_buttons[(key, direction)] = self._child(Button(text, partial(self._adjust_tune, key, direction),
                                                                  font_size=58, button_style=ButtonStyle.TRANSPARENT_WHITE_BORDER,
                                                                  border_radius=8))
    self._tune_reset_button = self._child(Button("RST", self._reset_tune, font_size=42,
                                                 button_style=ButtonStyle.TRANSPARENT_WHITE_BORDER, border_radius=8))

  def _update_state(self) -> None:
    """Update HUD state based on car state and controls state."""
    sm = ui_state.sm
    if sm.recv_frame["carState"] < ui_state.started_frame:
      self.is_cruise_set = False
      self.set_speed = SET_SPEED_NA
      self.speed = 0.0
      return

    controls_state = sm['controlsState']
    car_state = sm['carState']

    v_cruise_cluster = car_state.vCruiseCluster
    self.set_speed = (
      controls_state.vCruiseDEPRECATED if v_cruise_cluster == 0.0 else v_cruise_cluster
    )
    self.is_cruise_set = 0 < self.set_speed < SET_SPEED_NA
    self.is_cruise_available = self.set_speed != -1

    if self.is_cruise_set and not ui_state.is_metric:
      self.set_speed *= KM_TO_MILE

    v_ego_cluster = car_state.vEgoCluster
    self.v_ego_cluster_seen = self.v_ego_cluster_seen or v_ego_cluster != 0.0
    v_ego = v_ego_cluster if self.v_ego_cluster_seen else car_state.vEgo
    speed_conversion = CV.MS_TO_KPH if ui_state.is_metric else CV.MS_TO_MPH
    self.speed = max(0.0, v_ego * speed_conversion)

  def _render(self, rect: rl.Rectangle) -> None:
    """Render HUD elements to the screen."""
    # Draw the header background
    rl.draw_rectangle_gradient_v(
      int(rect.x),
      int(rect.y),
      int(rect.width),
      UI_CONFIG.header_height,
      COLORS.HEADER_GRADIENT_START,
      COLORS.HEADER_GRADIENT_END,
    )

    if self.is_cruise_available:
      self._draw_set_speed(rect)

    self._draw_current_speed(rect)
    self._draw_torque_tune_panel(rect)

    button_x = rect.x + rect.width - UI_CONFIG.border_size - UI_CONFIG.button_size
    button_y = rect.y + UI_CONFIG.border_size
    self._exp_button.render(rl.Rectangle(button_x, button_y, UI_CONFIG.button_size, UI_CONFIG.button_size))

  def user_interacting(self) -> bool:
    return self._exp_button.is_pressed

  def _draw_set_speed(self, rect: rl.Rectangle) -> None:
    """Draw the MAX speed indicator box."""
    set_speed_width = UI_CONFIG.set_speed_width_metric if ui_state.is_metric else UI_CONFIG.set_speed_width_imperial
    x = rect.x + 60 + (UI_CONFIG.set_speed_width_imperial - set_speed_width) // 2
    y = rect.y + 45

    set_speed_rect = rl.Rectangle(x, y, set_speed_width, UI_CONFIG.set_speed_height)
    rl.draw_rectangle_rounded(set_speed_rect, 0.35, 10, COLORS.BLACK_TRANSLUCENT)
    rl.draw_rectangle_rounded_lines_ex(set_speed_rect, 0.35, 10, 6, COLORS.BORDER_TRANSLUCENT)

    max_color = COLORS.GREY
    set_speed_color = COLORS.DARK_GREY
    if self.is_cruise_set:
      set_speed_color = COLORS.WHITE
      if ui_state.status == UIStatus.ENGAGED:
        max_color = COLORS.ENGAGED
      elif ui_state.status == UIStatus.DISENGAGED:
        max_color = COLORS.DISENGAGED
      elif ui_state.status == UIStatus.OVERRIDE:
        max_color = COLORS.OVERRIDE

    max_text = tr("MAX")
    max_text_width = measure_text_cached(self._font_semi_bold, max_text, FONT_SIZES.max_speed).x
    rl.draw_text_ex(
      self._font_semi_bold,
      max_text,
      rl.Vector2(x + (set_speed_width - max_text_width) / 2, y + 27),
      FONT_SIZES.max_speed,
      0,
      max_color,
    )

    set_speed_text = CRUISE_DISABLED_CHAR if not self.is_cruise_set else str(round(self.set_speed))
    speed_text_width = measure_text_cached(self._font_bold, set_speed_text, FONT_SIZES.set_speed).x
    rl.draw_text_ex(
      self._font_bold,
      set_speed_text,
      rl.Vector2(x + (set_speed_width - speed_text_width) / 2, y + 77),
      FONT_SIZES.set_speed,
      0,
      set_speed_color,
    )

  def _draw_current_speed(self, rect: rl.Rectangle) -> None:
    """Draw the current vehicle speed and unit."""
    speed_text = str(round(self.speed))
    speed_text_size = measure_text_cached(self._font_bold, speed_text, FONT_SIZES.current_speed)
    speed_pos = rl.Vector2(rect.x + rect.width / 2 - speed_text_size.x / 2, 180 - speed_text_size.y / 2)
    rl.draw_text_ex(self._font_bold, speed_text, speed_pos, FONT_SIZES.current_speed, 0, COLORS.WHITE)

    unit_text = tr("km/h") if ui_state.is_metric else tr("mph")
    unit_text_size = measure_text_cached(self._font_medium, unit_text, FONT_SIZES.speed_unit)
    unit_pos = rl.Vector2(rect.x + rect.width / 2 - unit_text_size.x / 2, 290 - unit_text_size.y / 2)
    rl.draw_text_ex(self._font_medium, unit_text, unit_pos, FONT_SIZES.speed_unit, 0, COLORS.WHITE_TRANSLUCENT)

  def _default_tune_values(self) -> dict[str, float] | None:
    if ui_state.CP is None or ui_state.CP.lateralTuning.which() != "torque":
      return None

    torque = ui_state.CP.lateralTuning.torque
    return {
      "latAccelFactor": float(torque.latAccelFactor),
      "friction": float(torque.friction),
      "maxLatAccel": float(ui_state.CP.maxLateralAccel),
    }

  def _tune_values(self) -> dict[str, float] | None:
    values = self._default_tune_values()
    if values is None:
      return None

    override = ui_state.params.get(TORQUE_TUNE_OVERRIDE_PARAM)
    if isinstance(override, dict) and override.get("enabled", False):
      for key in values:
        if key in override:
          values[key] = float(override[key])
    return values

  def _write_tune_values(self, values: dict[str, float]) -> None:
    ui_state.params.put_nonblocking(TORQUE_TUNE_OVERRIDE_PARAM, {
      "enabled": True,
      "latAccelFactor": round(values["latAccelFactor"], 3),
      "friction": round(values["friction"], 3),
      "maxLatAccel": round(values["maxLatAccel"], 3),
    })

  def _adjust_tune(self, key: str, direction: int) -> None:
    values = self._tune_values()
    if values is None:
      return

    lo, hi = TUNE_LIMITS[key]
    values[key] = min(max(values[key] + direction * TUNE_STEP[key], lo), hi)
    self._write_tune_values(values)

  def _reset_tune(self) -> None:
    ui_state.params.remove(TORQUE_TUNE_OVERRIDE_PARAM)

  def _draw_text_right(self, text: str, x: float, y: float, font_size: int, color: rl.Color = COLORS.WHITE) -> None:
    text_size = measure_text_cached(self._font_medium, text, font_size)
    rl.draw_text_ex(self._font_medium, text, rl.Vector2(x - text_size.x, y), font_size, 0, color)

  def _draw_signed_component_bar(self, x: float, y: float, width: float, height: float,
                                 values: list[tuple[str, float, rl.Color]], total: float) -> None:
    center_x = int(x + width / 2)
    half_width = int(width / 2 - 8)
    pos_sum = sum(max(value, 0.0) for _, value, _ in values)
    neg_sum = abs(sum(min(value, 0.0) for _, value, _ in values))
    scale = max(0.25, abs(total), pos_sum, neg_sum)

    rl.draw_rectangle_rounded(rl.Rectangle(x, y, width, height), 0.20, 8, COLORS.BAR_BG)
    rl.draw_rectangle_rounded_lines_ex(rl.Rectangle(x, y, width, height), 0.20, 8, 2, COLORS.BORDER_TRANSLUCENT)
    rl.draw_line(center_x, int(y - 5), center_x, int(y + height + 5), COLORS.BAR_ZERO)

    pos_x = center_x
    neg_x = center_x
    for _, value, color in values:
      segment_width = int(abs(value) / scale * half_width)
      if segment_width <= 0:
        continue
      if value >= 0.0:
        rl.draw_rectangle(pos_x, int(y + 4), segment_width, int(height - 8), color)
        pos_x += segment_width
      else:
        neg_x -= segment_width
        rl.draw_rectangle(neg_x, int(y + 4), segment_width, int(height - 8), color)

    total_x = int(center_x + _clamp(total / scale, -1.0, 1.0) * half_width)
    rl.draw_line(total_x, int(y - 9), total_x, int(y + height + 9), COLORS.BAR_MARKER)
    rl.draw_circle(total_x, int(y + height / 2), 6.0, COLORS.BAR_MARKER)

  def _draw_signed_single_bar(self, x: float, y: float, width: float, height: float, value: float, limit: float = 1.0) -> None:
    center_x = int(x + width / 2)
    half_width = int(width / 2 - 8)
    clipped = _clamp(value, -limit, limit)
    end_x = int(center_x + clipped / limit * half_width)
    bar_x = min(center_x, end_x)
    bar_w = abs(end_x - center_x)

    rl.draw_rectangle_rounded(rl.Rectangle(x, y, width, height), 0.20, 8, COLORS.BAR_BG)
    rl.draw_rectangle_rounded_lines_ex(rl.Rectangle(x, y, width, height), 0.20, 8, 2, COLORS.BORDER_TRANSLUCENT)
    rl.draw_line(center_x, int(y - 5), center_x, int(y + height + 5), COLORS.BAR_ZERO)
    if bar_w > 0:
      rl.draw_rectangle(bar_x, int(y + 4), bar_w, int(height - 8), COLORS.BAR_CMD)
    rl.draw_line(end_x, int(y - 9), end_x, int(y + height + 9), COLORS.BAR_MARKER)
    rl.draw_circle(end_x, int(y + height / 2), 6.0, COLORS.BAR_MARKER)

  def _draw_bar_legend(self, x: float, y: float, values: list[tuple[str, float, rl.Color]]) -> None:
    cursor_x = x
    for label, value, color in values:
      rl.draw_rectangle(int(cursor_x), int(y + 6), 18, 18, color)
      rl.draw_text_ex(self._font_medium, f"{label} {value:+.2f}", rl.Vector2(cursor_x + 26, y),
                      FONT_SIZES.tune_tiny, 0, COLORS.WHITE)
      cursor_x += 150

  def _draw_command_composition(self, panel_x: float, panel_y: float, panel_width: float) -> None:
    sm = ui_state.sm
    lateral_state = sm['controlsState'].lateralControlState
    if lateral_state.which() != "torqueState":
      return

    torque_state = lateral_state.torqueState
    p_term = float(torque_state.p)
    i_term = float(torque_state.i)
    d_term = float(torque_state.d)
    f_term = float(torque_state.f)
    lat_total = p_term + i_term + d_term + f_term
    torque_cmd = float(sm['carControl'].actuators.torque)
    current_kp = self._current_torque_kp()

    x = panel_x + 36
    w = panel_width - 72
    y = panel_y + 402

    rl.draw_text_ex(self._font_medium, f"KP/KI {current_kp:.3f} / {LAT_TORQUE_KI:.3f}    ERR {float(torque_state.error):+.2f}",
                    rl.Vector2(x, y), FONT_SIZES.tune_small, 0, COLORS.WHITE_TRANSLUCENT)

    values = [
      ("P", p_term, COLORS.BAR_P),
      ("I", i_term, COLORS.BAR_I),
      ("D", d_term, COLORS.BAR_D),
      ("FF", f_term, COLORS.BAR_F),
    ]
    rl.draw_text_ex(self._font_medium, "LAT ACCEL COMPONENTS", rl.Vector2(x, y + 43),
                    FONT_SIZES.tune_tiny, 0, COLORS.WHITE_TRANSLUCENT)
    self._draw_text_right(f"SUM {lat_total:+.2f}", x + w, y + 43, FONT_SIZES.tune_tiny, COLORS.WHITE_TRANSLUCENT)
    self._draw_signed_component_bar(x, y + 76, w, 36, values, lat_total)
    self._draw_bar_legend(x, y + 120, values)

    rl.draw_text_ex(self._font_medium, "STEERING COMMAND", rl.Vector2(x, y + 158),
                    FONT_SIZES.tune_tiny, 0, COLORS.WHITE_TRANSLUCENT)
    self._draw_text_right(f"CMD {torque_cmd:+.3f}", x + w, y + 158, FONT_SIZES.tune_tiny, COLORS.WHITE_TRANSLUCENT)
    self._draw_signed_single_bar(x, y + 190, w, 34, torque_cmd)

  def _current_torque_kp(self) -> float:
    return float(_interp(ui_state.sm['carState'].vEgo, LAT_TORQUE_INTERP_SPEEDS, LAT_TORQUE_KP_INTERP))

  def _draw_torque_tune_panel(self, rect: rl.Rectangle) -> None:
    values = self._tune_values()
    if values is None:
      return

    panel_x = rect.x + rect.width - UI_CONFIG.border_size - UI_CONFIG.tune_panel_width
    panel_y = rect.y + UI_CONFIG.border_size + UI_CONFIG.button_size + 24
    panel_rect = rl.Rectangle(panel_x, panel_y, UI_CONFIG.tune_panel_width, UI_CONFIG.tune_panel_height)
    rl.draw_rectangle_rounded(panel_rect, 0.08, 10, COLORS.BLACK_TRANSLUCENT)
    rl.draw_rectangle_rounded_lines_ex(panel_rect, 0.08, 10, 3, COLORS.BORDER_TRANSLUCENT)

    rl.draw_text_ex(self._font_medium, "TORQUE TUNE", rl.Vector2(panel_x + 36, panel_y + 28),
                    FONT_SIZES.tune_title, 0, COLORS.WHITE_TRANSLUCENT)
    self._tune_reset_button.render(rl.Rectangle(panel_x + UI_CONFIG.tune_panel_width - 156, panel_y + 20, 118, 72))

    rows = (
      ("LAT", "latAccelFactor"),
      ("F", "friction"),
      ("MAX", "maxLatAccel"),
    )
    for idx, (label, key) in enumerate(rows):
      row_y = panel_y + 112 + idx * 92
      rl.draw_text_ex(self._font_medium, label, rl.Vector2(panel_x + 40, row_y + 22),
                      FONT_SIZES.tune_label, 0, COLORS.WHITE)
      value_text = f"{values[key]:.2f}"
      value_text_size = measure_text_cached(self._font_medium, value_text, FONT_SIZES.tune_value)
      rl.draw_text_ex(self._font_medium, value_text, rl.Vector2(panel_x + 360 - value_text_size.x / 2, row_y + 16),
                      FONT_SIZES.tune_value, 0, COLORS.WHITE)

      self._tune_buttons[(key, -1)].render(rl.Rectangle(panel_x + 590, row_y, UI_CONFIG.tune_button_size, UI_CONFIG.tune_button_size))
      self._tune_buttons[(key, 1)].render(rl.Rectangle(panel_x + 742, row_y, UI_CONFIG.tune_button_size, UI_CONFIG.tune_button_size))

    self._draw_command_composition(panel_x, panel_y, UI_CONFIG.tune_panel_width)


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
