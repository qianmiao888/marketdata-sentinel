"""Pure query binding used by the business UI and regression checks."""

import json

from sentinel.service import Context


def scope_key(params, question, mode="deterministic", baseline="A"):
    context = Context.model_validate(params).model_dump(mode="json")
    return json.dumps([context, question, mode, baseline], sort_keys=True, ensure_ascii=False)


def current_bundle(state, key):
    return state.get("bundle") if state.get("scope_key") == key else None
