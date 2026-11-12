"""
layers.py
Simple layer manager: name -> {color, visible, locked}.
"""
from typing import Dict


LINEWEIGHTS = (0, .05, .09, .13, .15, .18, .2, .25, .3, .35, .4, .5, .53, .6, .7, .8, .9, 1, 1.06, 1.2, 1.4, 1.58, 2, 2.11)

LAYER_DEFAULTS = {"color": "#FFFFFF", "visible": True, "locked": False,
                  "frozen": False, "linetype": "CONTINUOUS", "lineweight": 0.25, "plot": True}


class LayerManager:
    def __init__(self):
        self.layers: Dict[str, dict] = {
            "0": dict(LAYER_DEFAULTS)
        }
        self.current_layer = "0"

    def add_layer(self, name: str, color: str = "#FFFFFF"):
        if name not in self.layers:
            self.layers[name] = {**LAYER_DEFAULTS, "color": color}

    def remove_layer(self, name: str):
        if name != "0" and name in self.layers:
            del self.layers[name]
            if self.current_layer == name:
                self.current_layer = "0"

    def set_current(self, name: str):
        if name in self.layers:
            self.current_layer = name

    def set_visible(self, name: str, visible: bool):
        if name in self.layers:
            self.layers[name]["visible"] = visible

    def set_locked(self, name: str, locked: bool):
        if name in self.layers:
            self.layers[name]["locked"] = locked

    def set_color(self, name: str, color: str):
        if name in self.layers:
            self.layers[name]["color"] = color

    def is_visible(self, name: str) -> bool:
        props = self.layers.get(name, {})
        return props.get("visible", True) and not props.get("frozen", False)

    def is_locked(self, name: str) -> bool:
        return self.layers.get(name, {}).get("locked", False)

    def names(self):
        return list(self.layers.keys())
