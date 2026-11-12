"""Optional user-configured chat-completions provider returning reviewed actions."""

import json
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from .automation import validate_actions

MAX_RESPONSE = 512 * 1024
ALLOWED = {"line", "circle", "rectangle", "move", "copy", "delete", "room"}
from .drafting_actions import OPS as BUILDING_OPS
ALLOWED |= BUILDING_OPS


def validate_endpoint(endpoint):
    value = urlsplit(endpoint)
    if (
        value.username
        or value.password
        or value.fragment
        or value.query
        or not value.netloc
    ):
        raise ValueError(
            "Use a complete API endpoint without credentials, query or fragment"
        )
    if value.scheme != "https" and not (
        value.scheme == "http" and value.hostname in ("localhost", "127.0.0.1", "::1")
    ):
        raise ValueError(
            "AI endpoint must use HTTPS, or localhost HTTP for a local model"
        )
    if not value.path.rstrip("/").endswith("/chat/completions"):
        raise ValueError("Use the full /v1/chat/completions endpoint")
    return endpoint


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError(
            "AI provider redirects are rejected; configure the final endpoint"
        )


def request_actions(endpoint, key, model, prompt, context):
    validate_endpoint(endpoint)
    if not isinstance(model, str) or not model.strip() or len(model) > 255:
        raise ValueError("Enter the provider model name")
    if len(prompt) > 20000:
        raise ValueError("Prompt exceeds 20,000 characters")
    schema = """Return ONLY a JSON object {"actions":[...]}. No code or commentary.
Allowed actions:
{"op":"line","start":[x,y],"end":[x,y]}
{"op":"circle","center":[x,y],"radius":positive}
{"op":"rectangle","start":[x,y],"end":[x,y]}
{"op":"move","ids":[existing selected IDs],"dx":number,"dy":number}
{"op":"copy","ids":[existing selected primitive IDs],"dx":number,"dy":number}
{"op":"delete","ids":[existing selected IDs]}
{"op":"room","start":[x,y],"width":positive,"depth":positive,"wall_width":positive,"name":"Room","number":"101","finish":"Paint"}
Coordinates use the drawing units in context. Maximum 1000 actions. Never invent target IDs.
"""
    from .drafting_actions import GUIDANCE
    schema += GUIDANCE
    data = {
        "model": model.strip(),
        "messages": [
            {"role": "system", "content": schema},
            {
                "role": "user",
                "content": json.dumps(
                    {"instruction": prompt, "context": context}, ensure_ascii=False
                ),
            },
        ],
        "temperature": 0,
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    request = Request(
        endpoint,
        data=json.dumps(data, allow_nan=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with build_opener(NoRedirect()).open(request, timeout=30) as response:
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise ValueError("AI response exceeds 512 KiB")
    try:
        result = json.loads(raw)
        content = result["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ValueError("Provider returned no text actions")
        if content.startswith("```"):
            lines = content.splitlines()
            content = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else content
        result = json.loads(content)
        if not isinstance(result, dict) or set(result) != {"actions"}:
            raise ValueError("Provider must return an actions object")
        actions = validate_actions(result["actions"])
        if any(a["op"] not in ALLOWED for a in actions):
            raise ValueError("Provider requested an unsupported action")
        return actions
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as ex:
        raise ValueError(
            "Provider response does not contain valid drawing actions"
        ) from ex


def provider_dialog(mw):
    from concurrent.futures import ThreadPoolExecutor
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QFormLayout,
        QLineEdit,
        QPlainTextEdit,
        QPushButton,
        QLabel,
        QMessageBox,
    )
    from . import appsettings
    from .automation import review_proposal
    from .native_io import entity_to_dict

    d = QDialog(mw)
    d.setWindowTitle("AI drawing proposals")
    d.resize(590, 470)
    root = QVBoxLayout(d)
    root.addWidget(
        QLabel(
            "Use your own compatible AI service or local model.\nGenerate sends the instruction, drawing units and selected 2D geometry to this endpoint.\nThe API key stays in this dialog. Review each proposal before applying."
        )
    )
    form = QFormLayout()
    root.addLayout(form)
    prefs = appsettings.get_settings()
    endpoint = QLineEdit(prefs.value("ai/endpoint", ""))
    endpoint.setPlaceholderText("https://your-provider/v1/chat/completions")
    model = QLineEdit(prefs.value("ai/model", ""))
    key = QLineEdit()
    key.setEchoMode(QLineEdit.EchoMode.Password)
    form.addRow("Endpoint", endpoint)
    form.addRow("Model", model)
    form.addRow("Session API key", key)
    prompt = QPlainTextEdit()
    prompt.setPlaceholderText("Describe the drawing changes…")
    root.addWidget(prompt)
    button = QPushButton("Generate and review")
    root.addWidget(button)
    status = QLabel()
    root.addWidget(status)
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pycad-ai")
    timer = QTimer(d)
    timer.setInterval(100)
    job = {"future": None}

    def generate():
        try:
            validate_endpoint(endpoint.text())
            selected = [
                entity_to_dict(e)
                for e in mw.canvas.selected_entities
                if e.kind != "INSERT"
            ]
            context = {"units": mw.document.units, "selected": selected}
            if len(json.dumps(context)) > 200000:
                raise ValueError("Selection is too large for the AI context")
            prefs.setValue("ai/endpoint", endpoint.text())
            prefs.setValue("ai/model", model.text())
            job["doc"] = mw.document
            job["future"] = pool.submit(
                request_actions,
                endpoint.text(),
                key.text(),
                model.text(),
                prompt.toPlainText(),
                context,
            )
            button.setEnabled(False)
            status.setText("Generating proposal…")
            timer.start()
        except ValueError as ex:
            QMessageBox.warning(d, "AI configuration", str(ex))

    def finish():
        future = job["future"]
        if not future or not future.done():
            return
        timer.stop()
        button.setEnabled(True)
        status.setText("")
        try:
            actions = future.result()
            if mw.document is not job["doc"]:
                raise ValueError("Active drawing changed; generate again")
            review_proposal(mw, actions, "Review AI proposal")
        except Exception as ex:
            # Exceptions may contain request details; show a short message without the key.
            message = str(ex).replace(key.text(), "[key]") if key.text() else str(ex)
            QMessageBox.warning(d, "AI proposal", message[:1000])

    button.clicked.connect(generate)
    timer.timeout.connect(finish)
    try:
        d.exec()
    finally:
        timer.stop()
        pool.shutdown(wait=False, cancel_futures=True)
        key.clear()
