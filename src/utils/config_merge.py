from typing import TypeVar

from pydantic import BaseModel


ModelT = TypeVar("ModelT", bound=BaseModel)


def merge_partial_model(current: ModelT, patch: BaseModel | None) -> ModelT:
    """
    Merge fields explicitly provided in a partial Pydantic model into `current`.
    """

    if patch is None:
        return current

    updates = patch.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        return current

    merged = current.model_dump()
    merged.update(updates)
    return type(current).model_validate(merged)