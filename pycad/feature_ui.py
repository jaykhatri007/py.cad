"""Public commands and compact menus for the nine v16 feature areas."""

from . import (
    smart_blocks,
    geometry_ui,
    sheets,
    layers_plus,
    annotations_plus,
    architecture,
    solids,
    automation,
)

COMMANDS = [
    "ATTDEF",
    "ATTEDIT",
    "BLOCKSCHEDULE",
    "CURVEEDIT",
    "HATCHISLAND",
    "SHEETSET",
    "PUBLISH",
    "LAYERSTATE",
    "VPLAYER",
    "RICHTEXT",
    "LEADERLINK",
    "WALL",
    "DOOR",
    "WINDOW",
    "ROOM",
    "ARCHITECTURE",
    "ARCH3D",
    "SOLIDTOOLS",
    "UNION",
    "SUBTRACT",
    "INTERSECT",
    "REVOLVE",
    "SWEEP",
    "VIEWBASE",
    "VIEWPROJ",
    "VIEWSECTION",
    "ACTRECORD",
    "ACTMACRO",
    "APPLOAD",
    "ASSIST",
    "AIPROPOSE",
    "CLOSETAB",
    "CHECKDRAWING",
    "UPDATELINKS",
    "BUILDING", "LEVELS", "SLAB", "CEILING", "ROOF", "STAIR", "SLABHOLE",
    "AUTOROOM", "BUILD3D", "BUILDVIEW", "MATERIALS", "BOQ", "QUANTITYTAG",
    "IFCEXPORT", "DRAFTCHAT",
]


def commands(mw):
    from . import building_ui, boq_ui, materials_ui, drafting_chat
    result = {
        "BUILDING": lambda: building_ui.manager(mw),
        "LEVELS": lambda: building_ui.levels_dialog(mw),
        "SLAB": lambda: building_ui.create_dialog(mw, 'slab'),
        "CEILING": lambda: building_ui.create_dialog(mw, 'ceiling'),
        "ROOF": lambda: building_ui.create_dialog(mw, 'roof'),
        "STAIR": lambda: building_ui.create_dialog(mw, 'stair'),
        "SLABHOLE": lambda: building_ui.hole_from_selection(mw),
        "AUTOROOM": lambda: building_ui.rooms(mw),
        "BUILD3D": lambda: building_ui.build_all(mw),
        "BUILDVIEW": lambda: building_ui.view_dialog(mw),
        "MATERIALS": lambda: materials_ui.dialog(mw),
        "BOQ": lambda: boq_ui.dialog(mw),
        "QUANTITYTAG": lambda: boq_ui.tag_dialog(mw),
        "IFCEXPORT": lambda: building_ui.ifc(mw),
        "DRAFTCHAT": lambda: drafting_chat.show(mw),
        "CHECKDRAWING": lambda: __import__('pycad.drawing_checks', fromlist=['dialog']).dialog(mw),
        "UPDATELINKS": lambda: __import__('pycad.connected_models', fromlist=['refresh']).refresh(mw),
        "ATTDEF": lambda: smart_blocks.attribute_dialog(mw, True),
        "ATTEDIT": lambda: smart_blocks.attribute_dialog(mw),
        "BLOCKSCHEDULE": lambda: smart_blocks.schedule_dialog(mw),
        "CURVEEDIT": lambda: geometry_ui.edit_curve(mw),
        "HATCHISLAND": lambda: geometry_ui.hatch_with_islands(mw),
        "SHEETSET": lambda: sheets.sheets_dialog(mw),
        "PUBLISH": lambda: sheets.sheets_dialog(mw),
        "LAYERSTATE": lambda: layers_plus.state_dialog(mw),
        "VPLAYER": lambda: layers_plus.viewport_override_dialog(mw),
        "RICHTEXT": lambda: annotations_plus.edit_rich_text(mw),
        "LEADERLINK": lambda: annotations_plus.link_leader(mw),
        "ARCHITECTURE": lambda: architecture.architecture_dialog(mw),
        "ARCH3D": lambda: architecture.walls_to_3d(mw),
        "ACTRECORD": lambda: automation.toggle_recording(mw),
        "ACTMACRO": lambda: automation.macro_dialog(mw),
        "APPLOAD": lambda: automation.plugin_dialog(mw),
        "ASSIST": lambda: automation.assistant_dialog(mw),
        "AIPROPOSE": lambda: __import__(
            "pycad.ai_provider", fromlist=["provider_dialog"]
        ).provider_dialog(mw),
        "CLOSETAB": lambda: mw.drawing_tabs.close_drawing(mw.drawing_tabs.active),
    }
    for name in ("WALL", "DOOR", "WINDOW", "ROOM"):
        result[name] = lambda n=name: architecture.create_from_selection(mw, n.lower())
    for name in (
        "SOLIDTOOLS",
        "UNION",
        "SUBTRACT",
        "INTERSECT",
        "VIEWBASE",
        "VIEWPROJ",
        "VIEWSECTION",
    ):
        result[name] = lambda: solids.solid_dialog(mw)
    for name in ("REVOLVE", "SWEEP"):
        result[name] = lambda n=name: solids.profile_operation(mw, n.lower())
    result.update(getattr(mw, "plugin_commands", {}))
    return result


def install(mw):
    groups = [
        ('Building', [('Building tools', 'BUILDING'), ('Levels / Storeys', 'LEVELS'),
                      ('Slab', 'SLAB'), ('Ceiling', 'CEILING'), ('Roof', 'ROOF'),
                      ('Stair / Railing', 'STAIR'), ('Slab / Ceiling opening', 'SLABHOLE'),
                      ('Detect linked rooms', 'AUTOROOM'), ('Build live models', 'BUILD3D'),
                      ('Building sections / Elevations', 'BUILDVIEW'), ('Materials / Appearance', 'MATERIALS'),
                      ('Bill of quantities', 'BOQ'), ('Tag quantity geometry', 'QUANTITYTAG'), ('Export IFC4', 'IFCEXPORT')]),
        (
            "Architecture",
            [
                ("Walls", "WALL"),
                ("Door", "DOOR"),
                ("Window", "WINDOW"),
                ("Room / Area label", "ROOM"),
                ("Object parameters / Finish schedule", "ARCHITECTURE"),
                ("Generate / Link 3D walls", "ARCH3D"),
                ("Refresh linked models / views", "UPDATELINKS"),
                ("Drawing checks", "CHECKDRAWING"),
            ],
        ),
        (
            "Advanced",
            [
                ("Block attributes", "ATTEDIT"),
                ("Attribute definitions", "ATTDEF"),
                ("Block schedule", "BLOCKSCHEDULE"),
                ("Curve controls", "CURVEEDIT"),
                ("Hatch islands", "HATCHISLAND"),
                ("Rich text", "RICHTEXT"),
                ("Link leader tip", "LEADERLINK"),
                ("Layer states", "LAYERSTATE"),
                ("Viewport layer overrides", "VPLAYER"),
                ("Sheet set / Publish PDF", "SHEETSET"),
                ("Solid operations / Sections / Elevations", "SOLIDTOOLS"),
                ("Revolve profile", "REVOLVE"),
                ("Sweep along path", "SWEEP"),
            ],
        ),
        (
            "Automation",
            [
                ("Start / Stop recording", "ACTRECORD"),
                ("Review / Replay macros", "ACTMACRO"),
                ("Load Python plugin", "APPLOAD"),
                ("Drawing assistant (offline)", "ASSIST"),
                ("AI provider proposals", "AIPROPOSE"),
                ("Drafting chat", "DRAFTCHAT"),
            ],
        ),
    ]
    tools_menu = next(
        action.menu()
        for action in mw.menuBar().actions()
        if action.menu() and action.text().replace("&", "") == "Tools"
    )
    for label, items in groups:
        menu = tools_menu.addMenu(label)
        for title, command in items:
            mw._add_action(menu, title, lambda _, c=command: mw.run_ribbon_command(c))
    mw.canonical_commands.update(COMMANDS)
    mw.command_names = sorted(mw.canonical_commands | set(mw.user_aliases))
