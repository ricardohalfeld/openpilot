import pyray as rl
from functools import partial
from dataclasses import dataclass
from openpilot.common.constants import CV
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
  tune_panel_height: int = 500
  tune_button_size: int = 104


@dataclass(frozen=True)
class FontSizes:
  current_speed: int = 176
  speed_unit: int = 66
  max_speed: int = 40
  set_speed: int = 90
  tune_label: int = 48
  tune_value: int = 58


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


UI_CONFIG = UIConfig()
FONT_SIZES = FontSizes()
COLORS = Colors()


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
                                                                  font_size=64, button_style=ButtonStyle.TRANSPARENT_WHITE_BORDER,
                                                                  border_radius=8))
    self._tune_reset_button = self._child(Button("RST", self._reset_tune, font_size=44,
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

  def _draw_torque_tune_panel(self, rect: rl.Rectangle) -> None:
    values = self._tune_values()
    if values is None:
      return

    panel_x = rect.x + rect.width - UI_CONFIG.border_size - UI_CONFIG.tune_panel_width
    panel_y = rect.y + UI_CONFIG.border_size + UI_CONFIG.button_size + 24
    panel_rect = rl.Rectangle(panel_x, panel_y, UI_CONFIG.tune_panel_width, UI_CONFIG.tune_panel_height)
    rl.draw_rectangle_rounded(panel_rect, 0.08, 10, COLORS.BLACK_TRANSLUCENT)
    rl.draw_rectangle_rounded_lines_ex(panel_rect, 0.08, 10, 3, COLORS.BORDER_TRANSLUCENT)

    rl.draw_text_ex(self._font_medium, "TORQUE TUNE", rl.Vector2(panel_x + 36, panel_y + 30),
                    FONT_SIZES.tune_label, 0, COLORS.WHITE_TRANSLUCENT)
    self._tune_reset_button.render(rl.Rectangle(panel_x + UI_CONFIG.tune_panel_width - 168, panel_y + 24, 128, 78))

    rows = (
      ("LAT", "latAccelFactor"),
      ("F", "friction"),
      ("MAX", "maxLatAccel"),
    )
    for idx, (label, key) in enumerate(rows):
      row_y = panel_y + 132 + idx * 112
      rl.draw_text_ex(self._font_medium, label, rl.Vector2(panel_x + 40, row_y + 26),
                      FONT_SIZES.tune_label, 0, COLORS.WHITE)
      value_text = f"{values[key]:.2f}"
      value_text_size = measure_text_cached(self._font_medium, value_text, FONT_SIZES.tune_value)
      rl.draw_text_ex(self._font_medium, value_text, rl.Vector2(panel_x + 392 - value_text_size.x / 2, row_y + 22),
                      FONT_SIZES.tune_value, 0, COLORS.WHITE)

      self._tune_buttons[(key, -1)].render(rl.Rectangle(panel_x + 608, row_y, UI_CONFIG.tune_button_size, UI_CONFIG.tune_button_size))
      self._tune_buttons[(key, 1)].render(rl.Rectangle(panel_x + 768, row_y, UI_CONFIG.tune_button_size, UI_CONFIG.tune_button_size))
