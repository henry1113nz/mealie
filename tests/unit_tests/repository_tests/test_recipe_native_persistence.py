"""Regression coverage for native recipe writes and transaction boundaries."""

import pytest

from mealie.schema.recipe.recipe import Recipe
from mealie.schema.recipe.recipe_ingredient import RecipeIngredient
from mealie.schema.recipe.recipe_notes import RecipeNote
from mealie.schema.recipe.recipe_step import NoteReference, RecipeStep
from tests.utils.factories import random_string
from tests.utils.fixture_schemas import TestUser


def test_recipe_nested_failure_rolls_back_recipe_and_organizers(unique_user: TestUser) -> None:
    repositories = unique_user.repos
    recipe = repositories.recipes.create(
        Recipe(
            name=random_string(),
            user_id=unique_user.user_id,
            group_id=unique_user.group_id,
            recipe_ingredient=[RecipeIngredient(note="Original ingredient")],
            recipe_instructions=[RecipeStep(text="Original step")],
            notes=[RecipeNote(title="Original note", text="Keep this note")],
            extras={"original": "value"},
        )
    )
    data = recipe.model_dump()
    new_name = random_string()
    new_tag = random_string()
    data.update(
        name=new_name,
        tags=[{"name": new_tag}],
        recipe_instructions=[{"text": "Changed step"}],
        recipe_ingredient=[{"food": {"name": "Missing persisted food identifier"}}],
        notes=[],
        extras={},
    )
    with pytest.raises(ValueError, match="Expected 'id' to be provided for food"):
        repositories.recipes.update(recipe.slug, data)

    restored = repositories.recipes.get_one(recipe.slug)
    assert restored.model_dump() == recipe.model_dump()
    assert repositories.recipes.get_one(new_name, "name") is None
    assert repositories.tags.get_one(new_tag, "name") is None


def test_recipe_replacement_never_reparents_foreign_steps(unique_user: TestUser) -> None:
    repositories = unique_user.repos
    original = repositories.recipes.create(
        Recipe(
            name=random_string(),
            user_id=unique_user.user_id,
            group_id=unique_user.group_id,
            notes=[RecipeNote(title="Source note", text="Keep source text")],
            recipe_instructions=[RecipeStep(text="Keep source step")],
        )
    )
    source_step = original.recipe_instructions[0]
    source_note = original.notes[0]
    target = repositories.recipes.create(
        Recipe(name=random_string(), user_id=unique_user.user_id, group_id=unique_user.group_id)
    )
    payload = target.model_dump()
    payload["recipe_instructions"] = [
        source_step.model_copy(
            update={
                "text": "Independent target step",
                "note_references": [NoteReference(reference_id=source_note.reference_id)],
            }
        ).model_dump()
    ]
    updated = repositories.recipes.update(target.slug, payload)

    assert updated.recipe_instructions[0].id != source_step.id
    assert updated.recipe_instructions[0].text == "Independent target step"
    assert updated.recipe_instructions[0].note_references[0].reference_id == source_note.reference_id
    assert repositories.recipes.get_one(original.slug).model_dump() == original.model_dump()


def test_recipe_random_search_keeps_exact_name_priority(unique_user: TestUser) -> None:
    from mealie.schema.response.pagination import PaginationQuery

    repositories = unique_user.repos
    term = random_string()
    exact = repositories.recipes.create(Recipe(name=term, user_id=unique_user.user_id, group_id=unique_user.group_id))
    for _ in range(5):
        repositories.recipes.create(
            Recipe(
                name=random_string(),
                user_id=unique_user.user_id,
                group_id=unique_user.group_id,
                recipe_ingredient=[RecipeIngredient(note=term)],
            )
        )
    page = repositories.recipes.page_all(
        PaginationQuery(per_page=-1, order_by="random", pagination_seed="keep-search-priority"), search=term
    )

    assert page.total == 6
    assert page.items[0].id == exact.id
    assert [item.id for item in page.items] == [
        item.id
        for item in repositories.recipes.page_all(
            PaginationQuery(per_page=-1, order_by="random", pagination_seed="keep-search-priority"), search=term
        ).items
    ]


def test_food_explicit_label_id_survives_nullable_relationship_payload(unique_user: TestUser) -> None:
    repositories = unique_user.repos
    label = repositories.group_multi_purpose_labels.create({"name": random_string(), "group_id": unique_user.group_id})
    food = repositories.ingredient_foods.create(
        {"name": random_string(), "group_id": unique_user.group_id, "label_id": label.id, "label": None}
    )
    assert food.label_id == label.id
    assert food.label.id == label.id
    updated = repositories.ingredient_foods.update(food.id, food.model_dump() | {"label": None})
    assert updated.label_id == label.id
    assert updated.label.id == label.id


def test_timeline_partial_update_refreshes_default_timestamp(unique_user: TestUser) -> None:
    from datetime import UTC, datetime

    repositories = unique_user.repos
    recipe = repositories.recipes.create(
        Recipe(name=random_string(), user_id=unique_user.user_id, group_id=unique_user.group_id)
    )
    event = repositories.recipe_timeline_events.create(
        {
            "recipe_id": recipe.id,
            "user_id": unique_user.user_id,
            "subject": "Original",
            "event_type": "info",
            "timestamp": datetime(2000, 1, 1, tzinfo=UTC),
        }
    )
    before = datetime.now(UTC)
    updated = repositories.recipe_timeline_events.update(event.id, {"subject": "Updated"})
    assert updated.timestamp >= before
    assert updated.subject == "Updated"
    explicit = repositories.recipe_timeline_events.update(event.id, {"timestamp": event.timestamp})
    assert explicit.timestamp == datetime(2000, 1, 1, tzinfo=UTC)


def test_food_sparse_update_and_patch_preserve_legacy_collection_defaults(unique_user: TestUser) -> None:
    repositories = unique_user.repos
    household_slug = repositories.households.get_one(unique_user.household_id).slug
    food = repositories.ingredient_foods.create(
        {
            "name": random_string(),
            "group_id": unique_user.group_id,
            "extras": {"key": "value"},
            "substitutions": [{"note": "Alternative"}],
            "households_with_ingredient_food": [household_slug],
        }
    )
    patched = repositories.ingredient_foods.patch(food.id, {"description": "Patched"})
    assert patched.extras == {"key": "value"}
    assert [row.note for row in patched.substitutions] == ["Alternative"]
    assert patched.households_with_ingredient_food == [household_slug]
    updated = repositories.ingredient_foods.update(
        food.id, {"name": food.name, "group_id": unique_user.group_id, "description": "Updated"}
    )
    assert updated.extras == {}
    assert updated.substitutions == []
    assert updated.households_with_ingredient_food == []
