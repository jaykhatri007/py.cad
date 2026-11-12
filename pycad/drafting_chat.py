"""Compact drafting chat: offline commands and optional structured AI proposals."""

import copy
import json
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, build_opener
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDockWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QComboBox,
    QLabel,
    QDialog,
    QFormLayout,
    QLineEdit,
)
from .units import UNIT_MM
from .automation import validate_actions, parse_instruction, review_proposal
from .ai_provider import validate_endpoint, NoRedirect, MAX_RESPONSE, ALLOWED
from .drafting_actions import GUIDANCE

N = r"([-+]?\d+(?:\.\d+)?)"


def normalise_units(text, doc):
    unit = r"(mm|cm|m|in|ft)"
    dimension = re.compile(
        N + r"\s*" + unit + r"?\s*(?:x|×|by)\s*" + N + r"\s*" + unit + r"?\b", re.I
    )

    def pair(match):
        a, ua, b, ub = match.groups()
        if ua or ub:
            if doc.units not in UNIT_MM:
                raise ValueError(
                    "Assign drawing units before using physical dimensions"
                )
            ua, ub = (ua or ub).lower(), (ub or ua).lower()
            a = float(a) * UNIT_MM[ua] / UNIT_MM[doc.units]
            b = float(b) * UNIT_MM[ub] / UNIT_MM[doc.units]
        return f"{a}x{b}"

    text = dimension.sub(pair, text)

    def length(match):
        if doc.units not in UNIT_MM:
            raise ValueError("Assign drawing units before using physical dimensions")
        return str(float(match[1]) * UNIT_MM[match[2].lower()] / UNIT_MM[doc.units])

    return re.sub(N + r"\s*" + unit + r"\b", length, text, flags=re.I)


def offline(doc, text, selected=()):
    from . import building, boq, object_properties

    if text.strip().lower() in ('explain selected','explain quantities','explain drawing'):
        from .productivity import explain
        entities=[doc.find_by_id(key) for key in selected]
        return dict(message=json.dumps(explain(doc,[e for e in entities if e is not None],question=text),indent=2,ensure_ascii=False),actions=[])
    text = normalise_units(text.strip(), doc)
    if text.lower().startswith('plan rooms '):
        if doc.units!='mm':raise ValueError('Room planner currently requires millimetre units')
        from .room_planner import plan
        rooms=[]
        for part in text[11:].split(';'):
            match=re.fullmatch(r'(.+?)\s+([-+0-9.eE]+)\s*[x×]\s*([-+0-9.eE]+)',part.strip())
            if not match:raise ValueError('Provide named sizes: plan rooms Office 6000x4000; Store 3000x3000. Use ROOMPLANNER for more questions.')
            rooms.append(dict(name=match[1],width=float(match[2]),depth=float(match[3])))
        return dict(message='Review separated room modules, hosted doors, labels and linked dimensions. Default separation 500 mm; ROOMPLANNER lets you change assumptions.',actions=plan(rooms))
    array=re.fullmatch(r'array selected (\d+)\s*(?:by|x|×)\s*(\d+)\s*spacing ([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)',text,re.I)
    if array:
        rows,cols=int(array[1]),int(array[2]);dx,dy=float(array[3]),float(array[4])
        if rows<1 or cols<1 or rows*cols<2 or rows*cols>1000:raise ValueError('Use an array with 2–1000 placements per proposal')
        if not selected:raise ValueError('Select primitive objects to array')
        actions=[dict(op='copy',ids=list(selected),dx=c*dx,dy=r*dy) for r in range(rows) for c in range(cols) if r or c]
        return dict(message='Review rectangular copy array',actions=validate_actions(actions))
    text = re.sub(r"^please\s+", "", text, flags=re.I)
    text = re.sub(r"^(draw|create|add)\s+(?:a|an)\s+", r"\1 ", text, flags=re.I)
    if text.startswith("{"):
        value = json.loads(text)
        return {
            "message": "Structured drawing proposal",
            "actions": validate_actions(value["actions"]),
        }
    if ";" in text or "\n" in text:
        actions = []
        for part in re.split(r";|\n", text):
            if part.strip():
                response = offline(doc, part, selected)
                if not response["actions"]:
                    raise ValueError(
                        "Send quantity questions separately after applying the drawing changes"
                    )
                # Separate instructions can each generate @wall1. Preserve each
                # instruction's internal references while combining proposals.
                remap = {
                    a["ref"]: "@part" + str(len(actions)) + "_" + a["ref"][1:]
                    for a in response["actions"]
                    if "ref" in a
                }
                for action in response["actions"]:
                    for field in ("ref", "wall"):
                        if field in action:
                            action[field] = remap.get(action[field], action[field])
                    if "ids" in action:
                        action["ids"] = [remap.get(k, k) for k in action["ids"]]
                actions += response["actions"]
        return dict(
            message="Combined drawing proposal", actions=validate_actions(actions)
        )
    if re.fullmatch(
        r"(?:show|generate|give|calculate)?\s*(?:the\s+)?(?:boq|bill of quantities|quantities|cost estimate)",
        text,
        re.I,
    ):
        result = boq.report(doc)
        lines = [
            f"{len(result['items'])} measured items · Priced subtotal {result['currency']} {result['priced_total']:,.2f}",
            f"{result['unpriced_items']} items need rates; {len(result['unmeasured_ids'])} objects need measurement tags.",
        ]
        lines += [
            f"{r['description']} / {r['material']}: {r['quantity']:.3f} {r['unit']}"
            for r in result["summary"][:30]
        ]
        lines += result["warnings"]
        return dict(message="\n".join(lines), actions=[])
    if re.fullmatch(r"(?:help|what can you do|examples)", text, re.I):
        return dict(
            message="Try: room 6m x 4m at 0,0; wall from 0,0 to 6000,0 width 200 height 3000; slab from selection thickness 150; roof from selection type Gable slope 25; stairs 18 steps height 3000 layout L; set selected height to 3600; detect rooms; build 3d; apply Timber to selection; show BOQ. Separate drawing commands with semicolons. AI provider mode accepts broader instructions using your configured service.",
            actions=[],
        )
    mm = 1 / UNIT_MM.get(doc.units, 1)
    match = re.fullmatch(
        r"(?:draw |create |add )?wall from\s+"
        + N
        + r"\s*,\s*"
        + N
        + r"\s+to\s+"
        + N
        + r"\s*,\s*"
        + N
        + r"(?:\s+width\s+"
        + N
        + r")?(?:\s+height\s+"
        + N
        + r")?",
        text,
        re.I,
    )
    if match:
        x, y, xx, yy, w, h = match.groups()
        return dict(
            message="Wall proposal",
            actions=[
                dict(
                    op="wall",
                    ref="@wall1",
                    start=[float(x), float(y)],
                    end=[float(xx), float(yy)],
                    width=float(w or 200 * mm),
                    height=float(
                        h or building.levels(doc)[building.current_level(doc)]["height"]
                    ),
                    material="Brick",
                )
            ],
        )
    match = re.fullmatch(
        r"(?:set|change)\s+(?:the\s+)?(?:selected|selection)(?:\s+(?:wall|object))?\s+(height|width|thickness|material|finish|name|steps|slope|overhang)\s+(?:to\s+)?(.+)",
        text,
        re.I,
    )
    if match:
        field, value = match.groups()
        field = field.lower()
        actions = []
        if not selected:
            raise ValueError("Select objects before asking for a property edit")
        for key in selected:
            entity = doc.find_by_id(key)
            if entity is None:
                raise ValueError("Selection no longer exists")
            fields = object_properties.values_for(doc, entity)
            prop = next(
                (
                    k
                    for k in ("Building." + field, "Architecture." + field, field)
                    if k in fields
                ),
                None,
            )
            if prop is None:
                raise ValueError("Selected object has no editable " + field)
            if type(fields[prop]) in (int, float):
                value = float(value)
            actions.append(dict(op="properties", ids=[key], values={prop: value}))
        return dict(
            message="Selected object edit proposal", actions=validate_actions(actions)
        )
    match = re.fullmatch(
        r"(?:create |add )?level\s+(.+?)\s+(?:at|elevation)\s+"
        + N
        + r"(?:\s+height\s+"
        + N
        + r")?",
        text,
        re.I,
    )
    if match:
        name, z, h = match.groups()
        return dict(
            message="Level proposal",
            actions=[
                dict(
                    op="level",
                    name=name,
                    elevation=float(z),
                    height=float(h or 3000 * mm),
                )
            ],
        )
    match = re.fullmatch(
        r"(?:assign|move)\s+(?:selected|selection)\s+to\s+level\s+(.+)", text, re.I
    )
    if match:
        return dict(
            message="Level assignment proposal",
            actions=validate_actions(
                [dict(op="assign_level", ids=list(selected), level=match[1])]
            ),
        )
    if re.fullmatch(r"(?:detect|find|create)\s+(?:automatic\s+)?rooms", text, re.I):
        return dict(
            message="Automatic room proposal",
            actions=[dict(op="auto_rooms", level=building.current_level(doc))],
        )
    if re.fullmatch(
        r"(?:build|generate|update)\s+(?:live\s+)?3d(?:\s+models)?", text, re.I
    ):
        return dict(
            message="Live building model proposal", actions=[dict(op="build3d")]
        )
    match = re.fullmatch(
        r"(?:apply|assign)\s+(.+?)\s+to\s+(?:selected|selection)", text, re.I
    )
    if match:
        return dict(
            message="Material proposal",
            actions=validate_actions(
                [dict(op="material", ids=list(selected), name=match[1])]
            ),
        )
    match = re.fullmatch(
        r"(?:create |add )?(slab|ceiling|roof)\s+from\s+(?:selected|selection)(.*)",
        text,
        re.I,
    )
    if match:
        from .geometry import PolylineEntity

        if len(selected) != 1:
            raise ValueError("Select one closed boundary")
        entity = doc.find_by_id(selected[0])
        if (
            not isinstance(entity, PolylineEntity)
            or not entity.closed
            or any(entity.bulges)
        ):
            raise ValueError("Select one closed straight-edge boundary")
        kind, options = match.groups()
        kind = kind.lower()
        params = {}
        for name in ("thickness", "elevation", "slope", "overhang"):
            found = re.search(r"\b" + name + r"\s+" + N, options, re.I)
            if found:
                params[name] = float(found[1])
        found = re.search(r"\btype\s+(Flat|Shed|Gable|Hip)\b", options, re.I)
        if found:
            params["roof_type"] = found[1].title()
        return dict(
            message=kind.title() + " proposal",
            actions=[
                dict(
                    op="building",
                    ref="@" + kind,
                    kind=kind,
                    boundary=[[p.x, p.y] for p in entity.points],
                    parameters=params,
                )
            ],
        )
    match = re.fullmatch(
        r"(?:create |add )?stairs?\s+" + N + r"\s+steps(.*)", text, re.I
    )
    if match:
        count, options = match.groups()
        if not float(count).is_integer():
            raise ValueError("Step count must be an integer")
        params = {"steps": int(float(count))}
        for name in ("width", "tread", "height", "landing", "rail_height"):
            found = re.search(r"\b" + name + r"\s+" + N, options, re.I)
            if found:
                params[name] = float(found[1])
        found = re.search(r"\blayout\s+(Straight|L|U)\b", options, re.I)
        if found:
            params["layout"] = (
                "Straight" if found[1].lower() == "straight" else found[1].upper()
            )
        found = re.search(r"\bat\s+" + N + r"\s*,\s*" + N, options, re.I)
        if found:
            params["position"] = [float(found[1]), float(found[2])]
        return dict(
            message="Stair proposal",
            actions=[
                dict(
                    op="building",
                    ref="@stair",
                    kind="stair",
                    boundary=[],
                    parameters=params,
                )
            ],
        )
    return dict(message="Drawing proposal", actions=parse_instruction(text, selected))


def context_for(doc, selected, history=()):
    from .native_io import entity_to_dict
    from .building import levels, current_level
    from .object_properties import values_for

    context = dict(
        units=doc.units,
        levels=levels(doc),
        current_level=current_level(doc),
        selected=[],
        history=list(history)[-10:],
    )
    editable = {e.id for e in doc.editable_entities()}
    typed = set(doc.extensions.get("architecture", {})) | set(
        doc.extensions.get("building_elements", {})
    )
    candidates = sorted(doc.entities, key=lambda e: e.id not in typed)[:250]
    context["objects"] = [
        dict(
            id=e.id,
            kind=e.kind,
            level=__import__("pycad.building", fromlist=["level_for"]).level_for(
                doc, e.id
            ),
            bounds=e.bbox(),
            editable=e.id in editable,
            properties=values_for(doc, e),
        )
        for e in candidates
    ]
    context["omitted_object_count"] = max(0, len(doc.entities) - len(candidates))
    context["material_names"] = sorted(
        set(__import__("pycad.materials", fromlist=["DEFAULTS"]).DEFAULTS)
        | set(doc.extensions.get("materials", {}))
    )
    if doc.units in UNIT_MM:
        from .boq import report

        quantities = report(doc)
        context["quantities"] = {
            k: quantities[k]
            for k in ("currency", "priced_total", "unpriced_items", "warnings")
        }
        context["quantities"]["summary"] = quantities["summary"][:100]
    for key in list(selected)[:100]:
        entity = doc.find_by_id(key)
        if entity:
            context["selected"].append(
                dict(
                    id=key,
                    geometry=entity_to_dict(entity),
                    properties=values_for(doc, entity),
                )
            )
    from .productivity import explain
    entities=[doc.find_by_id(key) for key in list(selected)[:100]]
    context['selected_explanations']=explain(doc,[e for e in entities if e is not None])
    if len(json.dumps(context)) > 200000:
        raise ValueError("Selection is too large for AI context")
    return context


def request_chat(endpoint, key, model, prompt, context):
    validate_endpoint(endpoint)
    if not isinstance(model, str) or not model.strip() or len(model) > 255:
        raise ValueError("Enter a model name")
    if not isinstance(prompt, str) or not 1 <= len(prompt) <= 20000:
        raise ValueError("Instruction must contain 1–20,000 characters")
    basic = """Return only JSON {"message":"short answer or explanation", "actions":[]}.
Use an empty actions array for answers or clarification. For drafting, supported primitive actions are:
{"op":"line","start":[x,y],"end":[x,y]}
{"op":"rectangle","start":[x,y],"end":[x,y]}
{"op":"circle","center":[x,y],"radius":positive}
{"op":"move","ids":["existing selected ID"],"dx":number,"dy":number}
{"op":"delete","ids":["existing selected ID"]}
{"op":"room","start":[x,y],"width":positive,"depth":positive,"wall_width":positive,"name":"Room","number":"101","finish":"Paint"}
Use selected_explanations for drawing and quantity questions; state missing data and return no actions for explanation-only requests. Never claim independent verification. Maximum 1000 actions. Ask for missing dimensions instead of inventing them. No Python, shell, file paths or code. """
    body = dict(
        model=model.strip(),
        messages=[
            {"role": "system", "content": basic + GUIDANCE},
            {
                "role": "user",
                "content": json.dumps(
                    {"instruction": prompt, "context": context}, ensure_ascii=False
                ),
            },
        ],
        temperature=0,
    )
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    req = Request(
        endpoint,
        data=json.dumps(body, allow_nan=False).encode(),
        headers=headers,
        method="POST",
    )
    with build_opener(NoRedirect()).open(req, timeout=30) as response:
        raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError("AI response exceeds 512 KiB")
    try:
        content = json.loads(raw)["choices"][0]["message"]["content"].strip()
        if content.startswith("```") and content.endswith("```"):
            content = "\n".join(content.splitlines()[1:-1])
        value = json.loads(content)
        if (
            not isinstance(value, dict)
            or set(value) != {"message", "actions"}
            or not isinstance(value["message"], str)
            or len(value["message"]) > 10000
            or not isinstance(value["actions"], list)
        ):
            raise ValueError("AI must return a message and actions array")
        if value["actions"]:
            validate_actions(value["actions"])
            if any(a["op"] not in ALLOWED for a in value["actions"]):
                raise ValueError("AI requested an unsupported operation")
        return value
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as ex:
        raise ValueError("AI returned an invalid structured response") from ex


class DraftingChat(QDockWidget):
    def __init__(self, mw):
        super().__init__("Drafting chat", mw)
        self.setObjectName("drafting_chat_dock")
        self.mw = mw
        self.setMinimumWidth(280)
        self.setMaximumWidth(420)
        body = QWidget()
        self.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(8, 8, 8, 8)
        row = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItems(["Offline commands", "AI provider"])
        row.addWidget(self.mode, 1)
        configure = QPushButton("Settings")
        configure.clicked.connect(self.configure)
        row.addWidget(configure)
        layout.addLayout(row)
        self.history = QPlainTextEdit()
        self.history.setReadOnly(True)
        self.history.setMaximumBlockCount(1000)
        layout.addWidget(self.history, 1)
        self.prompt = QPlainTextEdit()
        self.prompt.setMaximumHeight(80)
        self.prompt.setPlaceholderText("Describe a drawing edit or ask for BOQ…")
        layout.addWidget(self.prompt)
        row = QHBoxLayout()
        self.send_button = QPushButton("Send")
        self.review_button = QPushButton("Preview / Apply")
        self.review_button.setEnabled(False)
        self.send_button.clicked.connect(self.send)
        self.review_button.clicked.connect(self.review)
        row.addWidget(self.send_button)
        row.addWidget(self.review_button)
        layout.addLayout(row)
        self.status = QLabel("Changes are previewed; Apply creates one Undo step.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        from .appsettings import get_settings

        prefs = get_settings()
        self.endpoint = prefs.value(
            "ai/endpoint", "http://localhost:11434/v1/chat/completions"
        )
        self.model = prefs.value("ai/model", "")
        self.api_key = ""
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pycad-chat")
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.finish)
        self.job = None
        self.pending = None
        self.sessions = {}
        self.document = None
        self.destroyed.connect(
            lambda: self.pool.shutdown(wait=False, cancel_futures=True)
        )
        self.refresh_session()

    def refresh_session(self):
        if self.document is self.mw.document:
            return
        self.document = self.mw.document
        self.pending = None
        self.review_button.setEnabled(False)
        session = self.sessions.setdefault(self.document, [])
        self.history.clear()
        if not session:
            self.history.appendPlainText(
                "Assistant: Describe a draft, edit selected objects, or type “show BOQ”. Type “help” for offline examples. AI provider mode uses your configured service."
            )
        for role, text in session:
            self.history.appendPlainText(role + ": " + text)

    def append(self, role, text):
        session = self.sessions.setdefault(self.document, [])
        session.append((role, text))
        del session[:-100]
        self.history.appendPlainText(role + ": " + text)

    def configure(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Drafting AI service")
        layout = QVBoxLayout(dialog)
        hint = QLabel(
            "AI mode sends your instruction, recent chat, object/quantity summaries and selected geometry to this endpoint. The API key is kept for this app session."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        form = QFormLayout()
        endpoint = QLineEdit(self.endpoint)
        model = QLineEdit(self.model)
        key = QLineEdit(self.api_key)
        key.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Compatible endpoint", endpoint)
        form.addRow("Model", model)
        form.addRow("Session API key", key)
        layout.addLayout(form)
        save = QPushButton("Save settings")

        def commit():
            try:
                validate_endpoint(endpoint.text())
                if not model.text().strip():
                    raise ValueError("Enter a model name")
                self.endpoint, self.model, self.api_key = (
                    endpoint.text(),
                    model.text(),
                    key.text(),
                )
                from .appsettings import get_settings

                prefs = get_settings()
                prefs.setValue("ai/endpoint", self.endpoint)
                prefs.setValue("ai/model", self.model)
                dialog.accept()
            except ValueError as ex:
                hint.setText(str(ex))

        save.clicked.connect(commit)
        layout.addWidget(save)
        dialog.exec()
        key.clear()

    def send(self):
        self.refresh_session()
        text = self.prompt.toPlainText().strip()
        if not text or self.job:
            return
        self.append("You", text)
        self.prompt.clear()
        self.pending = None
        self.review_button.setEnabled(False)
        doc = self.document
        selected = [e.id for e in self.mw.canvas.selected_entities]
        from .native_io import document_to_dict

        fingerprint = document_to_dict(doc)
        try:
            if text.lower() in ("undo", "redo"):
                getattr(doc.undo_stack, text.lower())()
                self.mw.refresh_document_ui()
                self.append("Assistant", text.title() + " completed.")
            elif self.mode.currentIndex() == 0:
                self.accept_response(offline(doc, text, selected), doc, fingerprint)
            else:
                validate_endpoint(self.endpoint)
                history = [
                    {"role": role, "text": message[:2000]}
                    for role, message in self.sessions[doc][-10:]
                ]
                context = context_for(doc, selected, history)
                self.job = dict(
                    doc=doc,
                    fingerprint=fingerprint,
                    future=self.pool.submit(
                        request_chat,
                        self.endpoint,
                        self.api_key,
                        self.model,
                        text,
                        context,
                    ),
                )
                self.send_button.setEnabled(False)
                self.status.setText("Generating a proposal…")
                self.timer.start()
        except Exception as ex:
            self.append("Assistant", str(ex)[:1500])

    def accept_response(self, response, doc, fingerprint):
        from .native_io import document_to_dict
        from .automation import prepare_proposal

        if self.mw.document is not doc or document_to_dict(doc) != fingerprint:
            raise ValueError(
                "Drawing changed while generating; send the instruction again"
            )
        actions = response["actions"]
        if actions:
            prepare_proposal(doc, actions)
            self.pending = dict(
                doc=doc, fingerprint=fingerprint, actions=copy.deepcopy(actions)
            )
            self.review_button.setEnabled(True)
        self.append(
            "Assistant",
            response["message"]
            + (
                f"\n{len(actions)} actions ready. Use Preview / Apply."
                if actions
                else ""
            ),
        )
        self.status.setText("Changes are previewed; Apply creates one Undo step.")

    def finish(self):
        if not self.job or not self.job["future"].done():
            return
        self.timer.stop()
        job = self.job
        self.job = None
        self.send_button.setEnabled(True)
        try:
            self.accept_response(job["future"].result(), job["doc"], job["fingerprint"])
        except Exception as ex:
            self.refresh_session()
            message = (
                str(ex).replace(self.api_key, "[key]") if self.api_key else str(ex)
            )
            self.append("Assistant", message[:1500])
            self.status.setText("No drawing changes applied.")

    def review(self):
        from .native_io import document_to_dict

        proposal = self.pending
        if not proposal:
            return
        try:
            if (
                self.mw.document is not proposal["doc"]
                or document_to_dict(self.mw.document) != proposal["fingerprint"]
            ):
                raise ValueError("Drawing changed; send the instruction again")
            if review_proposal(
                self.mw, proposal["actions"], "Review drafting chat changes"
            ):
                self.append(
                    "Assistant",
                    "Applied. Type “undo” to restore, or “show BOQ” to recalculate quantities.",
                )
                self.pending = None
                self.review_button.setEnabled(False)
        except Exception as ex:
            self.append("Assistant", str(ex)[:1500])
            self.pending = None
            self.review_button.setEnabled(False)


def show(mw):
    if not hasattr(mw, "drafting_chat"):
        mw.drafting_chat = DraftingChat(mw)
        mw.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, mw.drafting_chat)
        mw.tabifyDockWidget(mw.properties_panel, mw.drafting_chat)
        mw.resizeDocks([mw.drafting_chat], [330], Qt.Orientation.Horizontal)
    mw.drafting_chat.refresh_session()
    mw.drafting_chat.show()
    mw.drafting_chat.raise_()
    mw.drafting_chat.prompt.setFocus()
