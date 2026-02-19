# Copilot Instructions — Max Min Integration

## Projecte

Integració custom de Home Assistant per rastrejar valors màxims, mínims i delta de sensors numèrics amb suport per períodes (daily, weekly, monthly, yearly, all time).

- **Repo**: `PacmanForever/max_min`
- **Idioma del codi**: anglès (comentaris, docstrings, noms de variables)
- **Idioma de comunicació**: català

## Entorn de desenvolupament

- **OS**: Linux (Debian/Ubuntu)
- **Python**: 3.13
- **Virtualenv**: `venv/` a l'arrel del projecte
- **Tests**: pytest amb freezegun, pytest-asyncio, pytest-cov, pytest-homeassistant-custom-component
- **Cobertura objectiu**: >99% en coordinator.py i sensor.py

## Arquitectura del codi

- `coordinator.py`: Lògica central — reset scheduling, inline resets, offset/dead zone, tracked_data
- `sensor.py`: Entitats HA — `_BaseMaxMinSensor` base class, `MaxSensor`, `MinSensor`, `DeltaSensor`
- `config_flow.py`: UI de configuració amb suport per períodes, tipus, offset, initial values
- `__init__.py`: Setup/unload d'entrada de configuració

## Convencions

- Commits en anglès, format: `vX.Y.Z: descripció breu`
- Changelog: format `# X.Y.Z - YYYY-MM-DD` amb seccions `## Fixed`, `## Improved`, `## Added`, `## Changed`
- Sempre executar tots els tests abans de commit
- Tags: `vX.Y.Z`
- Releases: via `gh release create` o GitHub Actions automàtic

## Home Assistant — Context de l'usuari

<!-- Omple aquesta secció amb la teva configuració real -->

- **Versió HA**: 
- **Tipus d'instal·lació**: (HAOS / Docker / Core / Supervised)
- **Sensors que uses amb max_min**:
  - Temperatura (sensor.xxx)
  - Pressió atmosfèrica (sensor.xxx)
  - Pluja acumulada (sensor.xxx) — cumulative, amb offset
  - ...
- **Altres integracions rellevants**: 

## Skills i coneixements de l'usuari

<!-- Afegeix aquí els teus skills perquè Copilot adapti les explicacions -->

- Home Assistant:
  - Configuració YAML: (bàsic / intermedi / avançat)
  - Automatitzacions: (bàsic / intermedi / avançat)
  - Custom integrations: (bàsic / intermedi / avançat)
  - Plantilles Jinja2: (bàsic / intermedi / avançat)
  - HACS: (bàsic / intermedi / avançat)
- Python: (bàsic / intermedi / avançat)
- Git: (bàsic / intermedi / avançat)
- Altres:
  - 

## Patrons HA recomanats (referència del core)

- **`runtime_data`**: Implementat. Mantenir `entry.runtime_data` (no tornar a `hass.data[DOMAIN][entry_id]`).
- **`integration_type`**: **Decisió de producte: mantenir `"hub"`** per visibilitat al llistat principal d'integracions de HA. No canviar a `"helper"` sense validar impacte UX amb l'usuari.
- **`PLATFORMS` constant**: Definir `PLATFORMS = ["sensor"]` i usar `async_unload_platforms(entry, PLATFORMS)` en lloc de `async_forward_entry_unload(entry, "sensor")`
- **`MINOR_VERSION`**: Afegir `MINOR_VERSION = 1` al config flow
- **`config_entry` al coordinator**: Passar `config_entry=config_entry` al `super().__init__()` de `DataUpdateCoordinator`
- **`_attr_has_entity_name = True`**: Patró modern amb `translation_key` per noms d'entitats internacionalitzables (millora futura)
- **URLs manifest**: Assegurar que `documentation` i `issue_tracker` apunten a `max_min` (no `max-min`)

## Lliçons apreses (no repetir errors)

- No usar `async_track_time_change` per resets periòdics → usar `async_track_point_in_time`
- `return` vs `continue` en loops de períodes — `return` salta tots els períodes restants
- `expected_unique_ids` ha d'incloure TOTS els tipus (max, min, delta) o es borren entitats al reload
- Inline reset ha de respectar l'offset per sensors cumulatius
- Dades restaurades sense `last_reset` s'han d'ignorar si el període ja està inicialitzat
- Valors inicials configurats s'han d'enforçar com a floor/ceiling després del restore
- **Chain Break Protection**: En callbacks temporitzats (`async_track_point_in_time`), la reprogramació del següent event ha d'anar SEMPRE en un bloc `finally`. Si la lògica falla (ex: sensor unavailable), la cadena de resets no es pot trencar mai.
- **Patró Watchdog**: No confiar cegament en un sol timer per events crítics (com resets de mitjanit). Implementar un Watchdog periòdic (ex: cada 10 min) que verifiqui `last_reset < periode_start` i forci el reset si s'ha perdut, respectant offsets.

## Preferències

- Respostes en català
- Codi en anglès
- Prioritzar correcció sobre velocitat
- Executar tests complets abans de considerar una tasca acabada
- No crear fitxers .md de resum tret que es demani explícitament
