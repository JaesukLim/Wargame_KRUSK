"""Optional Panda3D 3D view.

This module is intentionally lightweight and degrades gracefully when Panda3D is not installed.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.battlefield import BattleField


@dataclass
class Panda3DConfig:
    free_cam_speed: float = 60.0
    target_cam_speed: float = 120.0


class Panda3DRenderer:
    def __init__(self, world: BattleField, config: Panda3DConfig | None = None):
        self.world = world
        self.config = config or Panda3DConfig()

    def run(self) -> None:
        try:
            from direct.showbase.ShowBase import ShowBase
            from direct.task import Task
            from panda3d.core import (
                AmbientLight,
                DirectionalLight,
                LColor,
                LPoint3,
                NodePath,
                TextNode,
                loadPrcFileData,
            )
        except Exception as exc:  # pragma: no cover - depends on env
            raise RuntimeError(
                "Panda3D is not installed in this environment. Install with 'pip install panda3d'."
            ) from exc

        loadPrcFileData("", "window-title Wargame KRUSK - 3D")

        class _App(ShowBase):
            def __init__(self, outer):
                ShowBase.__init__(self)
                self.outer = outer
                self._time = 0.0

                self.disableMouse()
                self._setup_world()
                self._setup_camera()
                self._setup_hud()

                self.taskMgr.add(self._tick, "sim_tick")
                self.taskMgr.add(self._render_tick, "render_tick")

                self.accept("escape", self.userExit)
                self.accept("1", self._focus_unit, [0])
                self.accept("2", self._focus_unit, [1])
                self.accept("3", self._focus_unit, [2])
                self.accept("4", self._focus_unit, [3])
                self.accept("5", self._focus_unit, [4])
                self.accept("f1", self._toggle_view)

                self.focus_index = 0

            def _setup_world(self):
                # lights
                ambient = AmbientLight("ambient")
                ambient.setColor(LColor(0.35, 0.35, 0.35, 1))
                ambient_np = self.render.attachNewNode(ambient)
                self.render.setLight(ambient_np)

                directional = DirectionalLight("sun")
                directional.setDirection((-1, -1, -2))
                directional.setColor(LColor(0.75, 0.75, 0.7, 1))
                directional_np = self.render.attachNewNode(directional)
                self.render.setLight(directional_np)

                # terrain as neutral base plane
                from panda3d.core import CardMaker

                gm = CardMaker("terrain")
                w = self.outer.world.terrain.width_m()
                h = self.outer.world.terrain.height_m()
                gm.setFrame(0, w, 0, h)
                geom = self.render.attachNewNode(gm.generate())
                geom.setHpr(0, -90, 0)
                geom.setPos(0, 0, 0)
                geom.setColor(0.2, 0.4, 0.16, 1)

                self.model_units = {}
                from panda3d.core import GeoMipTerrain

                self._unit_nodes = {}
                for u in self.outer.world.units.values():
                    color = (1, 0.15, 0.15, 1) if u.side.value == "red" else (0.15, 0.2, 1, 1)
                    self._create_unit_model(u)

            def _create_unit_model(self, u):
                if u.kind.value == "artillery":
                    model = self.loader.loadModel("models/box")
                    base_scale = (400, 400, 80)
                else:
                    model = self.loader.loadModel("models/smiley")
                    base_scale = (180, 180, 180)
                model.setScale(*base_scale)
                model.setPythonTag("base_scale", base_scale)
                model.reparentTo(self.render)
                model.setPos(u.position.x, u.position.y, 60)
                color = (1, 0.2, 0.2, 1) if u.side.value == "red" else (0.2, 0.3, 1, 1)
                model.setColor(*color)
                self._unit_nodes[u.id] = model

            def _setup_camera(self):
                self.camera.setPos(4000, 4500, 2200)
                self.camera.lookAt(4000, 4000, 0)
                self._free_cam = True
                self._current_focus = None

            def _setup_hud(self):
                self.title = self.a2dTopLeft.attachNewNode(TextNode("hud"))
                self.title.node().setText("[F1] 자유시점/부대 시점 전환")
                self.title.setScale(0.06)
                self.title.setPos(0.02, 0, -0.06)

            def _toggle_view(self):
                self._free_cam = not self._free_cam
                if self._free_cam:
                    self.camera.setPos(4000, 4500, 2200)
                    self.camera.lookAt(4000, 4000, 0)
                else:
                    self._focus_unit(0)

            def _focus_unit(self, index: int):
                units = [u for u in self.outer.world.alive_units()]
                if not units:
                    return
                if index >= len(units):
                    return
                u = units[index]
                self._current_focus = u.id
                target_pos = self.outer.world.units[u.id].position
                self.camera.setPos(target_pos.x + 500, target_pos.y + 700, 500)
                self.camera.lookAt(target_pos.x, target_pos.y, 0)

            def _tick(self, task):
                dt = globalClock.getDt()
                self._time += dt
                self.outer.world.update(dt)
                self.outer.sync_units(self._unit_nodes)
                return Task.cont

            def _render_tick(self, task):
                # small per-frame polish
                self.outer.update_shell_visuals(self.render, self._unit_nodes)
                return Task.cont

        app = _App(self)
        app.run()

    def sync_units(self, node_map):
        for uid, node in node_map.items():
            unit = self.world.units.get(uid)
            if unit is None:
                node.removeNode()
                continue
            node.setPos(unit.position.x, unit.position.y, 80)
            # Encode remaining strength by scale without losing the model's
            # original visual footprint.
            base = node.getPythonTag("base_scale") or (180, 180, 180)
            factor = 0.45 + 0.55 * unit.normalized_strength
            node.setScale(base[0] * factor, base[1] * factor, base[2] * factor)

    def update_shell_visuals(self, render_node, node_map):
        return
