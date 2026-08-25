# app/infrastructure/checklists/yaml_checklist_repository.py

from pathlib import Path

import yaml

from app.domain.checklists import (
    ChecklistCatalog,
    ChecklistDefinition,
)
from app.domain.enums import ChecklistCode


class YamlChecklistRepository:
    """Хранилище постоянных чек-листов с Pydantic-валидацией при старте."""

    def __init__(
        self,
        resources_dir: Path,
    ) -> None:
        self._resources_dir = resources_dir

        self._catalog = (
            self._load_catalog()
        )

        self._definitions = (
            self._load_definitions()
        )

        catalog_codes = {
            item.code
            for item
            in self._catalog.checklists
        }

        definition_codes = set(
            self._definitions
        )

        if catalog_codes != definition_codes:
            raise ValueError(
                "Checklist catalog and definitions "
                "contain different codes: "
                f"catalog={sorted(catalog_codes)}, "
                f"definitions={sorted(definition_codes)}"
            )

    def get(
        self,
        code: ChecklistCode,
    ) -> ChecklistDefinition:
        """Получить чек-лист по коду."""
        try:
            return self._definitions[
                code
            ]
        except KeyError as exc:
            raise KeyError(
                f"Unknown checklist code: {code}"
            ) from exc

    def list(
        self,
    ) -> tuple[ChecklistDefinition, ...]:
        """Вернуть чек-листы в порядке каталога."""
        return tuple(
            self._definitions[
                item.code
            ]
            for item
            in self._catalog.checklists
        )

    def get_catalog(
        self,
    ) -> ChecklistCatalog:
        """Вернуть провалидированный каталог классификации."""
        return self._catalog

    def _load_catalog(
        self,
    ) -> ChecklistCatalog:
        path = (
            self._resources_dir
            / "catalog.yaml"
        )

        payload = self._read_yaml(
            path
        )

        return ChecklistCatalog.model_validate(
            payload
        )

    def _load_definitions(
        self,
    ) -> dict[
        ChecklistCode,
        ChecklistDefinition,
    ]:
        definitions: dict[
            ChecklistCode,
            ChecklistDefinition,
        ] = {}

        directory = (
            self._resources_dir
            / "definitions"
        )

        for path in sorted(
            directory.glob("*.yaml")
        ):
            definition = (
                ChecklistDefinition.model_validate(
                    self._read_yaml(path)
                )
            )

            if definition.code in definitions:
                raise ValueError(
                    "Duplicate checklist definition: "
                    f"{definition.code}"
                )

            definitions[
                definition.code
            ] = definition

        if not definitions:
            raise ValueError(
                "Checklist definitions "
                f"not found in {directory}"
            )

        return definitions

    @staticmethod
    def _read_yaml(
        path: Path,
    ) -> object:
        """Безопасно прочитать YAML."""
        if not path.is_file():
            raise FileNotFoundError(
                path
            )

        with path.open(
            "r",
            encoding="utf-8",
        ) as file:
            return yaml.safe_load(
                file
            )
        