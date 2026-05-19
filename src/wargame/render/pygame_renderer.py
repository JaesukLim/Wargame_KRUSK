"""2D simulation renderer based on pygame."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from ..core.battlefield import BattleField
from ..core.types import Point, Side, UnitKind
from ..core.unit import ShellImpact, Unit


@dataclass
class RenderConfig:
    width: int = 1280
    height: int = 860
    fps: int = 60
    margin: int = 40
    show_grid: bool = False
    show_paths: bool = True
    line_click_threshold_px: int = 10


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    v = value.lstrip("#")
    if len(v) == 6:
        return tuple(int(v[i : i + 2], 16) for i in (0, 2, 4))
    return 200, 200, 200


def _unit_radius(sim_unit: Unit, scale: float) -> int:
    return max(8, int(16 * scale * sim_unit.normalized_strength ** 0.4))


def _unit_symbol_size(sim_unit: Unit) -> tuple[int, int]:
    if sim_unit.is_artillery:
        return 34, 28
    return 38, 28


def _point_to_screen(p: Point, world_to_screen) -> tuple[int, int]:
    x, y = world_to_screen(p)
    return int(x), int(y)


class PygameRenderer:
    def __init__(self, world, config: RenderConfig):
        self.world: BattleField = world
        self.config = config
        self._selected_contact = None
        self._selected_shell = None
        self._pressed = None
        self._hover = None
        self._world_to_screen = None

    def _init(self):
        import pygame

        pygame.init()
        self.screen = pygame.display.set_mode((self.config.width, self.config.height))
        self.surface = self.screen
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 14)
        self.font_big = pygame.font.SysFont("consolas", 18, bold=True)
        pygame.display.set_caption("Wargame KRUSK - 2D View")

        # auto world transform
        min_x, min_y, max_x, max_y = self.world.terrain.bounds
        w = max_x - min_x
        h = max_y - min_y
        sx = (self.config.width - 2 * self.config.margin) / w
        sy = (self.config.height - 2 * self.config.margin) / h
        scale = min(sx, sy)
        ox = self.config.margin
        oy = self.config.margin + h * scale

        def transform(pos: Point) -> tuple[float, float]:
            return ox + (pos.x - min_x) * scale, oy - (pos.y - min_y) * scale

        self._world_to_screen = transform
        self._scale = scale

    def run(self):
        import pygame

        self._init()
        running = True
        while running:
            dt = self.clock.tick(self.config.fps) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    running = False
                elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                    self._on_click(pygame.mouse.get_pos())

            if self.world is not None:
                self.world.update(dt)
                self._draw()
                self._draw_ui()
                pygame.display.flip()
        pygame.quit()

    def _draw(self) -> None:
        import pygame

        self.surface.fill((12, 16, 24))
        self._draw_terrain()
        self._draw_contacts()
        self._draw_shells()
        self._draw_units()

    def _draw_terrain(self) -> None:
        import pygame

        # light terrain background based on terrain type
        # avoid drawing millions of rects? only 40x50 here.
        for cell in self.world.terrain.all_units():
            x1, y1 = _point_to_screen(Point(cell.x - self.world.terrain.cell_size_m / 2, cell.y - self.world.terrain.cell_size_m / 2), self._world_to_screen)
            x2, y2 = _point_to_screen(Point(cell.x + self.world.terrain.cell_size_m / 2, cell.y + self.world.terrain.cell_size_m / 2), self._world_to_screen)
            size_x = max(1, abs(x2 - x1))
            size_y = max(1, abs(y2 - y1))
            left = min(x1, x2)
            top = min(y1, y2)
            if cell.landform_name == "water":
                color = (25, 54, 108)
            elif cell.landform_name == "hill":
                color = (95, 132, 80)
            else:
                color = (88, 112, 72)
            pygame.draw.rect(self.surface, color, (left, top, size_x, size_y))
            if self.config.show_grid:
                pygame.draw.rect(self.surface, (40, 40, 40), (left, top, size_x, size_y), width=1)

    def _draw_units(self) -> None:
        import pygame

        for u in self.world.alive_units():
            pos = _point_to_screen(u.position, self._world_to_screen)
            rgb = (220, 70, 80) if u.side == Side.RED else (70, 110, 220)
            self._draw_unit_symbol(u, pos, rgb)

            txt = f"{u.name[:8]} {u.strength:,.0f}"
            self.surface.blit(self.font.render(txt, True, (250, 250, 250)), (pos[0] + 24, pos[1] - 8))

            if self.config.show_paths and u.movement_path.waypoints:
                # draw path
                points = [_point_to_screen(p, self._world_to_screen) for p in u.movement_path.waypoints]
                if len(points) > 1:
                    pygame.draw.lines(self.surface, (200, 200, 80), False, points, 1)

    def _draw_unit_symbol(self, u: Unit, pos: tuple[int, int], side_color: tuple[int, int, int]) -> None:
        """Draw a NATO-like unit marker whose interior acts as a strength gauge."""

        import pygame

        w, h = _unit_symbol_size(u)
        rect = pygame.Rect(pos[0] - w // 2, pos[1] - h // 2, w, h)
        pygame.draw.rect(self.surface, (18, 22, 30), rect, border_radius=3)

        # "Water-drain" gauge: remaining combat power fills from bottom upward.
        fill_h = int((h - 4) * u.normalized_strength)
        fill_rect = pygame.Rect(rect.left + 2, rect.bottom - 2 - fill_h, w - 4, fill_h)
        gauge_color = tuple(min(255, int(c * 0.95 + 35)) for c in side_color)
        pygame.draw.rect(self.surface, gauge_color, fill_rect)

        pygame.draw.rect(self.surface, side_color, rect, width=2, border_radius=3)

        cx, cy = pos
        if u.is_artillery:
            pygame.draw.circle(self.surface, (245, 245, 245), (cx, cy), 4)
            pygame.draw.line(self.surface, (245, 245, 245), (cx - 10, cy + 7), (cx + 10, cy + 7), 2)
        else:
            pygame.draw.ellipse(self.surface, (245, 245, 245), (cx - 12, cy - 6, 24, 12), 2)
            pygame.draw.line(self.surface, (245, 245, 245), (cx - 8, cy), (cx + 8, cy), 2)

        echelon = "III" if u.is_artillery else "I"
        self.surface.blit(self.font.render(echelon, True, (240, 240, 240)), (rect.left + 2, rect.top - 14))

    def _draw_contacts(self) -> None:
        import pygame

        for c in self.world.contacts.values():
            u = self.world.units.get(c.attacker_id)
            v = self.world.units.get(c.defender_id)
            if not u or not v:
                continue
            p1 = _point_to_screen(u.position, self._world_to_screen)
            p2 = _point_to_screen(v.position, self._world_to_screen)
            pygame.draw.line(self.surface, (220, 190, 90), p1, p2, 3)

    def _draw_shells(self) -> None:
        import pygame

        now = self.world.time_s
        for s in self.world.shells.values():
            if not s.is_enroute:
                continue
            # draw moving indicator line
            p0 = _point_to_screen(s.start_pos, self._world_to_screen)
            p1 = _point_to_screen(s.target_pos, self._world_to_screen)
            pygame.draw.line(self.surface, (255, 90, 30), p0, p1, 1)
            t = min(1.0, max(0.0, 1 - (s.remaining_time(now) / max(1.0, s.impact_time - s.launch_time))))
            px = int(p0[0] + (p1[0] - p0[0]) * t)
            py = int(p0[1] + (p1[1] - p0[1]) * t)
            pygame.draw.circle(self.surface, (255, 160, 60), (px, py), 4)

    def _draw_ui(self) -> None:
        import pygame

        snap = self.world.snapshot()
        info_lines = [
            f"time={snap.time_s:6.1f}s",
            f"active units: {snap.active_units}",
            f"red={snap.red_strength:,.1f}  blue={snap.blue_strength:,.1f}",
            f"contacts={snap.active_contacts}",
            "LMB: click line/units for combat detail",
            "ESC: quit",
        ]

        # status panel
        x = 12
        y = 8
        for line in info_lines:
            self.surface.blit(self.font.render(line, True, (230, 230, 230)), (x, y))
            y += 19

        if self._selected_contact:
            c = self._selected_contact
            y += 8
            text = f"Contact: {c['a']} <-> {c['b']}"
            self.surface.blit(self.font_big.render(text, True, (255, 228, 170)), (x, y))
            y += 24
            det = c["kills"]
            self.surface.blit(self.font.render(f"loss A={det[0]:.2f}, loss B={det[1]:.2f}", True, (240, 240, 240)), (x, y))
            y += 19
            if c.get("k"):
                k = c["k"]
                self.surface.blit(self.font.render(f"kAB={k[0]:.5f}, kBA={k[1]:.5f}, range={c.get('range_m',0):.0f}m", True, (240, 240, 240)), (x, y))
            y += 19
            if c.get("shells"):
                self.surface.blit(self.font.render(f"Incoming shells: {len(c['shells'])}", True, (240, 240, 240)), (x, y))

        if self._hover:
            text = f"hover: {self._hover}"
            self.surface.blit(self.font.render(text, True, (200, 250, 200)), (x, self.config.height - 22))

    def _on_click(self, pos: tuple[int, int]) -> None:
        # 1) unit hit-test by gauge circle radius
        world_click = pos

        for c in self.world.contacts.values():
            a = self.world.units.get(c.attacker_id)
            b = self.world.units.get(c.defender_id)
            if not a or not b:
                continue
            p1 = _point_to_screen(a.position, self._world_to_screen)
            p2 = _point_to_screen(b.position, self._world_to_screen)
            d = self._distance_point_to_segment(world_click, p1, p2)
            if d <= self.config.line_click_threshold_px:
                shell_ids = [
                    s.shell_id
                    for s in self.world.shells.values()
                    if s.is_enroute and s.target_id in (a.id, b.id)
                ]
                self._selected_contact = {
                    "a": a.id,
                    "b": b.id,
                    "kills": c.last_deltas,
                    "k": c.last_k,
                    "range_m": c.last_range_m,
                    "terrain_factors": c.terrain_factors,
                    "shells": shell_ids,
                }
                return

        # unit pick fallback
        for unit in self.world.alive_units():
            p = _point_to_screen(unit.position, self._world_to_screen)
            w, h = _unit_symbol_size(unit)
            if abs(p[0] - world_click[0]) <= w // 2 and abs(p[1] - world_click[1]) <= h // 2:
                self._hover = unit.id
                self._selected_contact = {
                    "a": unit.id,
                    "b": "(unit)",
                    "kills": (unit.strength, unit.max_strength),
                    "k": None,
                    "range_m": 0,
                    "shells": [],
                }
                return

        self._selected_contact = None
        self._hover = None

    @staticmethod
    def _distance_point_to_segment(point: tuple[int, int], a: tuple[int, int], b: tuple[int, int]) -> float:
        ax, ay = a
        bx, by = b
        px, py = point
        vx = bx - ax
        vy = by - ay
        wx = px - ax
        wy = py - ay
        vv = vx * vx + vy * vy
        if vv == 0:
            return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
        t = max(0.0, min(1.0, (wx * vx + wy * vy) / vv))
        closest_x = ax + t * vx
        closest_y = ay + t * vy
        return ((px - closest_x) ** 2 + (py - closest_y) ** 2) ** 0.5
